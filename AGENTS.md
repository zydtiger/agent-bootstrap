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

## Development and validation

Use uv for environment, dependency, command, and build operations. Install the
hook runner once per machine, then activate this clone:

```bash
uv tool install prek
prek install
```

- Full: `prek run --all-files && prek run --all-files --hook-stage pre-push`
- Targeted: `prek run --files <changed-path>... && prek run --files <changed-path>... --hook-stage pre-push`
- Documentation-only: `prek run --files <changed-document-path>... && git diff --check -- <changed-document-path>...`
- Package changes: run the full validation, then `uv build`.

`.pre-commit-config.yaml` is the sole definition of mechanical commands and
their scope. Commit subjects must start with `Merge ` or use
`prefix(scope): lowercase summary`, where the optional scope is lowercase and
the prefix is `feat`, `fix`, `docs`, `test`, `build`, `ci`, `refactor`, `perf`,
`conf`, or `chore`. The `commit-msg` hook enforces that contract; source-file
validation does not validate commit messages.

CI (`.github/workflows/ci.yml`) invokes the same hook runner rather than
restating hook commands: a `lint` job runs the commit-stage hooks once, and a
matrixed `test` job runs the pre-push stage on every supported Python version,
then builds and smoke-tests the wheel on the lowest one.

## Versioning and Releases

- Follow Semantic Versioning for the package version in `pyproject.toml` and keep `uv.lock` synchronized.
- Before changing the package version, state the exact current and proposed versions and obtain explicit user approval. Approval to implement, commit, open a pull request, or merge does not authorize a version bump.
- Treat an approved version bump as one release transaction: update and validate the package metadata, commit and push the release state, create and push the matching immutable tag, and publish the matching GitHub release. Do not leave bumped package metadata unreleased unless the user explicitly requests that exception.
- Increment PATCH for backward-compatible fixes, MINOR for backward-compatible functionality, and MAJOR for breaking changes after `1.0.0`.
- Before `1.0.0`, increment MINOR for breaking API or manifest behavior changes; reserve PATCH for backward-compatible fixes.
- Treat manifest schema versions independently from the package version. Increment the schema only when a manifest shape or meaning requires explicit opt-in, and preserve older schemas when compatibility is intentional.
- Tag releases from `main` as `v<package-version>` and create the matching GitHub release only after the required validation succeeds.
- Never move or replace an existing release tag. A repository ruleset named `protect-release-tags` enforces this on the remote for `refs/tags/v*`, denying tag deletion, non-fast-forward updates, and updates, with no bypass. A rejected tag push is that rule working, not a broken remote.

Do not stage, commit, configure remotes, push, tag, release, or publish unless explicitly requested.
