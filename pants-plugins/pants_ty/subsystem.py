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

    default_version = "0.0.34"
    default_known_versions = [
        "0.0.34|linux_arm64|658fbb36846d28ed4e71df0ddaf3bf6f5ac64913ae2fe2105b086436a123e3fd|10396325",
        "0.0.34|linux_x86_64|6579d8436fb17f49f338aed854027464a259af2cbf92fde10717461d8c867c90|11262666",
        "0.0.34|macos_arm64|7f571161be28cb2ca211f609959b23dd8cea79b7b5b7857c3970e5f69a872fec|9885026",
        "0.0.34|macos_x86_64|aa28bac4ad4ffd138fd94b1274049f269835752aab2b9bc1d5044ca0f08062d3|10576878",
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
