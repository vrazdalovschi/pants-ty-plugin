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

    default_version = "0.0.29"
    default_known_versions = [
        "0.0.29|linux_arm64|7b4e2a2b0226ab53213ef61c9526be8263c6468a2f3e7b46141cf43ec7434126|10005797",
        "0.0.29|linux_x86_64|2b690a1387de766261054edc830d2345a2c0d165cf481b593d3443f1f68cab39|10841263",
        "0.0.29|macos_arm64|56df4b58d46a80b6c6b1877efd6e2af73ddf7ec729453e73ae05df92ebdf27c9|9536500",
        "0.0.29|macos_x86_64|67ffbc6bc473e1b0a33f04800162402deea1c7dae73a61cfd200ba1d6bd7fa2a|10186860",
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
