# agent-bootstrap

`agent-bootstrap` renders ordered Markdown fragments into a selected global
agent instruction file.

The renderer is public and configuration-neutral. Personal preferences and
machine-specific facts belong in a separate configuration directory, which may
be a private Git repository or an untracked local directory.

## Why a manifest

The renderer does not prescribe names such as `common/`, `agents/`, or
`machines/`. A manifest declares the fragment paths and their exact order, so a
configuration repository may use any internal layout.

Each invocation selects both a configured host and an agent. The agent is
mandatory because it determines both the agent-specific fragments and the
global installation target:

- `codex`: `~/.codex/AGENTS.md`
- `pi`: `~/.pi/agent/AGENTS.md`
- `zcode`: `~/.zcode/AGENTS.md`

## Manifest

```toml
schema_version = 3

fragments = [
  "preferences/shared.md",
]

[agents.codex]
fragments = [
  "preferences/codex.md",
]

[agents.pi]
fragments = [
  "preferences/pi.md",
]

[hosts.workstation]
fragments = [
  "machines/workstation.md",
]

[hosts.laptop]
fragments = [
  "machines/laptop.md",
]

[host_agents.workstation.codex]
fragments = [
  "machines/workstation-codex.md",
]
```

Fragment paths are relative to the manifest's directory. Rendering preserves
the declared order:

```text
top-level common fragments -> selected agent fragments -> selected host fragments -> matching host-agent fragments
```

All fragments must be UTF-8 Markdown files inside the manifest directory.
Missing files, duplicate selections, absolute paths, paths that escape the
configuration directory, unknown keys, unknown agents, unknown hosts, and
duplicate selections across any layer are errors.

`host_agents` is optional and is available in schema version 3. Its host and
agent names must already be declared in `hosts` and `agents`; its fragments
are selected only for that exact host-agent pair. Schema version 2 manifests
remain supported with byte-identical output and the original three-layer
order. Adding `host_agents` to a schema version 2 manifest is an explicit
upgrade error; change `schema_version` to `3` first.

A runnable sanitized configuration is available in
[`examples/agent-config`](examples/agent-config).

## Commands

Render to standard output without changing files:

```bash
agent-bootstrap render \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --agent codex
```

Preview installation status and a diff:

```bash
agent-bootstrap install \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --agent codex \
  --dry-run \
  --diff
```

Install atomically to the selected agent target:

```bash
agent-bootstrap install \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --agent pi
```

The installer refuses to replace an existing file that lacks its generated
marker. Review the diff and pass `--force` only when deliberately adopting an
existing target.

Check for drift:

```bash
agent-bootstrap check \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --agent codex
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

Generated files contain a stable header with the selected host, agent,
home-relative target, and ordered manifest-relative source paths. Output uses
UTF-8, Unix newlines, one blank line between fragments, and one final newline.
It contains no timestamps or absolute configuration paths, so unchanged inputs
produce byte-identical output.

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
