# agent-bootstrap

`agent-bootstrap` renders ordered Markdown fragments into the global Codex
instruction file at `~/.codex/AGENTS.md`.

The renderer is public and configuration-neutral. Personal preferences and
machine-specific facts belong in a separate configuration directory, which may
be a private Git repository or an untracked local directory.

## Why a manifest

The renderer does not prescribe names such as `common/`, `agents/`, or
`machines/`. A manifest declares the fragment paths and their exact order, so a
configuration repository may use any internal layout.

Only the host varies at execution time. This initial version has one fixed
target—Codex's global `~/.codex/AGENTS.md`—and intentionally has no `--agent` or
`--output` selector.

## Manifest

```toml
schema_version = 1

fragments = [
  "preferences/shared.md",
  "preferences/codex.md",
]

[hosts.workstation]
fragments = [
  "machines/workstation.md",
]

[hosts.laptop]
fragments = [
  "machines/laptop.md",
]
```

Fragment paths are relative to the manifest's directory. Rendering preserves
the declared order:

```text
top-level fragments -> selected host fragments
```

All fragments must be UTF-8 Markdown files inside the manifest directory.
Missing files, duplicate selections, absolute paths, paths that escape the
configuration directory, unknown keys, and unknown hosts are errors.

A runnable sanitized configuration is available in
[`examples/agent-config`](examples/agent-config).

## Commands

Render to standard output without changing files:

```bash
agent-bootstrap render \
  --manifest ~/agent-config/manifest.toml \
  --host workstation
```

Preview installation status and a diff:

```bash
agent-bootstrap install \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --dry-run \
  --diff
```

Install atomically to `~/.codex/AGENTS.md`:

```bash
agent-bootstrap install \
  --manifest ~/agent-config/manifest.toml \
  --host workstation
```

The installer refuses to replace an existing file that lacks its generated
marker. Review the diff and pass `--force` only when deliberately adopting an
existing target.

Check for drift:

```bash
agent-bootstrap check \
  --manifest ~/agent-config/manifest.toml \
  --host workstation
```

`check` exits with `0` when current, `1` when stale or missing, and `2` for an
invalid manifest or operational error.

## Installation

For local development:

```bash
uv sync
uv tool install --editable .
```

The package also supports:

```bash
uv run python -m agent_bootstrap --help
```

## Generated output

Generated files contain a stable header with the selected host and ordered
manifest-relative source paths. Output uses UTF-8, Unix newlines, one blank line
between fragments, and one final newline. It contains no timestamps or absolute
configuration paths, so unchanged inputs produce byte-identical output.

## Security boundary

The manifest and fragments are data, not executable templates. The renderer:

- does not execute shell commands;
- does not interpolate environment variables;
- does not read credential files;
- rejects fragment paths outside the manifest directory; and
- creates a new global instruction file with user-only permissions where the
  platform supports them.

Instruction fragments may refer to a credential location such as
`~/.codex/.env`, but must not contain tokens, passwords, private keys, or full
environment contents—even when the configuration repository is private.

## Development

```bash
uv sync
uv run ruff check .
uv run mypy
uv run pytest
uv build
```
