from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pants.backend.python.subsystems.setup import PythonSetup
from pants.backend.python.target_types import (
    InterpreterConstraintsField,
    PythonResolveField,
    PythonSourceField,
)
from pants.backend.python.util_rules import pex_from_targets
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.partition import (
    _partition_by_interpreter_constraints_and_resolve,
)
from pants.backend.python.util_rules.pex import (
    PexRequest,
    VenvPexProcess,
    VenvPexRequest,
    create_pex,
    create_venv_pex,
)
from pants.backend.python.util_rules.pex_environment import PexEnvironment
from pants.backend.python.util_rules.pex_from_targets import RequirementsPexRequest
from pants.backend.python.util_rules.python_sources import (
    PythonSourceFilesRequest,
    prepare_python_sources,
)
from pants.core.goals.check import CheckRequest, CheckResult, CheckResults
from pants.core.util_rules import config_files
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.external_tool import download_external_tool
from pants.core.util_rules.source_files import SourceFilesRequest, determine_source_files
from pants.engine.collection import Collection
from pants.engine.fs import MergeDigests
from pants.engine.internals.graph import resolve_coarsened_targets
from pants.engine.intrinsics import execute_process, merge_digests
from pants.engine.platform import Platform
from pants.engine.process import Process, ProcessCacheScope, execute_process_or_raise
from pants.engine.rules import Rule, collect_rules, concurrently, implicitly, rule
from pants.engine.target import (
    CoarsenedTargets,
    CoarsenedTargetsRequest,
    FieldSet,
    Target,
)
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.ordered_set import FrozenOrderedSet, OrderedSet
from pants.util.strutil import pluralize

from pants_ty.skip_field import SkipTyField
from pants_ty.subsystem import Ty


def _python_version_args(
    *, python_version: str | None, user_args: Sequence[str]
) -> tuple[str, ...]:
    if python_version is None:
        return ()
    if any(
        arg.startswith("--python-version=") or arg.startswith("--target-version=")
        for arg in user_args
    ):
        return ()
    return (f"--python-version={python_version}",)


def _extra_search_path_args(source_roots: Sequence[str]) -> tuple[str, ...]:
    unique_source_roots = tuple(dict.fromkeys(source_roots))
    return tuple(f"--extra-search-path={source_root}" for source_root in unique_source_roots)


def _batch_input_paths(
    paths: Sequence[str], *, max_paths_per_batch: int
) -> tuple[tuple[str, ...], ...]:
    if max_paths_per_batch <= 0:
        raise ValueError("max_paths_per_batch must be positive")
    if not paths:
        return ()
    return tuple(
        tuple(paths[index : index + max_paths_per_batch])
        for index in range(0, len(paths), max_paths_per_batch)
    )


@dataclass(frozen=True)
class TyFieldSet(FieldSet):
    required_fields = (PythonSourceField,)

    sources: PythonSourceField
    resolve: PythonResolveField
    interpreter_constraints: InterpreterConstraintsField

    @classmethod
    def opt_out(cls, tgt: Target) -> bool:
        return tgt.get(SkipTyField).value


class TyRequest(CheckRequest):
    field_set_type = TyFieldSet
    tool_name = Ty.options_scope


@dataclass(frozen=True)
class TyPartition:
    field_sets: FrozenOrderedSet[TyFieldSet]
    root_targets: CoarsenedTargets
    resolve_description: str | None
    interpreter_constraints: InterpreterConstraints

    def description(self) -> str:
        ics = str(sorted(str(c) for c in self.interpreter_constraints))
        return f"{self.resolve_description}, {ics}" if self.resolve_description else ics


class TyPartitions(Collection[TyPartition]):
    pass


@rule(
    desc="Determine if it is necessary to partition Ty's input",
    level=LogLevel.DEBUG,
)
async def ty_determine_partitions(
    request: TyRequest,
    ty: Ty,
    python_setup: PythonSetup,
) -> TyPartitions:
    resolve_and_interpreter_constraints_to_field_sets = (
        _partition_by_interpreter_constraints_and_resolve(request.field_sets, python_setup)
    )

    coarsened_targets = await resolve_coarsened_targets(
        CoarsenedTargetsRequest(field_set.address for field_set in request.field_sets),
        **implicitly(),
    )
    coarsened_targets_by_address = coarsened_targets.by_address()

    return TyPartitions(
        TyPartition(
            FrozenOrderedSet(field_sets),
            CoarsenedTargets(
                OrderedSet(
                    coarsened_targets_by_address[field_set.address] for field_set in field_sets
                )
            ),
            resolve if len(python_setup.resolves) > 1 else None,
            interpreter_constraints or ty.interpreter_constraints,
        )
        for (resolve, interpreter_constraints), field_sets in sorted(
            resolve_and_interpreter_constraints_to_field_sets.items()
        )
    )


@rule(desc="Typecheck one Ty partition", level=LogLevel.DEBUG)
async def ty_typecheck_partition(
    partition: TyPartition,
    ty: Ty,
    platform: Platform,
    pex_environment: PexEnvironment,
    python_setup: PythonSetup,
) -> CheckResult:
    (
        ty_tool,
        config_files_snapshot,
        root_sources,
        transitive_sources,
        requirements_pex,
    ) = await concurrently(
        download_external_tool(ty.get_request(platform)),
        find_config_file(ty.config_request()),
        determine_source_files(SourceFilesRequest(fs.sources for fs in partition.field_sets)),
        prepare_python_sources(
            PythonSourceFilesRequest(partition.root_targets.closure()), **implicitly()
        ),
        create_pex(
            **implicitly(
                RequirementsPexRequest(
                    (fs.address for fs in partition.field_sets),
                    hardcoded_interpreter_constraints=partition.interpreter_constraints,
                )
            )
        ),
    )

    complete_pex_env = pex_environment.in_workspace()
    requirements_venv_pex = await create_venv_pex(
        VenvPexRequest(
            PexRequest(
                output_filename="requirements_venv.pex",
                internal_only=True,
                pex_path=[requirements_pex],
                interpreter_constraints=partition.interpreter_constraints,
            ),
            complete_pex_env,
        ),
        **implicitly(),
    )

    _ = await execute_process_or_raise(
        **implicitly(
            VenvPexProcess(
                requirements_venv_pex,
                description="Force Ty requirements venv to materialize",
                argv=["-c", "''"],
                cache_scope=ProcessCacheScope.PER_SESSION,
            )
        )
    )

    input_digest = await merge_digests(
        MergeDigests(
            (
                transitive_sources.source_files.snapshot.digest,
                config_files_snapshot.snapshot.digest,
                requirements_venv_pex.digest,
            )
        )
    )

    immutable_input_key = "__ty_tool"
    exe_path = os.path.join(immutable_input_key, ty_tool.exe)
    requirements_venv_path = os.path.join(
        complete_pex_env.pex_root, requirements_venv_pex.venv_rel_dir
    )

    python_version = partition.interpreter_constraints.minimum_python_version(
        python_setup.interpreter_versions_universe
    )
    config_args = (f"--config-file={ty.config}",) if ty.config else ()
    common_args = (
        "check",
        *config_args,
        f"--python={requirements_venv_path}",
        *_python_version_args(python_version=python_version, user_args=ty.args),
        *_extra_search_path_args(transitive_sources.source_roots),
        *ty.args,
    )
    path_batches = _batch_input_paths(tuple(root_sources.snapshot.files), max_paths_per_batch=512)

    if not path_batches:
        return CheckResult(0, "", "", partition_description=partition.description())

    batch_results = await concurrently(
        execute_process(
            Process(
                argv=(exe_path, *common_args, *path_batch),
                input_digest=input_digest,
                immutable_input_digests={immutable_input_key: ty_tool.digest},
                description=f"Run Ty on {pluralize(len(path_batch), 'file')}.",
                level=LogLevel.DEBUG,
            ),
            **implicitly(),
        )
        for path_batch in path_batches
    )

    return CheckResult(
        exit_code=max(result.exit_code for result in batch_results),
        stdout="".join(result.stdout.decode() for result in batch_results),
        stderr="".join(result.stderr.decode() for result in batch_results),
        partition_description=partition.description(),
    )


@rule(desc="Typecheck using Ty", level=LogLevel.DEBUG)
async def ty_typecheck(
    request: TyRequest,
    ty: Ty,
) -> CheckResults:
    if ty.skip:
        return CheckResults([], checker_name=request.tool_name)

    partitions = await ty_determine_partitions(request, **implicitly())
    partitioned_results = await concurrently(
        ty_typecheck_partition(partition, **implicitly()) for partition in partitions
    )
    return CheckResults(partitioned_results, checker_name=request.tool_name)


def rules() -> Iterable[Rule | UnionRule]:
    return (
        *collect_rules(),
        *config_files.rules(),
        *pex_from_targets.rules(),
        UnionRule(CheckRequest, TyRequest),
    )
