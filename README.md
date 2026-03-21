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
plugins = ["pants-ty==0.1.1"]
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

Create either `ty.toml` or add `[tool.ty]` to `pyproject.toml`.

Example:

```toml
[tool.ty]
exclude = [".pants.d", "dist"]
```

Pants exposes the plugin options under `[ty]`:

```toml
[ty]
args = ["--output-format=concise"]
config_discovery = true
```

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

## Development

This repo uses Pants to lint, test, and dogfood the plugin itself.

```bash
ruff check pants-plugins tests
pants test ::
pants check ::
```

To build a distributable wheel and sdist:

```bash
python -m build
```

### Automated releases

After you configure PyPI trusted publishing for this repository, you can cut a release with:

```bash
scripts/release.sh 0.1.2
```

The script will:

- require a clean `main` branch
- run `ruff check pants-plugins tests`, `pants test ::`, and `pants check ::`
- update the version in `pyproject.toml`
- update `pants-plugins/pants_ty/__init__.py`
- create a release commit
- create an annotated tag like `v0.1.2`
- push `main`
- push the tag

Useful flags:

```bash
scripts/release.sh --dry-run 0.1.2
scripts/release.sh --skip-checks 0.1.2
```

## Repository layout

- `pants-plugins/pants_ty`: plugin source
- `tests/pants_ty`: unit and integration tests
- `pants.toml`: local development config
- `pants.ci.toml`: CI-specific Pants settings

## Notes

- The Pants plugin API is not stable across minor versions. This repo currently targets
  Pants `2.31.x`.
- The backend only resolves imports that Pants already knows through source roots and
  target resolves.
