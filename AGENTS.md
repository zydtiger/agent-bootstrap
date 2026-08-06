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

Do not stage, commit, configure remotes, push, tag, release, or publish unless explicitly requested.
