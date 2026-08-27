# Repository Guidelines

## Purpose

- Keep this repository focused on deterministic assembly of global Codex instructions.
- Keep personal preferences, host details, credentials, and generated `AGENTS.md` files out of this repository.
- Treat `manifest.toml` as configuration supplied by a separate consumer repository.
- Keep the CLI Codex-specific until another target is explicitly approved.

## Design

- Keep Typer in `cli.py`; core parsing, rendering, and installation must remain callable without it.
- Keep manifest parsing strict and schema-versioned.
- Resolve fragments relative to the manifest and reject paths that escape its directory.
- Keep rendering deterministic: no timestamps, environment interpolation, or executable templates.
- Publish instruction files atomically and refuse unmanaged-file replacement by default.

## Development

Use uv for environment, dependency, command, and build operations:

```bash
uv sync
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

Ruff, mypy and lockfile consistency are enforced by the commit-stage hooks in
`.pre-commit-config.yaml`, and pytest by the `pre-push` stage hook. Install the
runner once per machine:

```bash
uv tool install prek
prek install
```

CI (`.github/workflows/ci.yml`) invokes the same hook runner rather than
restating hook commands: a `lint` job runs the commit-stage hooks once, and a
matrixed `test` job runs the pre-push stage on every supported Python version,
then builds and smoke-tests the wheel on the lowest one.

## Versioning and Releases

- Follow Semantic Versioning for the package version in `pyproject.toml` and keep `uv.lock` synchronized.
- Increment PATCH for backward-compatible fixes, MINOR for backward-compatible functionality, and MAJOR for breaking changes after `1.0.0`.
- Before `1.0.0`, increment MINOR for breaking API or manifest behavior changes; reserve PATCH for backward-compatible fixes.
- Treat manifest schema versions independently from the package version. Increment the schema only when a manifest shape or meaning requires explicit opt-in, and preserve older schemas when compatibility is intentional.
- Tag releases from `main` as `v<package-version>` and create the matching GitHub release only after the required validation succeeds.
- Never move or replace an existing release tag. A repository ruleset named `protect-release-tags` enforces this on the remote for `refs/tags/v*`, denying tag deletion, non-fast-forward updates, and updates, with no bypass. A rejected tag push is that rule working, not a broken remote.

Do not stage, commit, configure remotes, push, tag, release, or publish unless explicitly requested.
