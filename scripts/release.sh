#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release.sh [--dry-run] [--skip-checks] VERSION

Examples:
  scripts/release.sh 0.1.1
  scripts/release.sh --dry-run 0.1.1
  scripts/release.sh --skip-checks 0.1.1
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

run() {
  if [ "$DRY_RUN" = "1" ]; then
    printf '+'
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
    return 0
  fi
  "$@"
}

DRY_RUN=0
SKIP_CHECKS=0
VERSION=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --skip-checks)
      SKIP_CHECKS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      if [ -n "$VERSION" ]; then
        die "expected a single VERSION argument"
      fi
      VERSION="$1"
      ;;
  esac
  shift
done

[ -n "$VERSION" ] || {
  usage >&2
  exit 1
}

VERSION="${VERSION#v}"
TAG="v$VERSION"

case "$VERSION" in
  ''|*[!0-9A-Za-z.-]*)
    die "version must contain only letters, digits, dots, and hyphens"
    ;;
esac

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git repository"
[ "$(git branch --show-current)" = "main" ] || die "release script must run from main"
git diff --quiet || die "working tree has unstaged changes"
git diff --cached --quiet || die "working tree has staged but uncommitted changes"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag already exists locally: $TAG"
git remote get-url origin >/dev/null 2>&1 || die "git remote 'origin' is not configured"

if git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
  die "tag already exists on origin: $TAG"
fi

if [ "$SKIP_CHECKS" = "0" ]; then
  run ruff check pants-plugins tests
  run pants test ::
  run pants check ::
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "Would update pyproject.toml and pants-plugins/pants_ty/__init__.py to version $VERSION"
else
  python3 - "$VERSION" <<'PY'
from pathlib import Path
import re
import sys

version = sys.argv[1]

pyproject = Path("pyproject.toml")
init_py = Path("pants-plugins/pants_ty/__init__.py")

pyproject_text = pyproject.read_text()
updated_pyproject, count = re.subn(
    r'(?m)^version = "[^"]+"$',
    f'version = "{version}"',
    pyproject_text,
    count=1,
)
if count != 1:
    raise SystemExit("Could not update version in pyproject.toml")
pyproject.write_text(updated_pyproject)

init_text = init_py.read_text()
updated_init, count = re.subn(
    r'(?m)^__version__ = "[^"]+"$',
    f'__version__ = "{version}"',
    init_text,
    count=1,
)
if count != 1:
    raise SystemExit("Could not update __version__ in pants-plugins/pants_ty/__init__.py")
init_py.write_text(updated_init)
PY
fi

run git add pyproject.toml pants-plugins/pants_ty/__init__.py
run git commit -m "Release $TAG"
run git tag -a "$TAG" -m "Release $TAG"
run git push origin main
run git push origin "$TAG"

echo "Release prepared: $TAG"
