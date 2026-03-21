from __future__ import annotations

import unittest

from pants_ty.rules import (
    _batch_input_paths,
    _extra_search_path_args,
    _python_version_args,
)


class TyRulesHelperTest(unittest.TestCase):
    def test_python_version_args_autosets_when_not_overridden(self) -> None:
        self.assertEqual(
            _python_version_args(python_version="3.11", user_args=()),
            ("--python-version=3.11",),
        )

    def test_python_version_args_respects_user_override(self) -> None:
        self.assertEqual(
            _python_version_args(
                python_version="3.11",
                user_args=("--python-version=3.12", "--error-on-warning"),
            ),
            (),
        )
        self.assertEqual(
            _python_version_args(
                python_version="3.11",
                user_args=("--target-version=3.12",),
            ),
            (),
        )

    def test_extra_search_path_args_preserves_order_and_deduplicates(self) -> None:
        self.assertEqual(
            _extra_search_path_args(("src/python", "libs/shared", "src/python")),
            (
                "--extra-search-path=src/python",
                "--extra-search-path=libs/shared",
            ),
        )

    def test_batch_input_paths_splits_large_inputs(self) -> None:
        self.assertEqual(
            _batch_input_paths(
                ("a.py", "b.py", "c.py", "d.py", "e.py"),
                max_paths_per_batch=2,
            ),
            (
                ("a.py", "b.py"),
                ("c.py", "d.py"),
                ("e.py",),
            ),
        )
