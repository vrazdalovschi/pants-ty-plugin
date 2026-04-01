# pants-ty-plugin

`pants-ty-plugin` adds a Pants `check` backend for [Astral ty](https://docs.astral.sh/ty/).

It is designed for Pants `2.31.x` and currently supports Linux and macOS. The backend installs
`ty` as an external binary, then runs it with:

- a resolve-backed Python environment for third-party dependencies
- Pants source roots as `--extra-search-path` entries for first-party imports

That means `ty` can resolve imports that Pants already knows about.

## Features

- `pants check --only=ty ...`
- `skip_ty = true` on Python targets
- `ty.toml` discovery
- `[tool.ty]` discovery from `pyproject.toml`
- resolve-aware `--python`
- source-root-aware `--extra-search-path`

## Install

### Option 1: install from PyPI through Pants

The recommended installation path is to use the published package from PyPI:

- PyPI: https://pypi.org/project/pants-ty/

Add the plugin to your repo's Pants config:

```toml
[GLOBAL]
plugins = ["pants-ty==0.1.2"]
backend_packages = [
  "pants.backend.python",
  "pants_ty",
]
```

Pants installs published plugins separately from your code resolves. Do not add `pants-ty`
to a resolve, lockfile, or `python_requirement`.

Then add your `ty.toml` or `[tool.ty]` config and run:

```bash
pants help ty
pants check --only=ty ::
```

### Option 2: vendor the plugin into a private repo

Copy only the Python package files from `pants-plugins/pants_ty/` into your repo's
`pants-plugins/pants_ty/` directory:

- `__init__.py`
- `register.py`
- `rules.py`
- `skip_field.py`
- `subsystem.py`

Do not copy this plugin repo's development-only files:

- `pants-plugins/BUILD`
- `pants-plugins/pants_ty/BUILD`
- `pants-plugins/lock.txt`
- `tests/`
- this repo's `pants.toml`, `pyproject.toml`, or GitHub workflow files

Those files are only for developing and releasing `pants-ty-plugin` itself. A consuming repo
should use its own resolves, lockfiles, and test setup.

Then configure:

```toml
[GLOBAL]
pants_version = "2.31.0"
backend_packages = [
  "pants.backend.python",
  "pants_ty",
]
pythonpath = ["%(buildroot)s/pants-plugins"]
```

If you accidentally copy the dev `BUILD` files too, you may see an error like:

```text
UnrecognizedResolveNamesError: ... resolve ... pants-plugins
```

That means your consuming repo picked up this repo's internal development resolve. Remove the
copied `BUILD` files and keep only the plugin Python modules.

## Configure

Ty's own configuration must live in either:

- `ty.toml`
- `pyproject.toml` under `[tool.ty]`

Do not put `[tool.ty]` in `pants.toml`. Pants options go under `[ty]`.

Example:

```toml
[tool.ty]
exclude = [".pants.d", "dist"]
```

Or in a dedicated `ty.toml`:

```toml
exclude = [".pants.d", "dist"]
```

Pants exposes the plugin options under `[ty]`:

```toml
[ty]
args = ["--output-format=concise"]
config_discovery = true
```

If your `ty.toml` lives somewhere else in the repo, point Pants at it explicitly:

```toml
[ty]
config = "config/python/ty.toml"
```

### Overriding the Ty binary version

You do not need a new `pants-ty` release for every new `ty` release.

From a checkout of this repo, generate a ready-to-paste config block:

```bash
./scripts/generate_known_versions.py 0.0.27
```

That prints:

```toml
[ty]
version = "0.0.27"
known_versions = [
  "0.0.27|linux_arm64|<sha256>|<size>",
  "0.0.27|linux_x86_64|<sha256>|<size>",
  "0.0.27|macos_arm64|<sha256>|<size>",
  "0.0.27|macos_x86_64|<sha256>|<size>",
]
```

Paste that block into the consuming repo's `pants.toml`.

Useful options:

```bash
./scripts/generate_known_versions.py 0.0.27 --platform macos_arm64 --platform linux_x86_64
./scripts/generate_known_versions.py 0.0.27 --entries-only
```

Each `known_versions` entry is `version|platform|sha256|length`. By default the script uses
Astral's official GitHub release archives.

You only need to do this when you want to upgrade the downloaded `ty` binary without changing
the plugin code. If a new `ty` release requires backend changes, then release a new
`pants-ty` version.

Run `pants help-advanced ty` to see the full option shape, including `url_template` and
`url_platform_mapping`.

Useful commands:

```bash
pants help ty
pants check --only=ty ::
pants check --only=ty path/to/pkg::
```

To skip a target:

```python
python_sources(
  name="lib",
  skip_ty=True,
)
```

## Setup

This repo expects `mise` and `pants` to already be installed:

- `mise`: https://mise.jdx.dev/installing-mise.html
- `pants`: https://www.pantsbuild.org/dev/docs/getting-started/installing-pants

The `mise` tasks use the installed Pants launcher directly, while `mise` manages the repo-local
Python version used for packaging and helper scripts.

## Development

This repo uses [`mise`](https://mise.jdx.dev/) to install local development tools and provide
task entrypoints for linting, testing, and releases.

```bash
mise install
mise run lint
mise run test
mise run check
mise run verify
```

The repository-managed tools currently include:

- `python 3.11.14`

`mise run test` passes `PANTS_LAUNCHER=$(command -v pants)` into the Pants-managed test process
so the integration tests can invoke the same installed Pants launcher inside the test sandbox.

If you prefer to run the underlying commands directly, the task mapping is:

```bash
pants lint ::
pants "--test-extra-env-vars=['PANTS_LAUNCHER=$(command -v pants)']" test ::
pants check ::
```

To build a distributable wheel and sdist:

```bash
python -m build
```

### Automated releases

After you configure PyPI trusted publishing for this repository, you can cut a release with:

```bash
mise install
mise run release 0.1.2
```

The release task wraps `scripts/release.sh` and uses the repo-managed `python` tooling from
`mise` plus your installed `pants` launcher. The script will:

- require a clean `main` branch
- run `pants lint ::`, `pants test ::`, and `pants check ::`
- update the version in `pyproject.toml`
- update `pants-plugins/pants_ty/__init__.py`
- create a release commit
- create an annotated tag like `v0.1.2`
- push `main`
- push the tag

Useful flags:

```bash
mise run release-dry-run 0.1.2
mise run release -- --skip-checks 0.1.2
```

## Repository layout

- `pants-plugins/pants_ty`: plugin source
- `.mise/tasks`: local development and release task wrappers
- `mise.toml`: repo-managed tool versions
- `scripts/generate_known_versions.py`: helper to generate `[ty].known_versions` overrides
- `tests/pants_ty`: unit and integration tests
- `pants.toml`: local development config
- `pants.ci.toml`: CI-specific Pants settings

## Notes

- The Pants plugin API is not stable across minor versions. This repo currently targets
  Pants `2.31.x`.
- The backend only resolves imports that Pants already knows through source roots and
  target resolves.
