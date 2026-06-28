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

    default_version = "0.0.55"
    default_known_versions = [
        "0.0.55|linux_arm64|a002a950a7e7ae1bc07a275b992414f4e2b001e8c46ac86c6e1086496e799701|10959082",
        "0.0.55|linux_x86_64|654d2c98d65419aedeac57cf29ca8d60ee1798abd6d9f9a6a1789c50b76261e5|11780419",
        "0.0.55|macos_arm64|877d3b410f233bcc5746332ac999a3c94e4afab6fbd488b0712f971bbe590115|10495164",
        "0.0.55|macos_x86_64|9dd2cd9041ca5d4bd44516ce71b9768bb289c3baa2c9bd65283d25cde7901df8|11118544",
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
