from __future__ import annotations

import argparse
import hashlib
from collections.abc import Mapping, Sequence
from urllib.request import urlopen

DEFAULT_URL_TEMPLATE = (
    "https://github.com/astral-sh/ty/releases/download/{version}/ty-{platform}.tar.gz"
)
DEFAULT_URL_PLATFORM_MAPPING = {
    "linux_arm64": "aarch64-unknown-linux-musl",
    "linux_x86_64": "x86_64-unknown-linux-musl",
    "macos_arm64": "aarch64-apple-darwin",
    "macos_x86_64": "x86_64-apple-darwin",
}


def _normalize_platforms(
    platforms: Sequence[str] | None,
    *,
    platform_mapping: Mapping[str, str],
) -> tuple[str, ...]:
    if not platforms:
        return tuple(platform_mapping.keys())

    unknown_platforms = tuple(platform for platform in platforms if platform not in platform_mapping)
    if unknown_platforms:
        expected = ", ".join(sorted(platform_mapping))
        unknown = ", ".join(unknown_platforms)
        raise ValueError(f"Unknown Pants platform(s): {unknown}. Expected one of: {expected}")

    return tuple(platforms)


def _download_metadata(url: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    length = 0

    with urlopen(url) as response:
        while chunk := response.read(64 * 1024):
            digest.update(chunk)
            length += len(chunk)

    return digest.hexdigest(), length


def generate_known_versions(
    version: str,
    *,
    url_template: str = DEFAULT_URL_TEMPLATE,
    platform_mapping: Mapping[str, str] = DEFAULT_URL_PLATFORM_MAPPING,
    platforms: Sequence[str] | None = None,
) -> tuple[str, ...]:
    entries: list[str] = []

    for pants_platform in _normalize_platforms(platforms, platform_mapping=platform_mapping):
        upstream_platform = platform_mapping[pants_platform]
        url = url_template.format(version=version, platform=upstream_platform)
        sha256, length = _download_metadata(url)
        entries.append(f"{version}|{pants_platform}|{sha256}|{length}")

    return tuple(entries)


def format_known_versions_block(version: str, entries: Sequence[str]) -> str:
    lines = [
        "[ty]",
        f'version = "{version}"',
        "known_versions = [",
        *(f'  "{entry}",' for entry in entries),
        "]",
    ]
    return "\n".join(lines)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Pants [ty].known_versions entries for a ty release.",
    )
    parser.add_argument("version", help="ty version to inspect, for example 0.0.25")
    parser.add_argument(
        "--platform",
        dest="platforms",
        action="append",
        choices=tuple(DEFAULT_URL_PLATFORM_MAPPING),
        help="Limit output to one Pants platform. May be passed multiple times.",
    )
    parser.add_argument(
        "--url-template",
        default=DEFAULT_URL_TEMPLATE,
        help=(
            "Download URL template. Use {version} and {platform}. "
            "Defaults to the official Astral GitHub release archive pattern."
        ),
    )
    parser.add_argument(
        "--entries-only",
        action="store_true",
        help="Print only the known_versions entries instead of a full [ty] block.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_argument_parser()
    args = parser.parse_args(argv)
    version = args.version.removeprefix("v")
    entries = generate_known_versions(
        version,
        url_template=args.url_template,
        platforms=args.platforms,
    )

    if args.entries_only:
        print("\n".join(f'"{entry}",' for entry in entries))
    else:
        print(format_known_versions_block(version, entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
