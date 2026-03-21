from __future__ import annotations

import unittest
from types import SimpleNamespace

from pants.engine.platform import Platform
from pants.core.util_rules.external_tool import TemplatedExternalTool

from pants_ty.subsystem import Ty


class TySubsystemTest(unittest.TestCase):
    def test_ty_is_templated_external_tool(self) -> None:
        self.assertTrue(issubclass(Ty, TemplatedExternalTool))

    def test_generate_exe_uses_expected_platform_paths(self) -> None:
        subsystem = object.__new__(Ty)

        self.assertEqual(
            subsystem.generate_exe(Platform.linux_x86_64),
            "ty-x86_64-unknown-linux-musl/ty",
        )
        self.assertEqual(
            subsystem.generate_exe(Platform.macos_arm64),
            "ty-aarch64-apple-darwin/ty",
        )

    def test_config_request_discovers_ty_configs(self) -> None:
        subsystem = object.__new__(Ty)
        subsystem.options = SimpleNamespace(config=None, config_discovery=True)
        request = subsystem.config_request()

        self.assertTrue(request.discovery)
        self.assertEqual(request.check_existence, ("ty.toml",))
        self.assertEqual(request.check_content, {"pyproject.toml": b"[tool.ty"})

    def test_subsystem_exposes_basic_options(self) -> None:
        self.assertEqual(Ty.options_scope, "ty")
        self.assertIsNotNone(Ty.skip)
        self.assertIsNotNone(Ty.args)
        self.assertIsNotNone(Ty.version)
        self.assertIsNotNone(Ty.known_versions)

    def test_known_versions_use_exact_platform_keys(self) -> None:
        platform_keys = {entry.split("|")[1] for entry in Ty.default_known_versions}
        self.assertEqual(
            platform_keys,
            {"linux_arm64", "linux_x86_64", "macos_arm64", "macos_x86_64"},
        )
