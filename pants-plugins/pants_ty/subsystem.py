from __future__ import annotations

from collections.abc import Iterable

from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.config_files import ConfigFilesRequest
from pants.core.util_rules.external_tool import TemplatedExternalTool
from pants.engine.platform import Platform
from pants.engine.rules import Rule, collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import (
    ArgsListOption,
    BoolOption,
    FileOption,
    SkipOption,
    StrListOption,
)
from pants.util.strutil import softwrap

from pants_ty.known_versions import DEFAULT_URL_PLATFORM_MAPPING, DEFAULT_URL_TEMPLATE


class Ty(TemplatedExternalTool):
    options_scope = "ty"
    name = "Ty"
    help = softwrap(
        """
        The Ty Python type checker (https://docs.astral.sh/ty/).
        """
    )

    default_version = "0.0.39"
    default_known_versions = [
        "0.0.39|linux_arm64|b641dd6f979e8cd97385117fa41911a30a97b8a442b3d08ff34d9ea250f901d7|10559967",
        "0.0.39|linux_x86_64|cad6e749c94afe53f1d98b57adc7a5686386e23fe8a05203369cd754b95d9183|11445704",
        "0.0.39|macos_arm64|adc872b644952661d5e299780a10f8a0f6d527856063f928b5d54eddd2634039|10077256",
        "0.0.39|macos_x86_64|dcc711a294d284f15d7757632926954c5f21bf4b2e2ca00b6e4a8006960eafe9|10775488",
    ]
    default_url_template = DEFAULT_URL_TEMPLATE
    default_url_platform_mapping = DEFAULT_URL_PLATFORM_MAPPING

    skip = SkipOption("check")
    args = ArgsListOption(example="--error-on-warning --output-format=concise")
    config = FileOption(
        default=None,
        advanced=True,
        help=softwrap(
            """
            Path to a `ty.toml` file to use for configuration.

            Setting this option disables `[ty].config_discovery`.
            """
        ),
    )
    config_discovery = BoolOption(
        default=True,
        advanced=True,
        help=softwrap(
            """
            If true, Pants will include relevant Ty config files during runs
            (`ty.toml` and `pyproject.toml` containing `[tool.ty]`).
            """
        ),
    )
    _interpreter_constraints = StrListOption(
        advanced=True,
        default=["CPython>=3.8,<3.15"],
        help="Python interpreter constraints for Ty.",
    )

    def generate_exe(self, plat: Platform) -> str:
        return f"ty-{self.default_url_platform_mapping[plat.value]}/ty"

    @property
    def interpreter_constraints(self) -> InterpreterConstraints:
        return InterpreterConstraints(self._interpreter_constraints)

    def config_request(self) -> ConfigFilesRequest:
        return ConfigFilesRequest(
            specified=self.config,
            specified_option_name=f"{self.options_scope}.config",
            discovery=self.config_discovery,
            check_existence=["ty.toml"],
            check_content={"pyproject.toml": b"[tool.ty"},
        )


def rules() -> Iterable[Rule | UnionRule]:
    return (
        *collect_rules(),
        *Ty.rules(),
        UnionRule(ExportableTool, Ty),
    )
