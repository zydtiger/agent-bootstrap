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

## Versioning and Releases

- Follow Semantic Versioning for the package version in `pyproject.toml` and keep `uv.lock` synchronized.
- Increment PATCH for backward-compatible fixes, MINOR for backward-compatible functionality, and MAJOR for breaking changes after `1.0.0`.
- Before `1.0.0`, increment MINOR for breaking API or manifest behavior changes; reserve PATCH for backward-compatible fixes.
- Treat manifest schema versions independently from the package version. Increment the schema only when a manifest shape or meaning requires explicit opt-in, and preserve older schemas when compatibility is intentional.
- Tag releases from `main` as `v<package-version>` and create the matching GitHub release only after the required validation succeeds.

Do not stage, commit, configure remotes, push, tag, release, or publish unless explicitly requested.
