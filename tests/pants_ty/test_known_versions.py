from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from pants_ty.known_versions import (
    DEFAULT_URL_PLATFORM_MAPPING,
    format_known_versions_block,
    generate_known_versions,
)


class TyKnownVersionsTest(unittest.TestCase):
    def test_generate_known_versions_for_local_release_artifacts(self) -> None:
        version = "0.0.99"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            release_dir = root / version
            release_dir.mkdir()

            expected_entries: list[str] = []
            for index, (pants_platform, upstream_platform) in enumerate(
                DEFAULT_URL_PLATFORM_MAPPING.items(),
                start=1,
            ):
                file_name = f"ty-{upstream_platform}.tar.gz"
                payload = f"{pants_platform}-{index}".encode()
                path = release_dir / file_name
                path.write_bytes(payload)
                expected_entries.append(
                    f"{version}|{pants_platform}|{hashlib.sha256(payload).hexdigest()}|{len(payload)}"
                )

            entries = generate_known_versions(
                version,
                url_template=f"{root.as_uri()}/{{version}}/ty-{{platform}}.tar.gz",
            )

        self.assertEqual(entries, tuple(expected_entries))

    def test_format_known_versions_block_renders_ready_to_paste_config(self) -> None:
        block = format_known_versions_block(
            "0.0.25",
            (
                "0.0.25|linux_x86_64|abc|123",
                "0.0.25|macos_arm64|def|456",
            ),
        )

        self.assertEqual(
            block,
            "\n".join(
                (
                    "[ty]",
                    'version = "0.0.25"',
                    "known_versions = [",
                    '  "0.0.25|linux_x86_64|abc|123",',
                    '  "0.0.25|macos_arm64|def|456",',
                    "]",
                )
            ),
        )
