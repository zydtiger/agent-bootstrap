"""Typer command-line interface for agent-bootstrap."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from agent_bootstrap.agent import Agent
from agent_bootstrap.config import ManifestError, load_manifest
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


@app.command()
def render(manifest: ManifestOption, host: HostOption, agent: AgentOption) -> None:
    """Render instructions to standard output without changing files."""
    content = _render(manifest, host, agent)
    typer.echo(content, nl=False)


@app.command()
def install(
    manifest: ManifestOption,
    host: HostOption,
    agent: AgentOption,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report changes without writing the target.")
    ] = False,
    show_diff: Annotated[
        bool, typer.Option("--diff", help="Print the prospective unified diff.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Allow replacement of an unmanaged target.")
    ] = False,
) -> None:
    """Install rendered instructions as the selected global agent file."""
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
    except InstallError as error:
        _fail(str(error))
    typer.echo(f"Updated {state.path}" if changed else f"Up to date: {state.path}")


@app.command()
def check(manifest: ManifestOption, host: HostOption, agent: AgentOption) -> None:
    """Check whether the selected global agent file matches the manifest."""
    content = _render(manifest, host, agent)
    try:
        state = inspect_target(content, agent)
    except InstallError as error:
        _fail(str(error))
    if state.changed:
        typer.echo(f"Stale or missing: {state.path}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Up to date: {state.path}")


def _render(manifest_path: Path, host: str, agent: Agent) -> str:
    try:
        return render_instructions(load_manifest(manifest_path), host, agent)
    except ManifestError as error:
        _fail(str(error))


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(2)
