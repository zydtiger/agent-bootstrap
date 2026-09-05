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

Each rendering selects both a configured host and an agent. The agent
determines both the agent-specific fragments and the global installation
target:

- `codex`: `~/.codex/AGENTS.md`
- `pi`: `~/.pi/agent/AGENTS.md`
- `zcode`: `~/.zcode/AGENTS.md`
- `claude`: `~/.claude/CLAUDE.md`
- `cursor`: `~/.cursor/rules/global.mdc`

Cursor's target is a machine-local user rule that does not sync through a Cursor
account. Its generated output begins with `alwaysApply: true` YAML frontmatter
so Cursor includes the rule in every Agent conversation. The other targets
retain their existing plain-Markdown output.

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

[agents.cursor]
fragments = [
  "preferences/cursor.md",
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

Validate the rendering matrix:

```bash
agent-bootstrap validate \
  --manifest ~/agent-config/manifest.toml
```

`validate` renders every declared host-agent pair without reading or writing
installations. `--host` or `--agent` narrows one dimension to a declared
member; unknown selectors are errors.

Check, preview, or install every agent declared for one host:

```bash
agent-bootstrap check \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --all-agents

agent-bootstrap install \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --all-agents \
  --dry-run \
  --diff

agent-bootstrap install \
  --manifest ~/agent-config/manifest.toml \
  --host workstation \
  --all-agents
```

`check` and `install` require exactly one explicit host and exactly one of
`--agent` or `--all-agents`. Batch selection uses only the agents declared in
the manifest, ordered lexicographically by host name and then agent
identifier, and `host_agents` overrides never affect eligibility. `--force`
stays reserved for explicit single-agent installation and is rejected with
`--all-agents`.

Batch commands print one line per target followed by a counts summary, with
diagnostics on standard error. Batch `check` reports each target as
`current`, `missing`, `stale`, `unmanaged`, or `error`, and keeps collecting
results after a target-level failure. A dry-run preview reports `current`,
`would-update`, or `blocked`, and `--diff` shows a labeled diff for every
changed readable target, including unmanaged files.

Batch installation renders every selected target and inspects every
destination before writing: any rendering, inspection, or unmanaged-file
blocker prevents all writes, so an unmanaged target must be adopted
explicitly with a single-agent `install --force`. Once the preflight passes,
changed targets are applied sequentially with the same atomic replacement and
user-only permissions as single-target installation, and unchanged files are
left untouched. A failed write stops the run while retaining completed
updates; the report identifies updated, unchanged, failed, and unattempted
targets, and rerunning after the failure skips current targets and completes
the remaining work.

## Exit status

| Command | Exit 0 | Exit 1 | Exit 2 |
| --- | --- | --- | --- |
| `render` | Output written. | Unused. | Usage, manifest, rendering, or I/O error. |
| `validate` | All selected renderings are valid. | Unused. | Usage, manifest, rendering, or I/O error. |
| `check` | All selected targets are current. | At least one missing, stale, or unmanaged target. | Usage, manifest, rendering, or inspection error. |
| `install --dry-run` | Preview completed, possibly with labeled ownership blockers. | Unused. | Usage, manifest, rendering, or inspection error. |
| `install` | Installation completed, including unchanged targets. | Unused. | Preflight blocked or installation failed. |

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
uv sync --locked
uv tool install prek   # once per machine
prek install           # once per clone
```

Run the full, targeted, or documentation-only validation defined in
`AGENTS.md`; that file points to the same hook stages CI executes. Build package
changes with `uv build` after validation.
