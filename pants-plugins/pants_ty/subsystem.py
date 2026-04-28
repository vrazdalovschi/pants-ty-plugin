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

    default_version = "0.0.33"
    default_known_versions = [
        "0.0.33|linux_arm64|6d24c789204226586bf7aa49da6254a2fcfde2660b0b2d0cf99ef6ea18c1edb2|10306535",
        "0.0.33|linux_x86_64|5e11c6883a73c379eda3481ed4766f34a30b7a0c2a3bc3653afb95bb74a4b7f7|11171025",
        "0.0.33|macos_arm64|df13913f8b082675788a8b10d05b0f6d0f076be2d777a1315a468c3a882e791c|9807025",
        "0.0.33|macos_x86_64|9e856908e2de49d5c319c68594846c70165a621b42071c53019a01ae9a125b0e|10512144",
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
