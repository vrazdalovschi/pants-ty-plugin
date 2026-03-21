from __future__ import annotations

import unittest

from pants_ty import register, skip_field, subsystem
from pants_ty.skip_field import SkipTyField


class SkipTyFieldTest(unittest.TestCase):
    def test_skip_field_alias(self) -> None:
        self.assertEqual(SkipTyField.alias, "skip_ty")
        self.assertFalse(SkipTyField.default)

    def test_skip_field_registers_on_expected_python_targets(self) -> None:
        registrations = tuple(skip_field.rules())
        self.assertEqual(len(registrations), 5)

    def test_register_module_includes_skip_field_rules(self) -> None:
        self.assertGreater(len(tuple(register.rules())), len(tuple(subsystem.rules())))
