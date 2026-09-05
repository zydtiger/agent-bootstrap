"""Typer command-line interface for agent-bootstrap."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from agent_bootstrap import batch
from agent_bootstrap.agent import Agent
from agent_bootstrap.config import Manifest, ManifestError, load_manifest
from agent_bootstrap.install import InstallError, inspect_target, install_target
from agent_bootstrap.render import render_instructions

app = typer.Typer(
    help="Render and install layered global agent instructions.",
    no_args_is_help=True,
    add_completion=False,
)

ManifestOption = Annotated[
    Path,
    typer.Option(
        "--manifest",
        "-m",
        help="Path to the instruction manifest.",
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
]
HostOption = Annotated[str, typer.Option("--host", "-H", help="Configured host name.")]
AgentOption = Annotated[Agent, typer.Option("--agent", "-A", help="Instruction agent to target.")]
OptionalHostOption = Annotated[
    str | None,
    typer.Option("--host", "-H", help="Configured host name."),
]
OptionalAgentOption = Annotated[
    Agent | None,
    typer.Option("--agent", "-A", help="Instruction agent to target."),
]
AllAgentsOption = Annotated[
    bool,
    typer.Option("--all-agents", help="Select every agent declared in the manifest."),
]


@app.command()
def render(manifest: ManifestOption, host: HostOption, agent: AgentOption) -> None:
    """Render instructions to standard output without changing files."""
    content = _render(manifest, host, agent)
    typer.echo(content, nl=False)


@app.command()
def validate(
    manifest: ManifestOption,
    host: OptionalHostOption = None,
    agent: OptionalAgentOption = None,
) -> None:
    """Validate rendering for every selected manifest target."""
    loaded = _load(manifest)
    results = batch.validate_targets(loaded, _select(loaded, host, agent))
    statuses: list[str] = []
    for result in results:
        statuses.append(result.status.value)
        typer.echo(f"{_label(result.target)}: {result.status.value}")
        if result.detail:
            typer.echo(f"  {result.detail}", err=True)
    typer.echo(_counts(statuses))
    if batch.ValidateStatus.INVALID.value in statuses:
        raise typer.Exit(2)


@app.command()
def install(
    manifest: ManifestOption,
    host: HostOption,
    agent: OptionalAgentOption = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report changes without writing the target.")
    ] = False,
    show_diff: Annotated[
        bool, typer.Option("--diff", help="Print the prospective unified diff.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Allow replacement of an unmanaged target.")
    ] = False,
    all_agents: AllAgentsOption = False,
) -> None:
    """Install rendered instructions as the selected global agent file."""
    if all_agents:
        if agent is not None:
            _fail("specify either --agent or --all-agents, not both")
        if force:
            _fail("--force requires an explicit --agent")
        _install_all_agents(manifest, host, dry_run=dry_run, show_diff=show_diff)
        return
    if agent is None:
        _fail("specify --agent or --all-agents")
    content = _render(manifest, host, agent)
    try:
        state = inspect_target(content, agent)
        typer.echo(f"Target: {state.path}")
        if show_diff and state.changed:
            typer.echo(state.diff(), nl=False)
        if dry_run:
            message = f"Would update {state.path}" if state.changed else f"Up to date: {state.path}"
            typer.echo(message)
            return
        changed = install_target(state, force=force)
    except (InstallError, OSError) as error:
        _fail(str(error))
    typer.echo(f"Updated {state.path}" if changed else f"Up to date: {state.path}")


@app.command()
def check(
    manifest: ManifestOption,
    host: HostOption,
    agent: OptionalAgentOption = None,
    all_agents: AllAgentsOption = False,
) -> None:
    """Check whether the selected global agent file matches the manifest."""
    if all_agents:
        if agent is not None:
            _fail("specify either --agent or --all-agents, not both")
        _check_all_agents(manifest, host)
        return
    if agent is None:
        _fail("specify --agent or --all-agents")
    content = _render(manifest, host, agent)
    try:
        state = inspect_target(content, agent)
    except (InstallError, OSError) as error:
        _fail(str(error))
    if state.changed:
        typer.echo(f"Stale or missing: {state.path}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Up to date: {state.path}")


def _check_all_agents(manifest_path: Path, host: str) -> None:
    loaded = _load(manifest_path)
    results = batch.check_targets(batch.plan_targets(_select(loaded, host, None), loaded))
    statuses: list[str] = []
    for result in results:
        statuses.append(result.status.value)
        typer.echo(f"{_label(result.target)}: {result.status.value} {result.destination}")
        if result.detail:
            typer.echo(f"  {result.detail}", err=True)
    typer.echo(_counts(statuses))
    if batch.CheckStatus.ERROR.value in statuses:
        raise typer.Exit(2)
    if any(status != batch.CheckStatus.CURRENT.value for status in statuses):
        raise typer.Exit(1)


def _install_all_agents(manifest_path: Path, host: str, *, dry_run: bool, show_diff: bool) -> None:
    loaded = _load(manifest_path)
    planned = batch.plan_targets(_select(loaded, host, None), loaded)
    if dry_run:
        _preview_all_agents(planned, show_diff=show_diff)
        return
    _apply_all_agents(planned)


def _preview_all_agents(planned: Sequence[batch.PlannedTarget], *, show_diff: bool) -> None:
    results = batch.preview_targets(planned)
    statuses: list[str] = []
    for item, result in zip(planned, results, strict=True):
        statuses.append(result.status.value)
        typer.echo(f"{_label(item.target)}: {result.status.value} {item.destination}")
        if result.detail:
            typer.echo(f"  {result.detail}", err=True)
        if show_diff and item.state is not None and item.state.changed:
            typer.echo(f"Diff {_label(item.target)}:")
            typer.echo(item.state.diff(), nl=False)
    typer.echo(_counts(statuses))
    if batch.PreviewStatus.ERROR.value in statuses:
        raise typer.Exit(2)


def _apply_all_agents(planned: Sequence[batch.PlannedTarget]) -> None:
    results = batch.apply_targets(planned)
    statuses: list[str] = []
    for result in results:
        statuses.append(result.status.value)
        typer.echo(f"{_label(result.target)}: {result.status.value} {result.destination}")
        if result.detail:
            typer.echo(f"  {result.detail}", err=True)
    typer.echo(_counts(statuses))
    if any(
        status in (batch.ApplyStatus.FAILED.value, batch.ApplyStatus.BLOCKED.value)
        for status in statuses
    ):
        raise typer.Exit(2)


def _load(manifest_path: Path) -> Manifest:
    try:
        return load_manifest(manifest_path)
    except (ManifestError, OSError) as error:
        _fail(str(error))


def _select(
    loaded: Manifest, host: str | None, agent: Agent | None
) -> tuple[batch.BatchTarget, ...]:
    try:
        return batch.select_targets(loaded, host, agent)
    except ManifestError as error:
        _fail(str(error))


def _render(manifest_path: Path, host: str, agent: Agent) -> str:
    try:
        return render_instructions(load_manifest(manifest_path), host, agent)
    except (ManifestError, OSError) as error:
        _fail(str(error))


def _label(target: batch.BatchTarget) -> str:
    return f"{target.host} {target.agent.value}"


def _counts(statuses: Sequence[str]) -> str:
    total = len(statuses)
    parts = [f"{statuses.count(status)} {status}" for status in dict.fromkeys(statuses)]
    return f"{total} target(s): " + ", ".join(parts)


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(2)
