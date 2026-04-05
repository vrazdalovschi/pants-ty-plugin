## Repository Operating Notes

- Use `rg` for file content searches.
- For ty known-version updates, use only `./scripts/generate_known_versions.py` and paste its
  output.
- Do not derive `known_versions` entries from ad-hoc network scraping in release work.
- In release prep, prefer this path:
  - `./scripts/generate_known_versions.py <ty_version>`
  - update `pants-ty` plugin version in `pyproject.toml` and
    `pants-plugins/pants_ty/__init__.py`
  - update `Ty.default_version` and `Ty.default_known_versions` in
    `pants-plugins/pants_ty/subsystem.py`
  - adjust README version examples.

This file is intentionally small and workflow-only to keep repeated release bumps minimal.
