"""Manifest-driven batch selection, planning, and application."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from agent_bootstrap.agent import Agent, target_for
from agent_bootstrap.config import Manifest, ManifestError
from agent_bootstrap.install import (
    InstallError,
    TargetState,
    inspect_target,
    install_target,
    is_unmanaged,
)
from agent_bootstrap.render import render_instructions


@dataclass(frozen=True)
class BatchTarget:
    """One selected host-agent pair."""

    host: str
    agent: Agent


def select_targets(
    manifest: Manifest, host: str | None, agent: Agent | None
) -> tuple[BatchTarget, ...]:
    """Select declared host-agent pairs, ordered by host name then agent name.

    ``host`` and ``agent`` each narrow one dimension to a declared member;
    ``None`` selects every declared host or agent. Eligibility comes only from
    the ``hosts`` and ``agents`` tables, never from ``host_agents`` overrides.
    """
    hosts = _selected_hosts(manifest, host)
    agents = _selected_agents(manifest, agent)
    return tuple(BatchTarget(host_name, agent_name) for host_name in hosts for agent_name in agents)


def _selected_hosts(manifest: Manifest, host: str | None) -> tuple[str, ...]:
    if host is None:
        return tuple(sorted(manifest.hosts))
    if host not in manifest.hosts:
        choices = ", ".join(sorted(manifest.hosts)) or "none"
        raise ManifestError(f"unknown host {host!r}; configured hosts: {choices}")
    return (host,)


def _selected_agents(manifest: Manifest, agent: Agent | None) -> tuple[Agent, ...]:
    if agent is None:
        return tuple(sorted(manifest.agents, key=lambda item: item.value))
    if agent not in manifest.agents:
        choices = ", ".join(
            item.value for item in sorted(manifest.agents, key=lambda item: item.value)
        )
        raise ManifestError(
            f"agent {agent.value!r} is not configured; configured agents: {choices or 'none'}"
        )
    return (agent,)


class ValidateStatus(StrEnum):
    """Rendering validation outcome for one target."""

    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class ValidateResult:
    """Rendering validation result for one target."""

    target: BatchTarget
    status: ValidateStatus
    detail: str = ""


def validate_targets(
    manifest: Manifest, targets: Sequence[BatchTarget]
) -> tuple[ValidateResult, ...]:
    """Render every target and collect validity without touching installations."""
    results: list[ValidateResult] = []
    for target in targets:
        try:
            render_instructions(manifest, target.host, target.agent)
        except (ManifestError, OSError) as error:
            results.append(ValidateResult(target, ValidateStatus.INVALID, str(error)))
        else:
            results.append(ValidateResult(target, ValidateStatus.VALID))
    return tuple(results)


@dataclass(frozen=True)
class PlannedTarget:
    """Rendered and inspected state for one target, or its collection error."""

    target: BatchTarget
    destination: Path
    state: TargetState | None
    error: str | None


def plan_targets(
    targets: Sequence[BatchTarget], manifest: Manifest, *, home: Path | None = None
) -> tuple[PlannedTarget, ...]:
    """Render and inspect every target, collecting errors without writing."""
    base = Path.home() if home is None else home
    planned: list[PlannedTarget] = []
    for target in targets:
        destination = base / target_for(target.agent)
        state: TargetState | None = None
        error: str | None = None
        try:
            content = render_instructions(manifest, target.host, target.agent)
            state = inspect_target(content, target.agent, home=home)
        except (ManifestError, InstallError, OSError) as caught:
            error = str(caught)
        planned.append(PlannedTarget(target, destination, state, error))
    return tuple(planned)


class CheckStatus(StrEnum):
    """Installation drift outcome for one target."""

    CURRENT = "current"
    MISSING = "missing"
    STALE = "stale"
    UNMANAGED = "unmanaged"
    ERROR = "error"


@dataclass(frozen=True)
class CheckResult:
    """Drift classification for one planned target."""

    target: BatchTarget
    destination: Path
    status: CheckStatus
    detail: str = ""


def check_targets(planned: Sequence[PlannedTarget]) -> tuple[CheckResult, ...]:
    """Classify every planned target, keeping results after a target failure."""
    results: list[CheckResult] = []
    for item in planned:
        state = item.state
        if item.error is not None or state is None:
            detail = item.error if item.error is not None else "target could not be planned"
            results.append(CheckResult(item.target, item.destination, CheckStatus.ERROR, detail))
            continue
        if state.current is None:
            status, detail = CheckStatus.MISSING, ""
        elif is_unmanaged(state):
            status, detail = CheckStatus.UNMANAGED, _unmanaged_detail(state)
        elif state.changed:
            status, detail = CheckStatus.STALE, ""
        else:
            status, detail = CheckStatus.CURRENT, ""
        results.append(CheckResult(item.target, item.destination, status, detail))
    return tuple(results)


class PreviewStatus(StrEnum):
    """Dry-run outcome for one target."""

    CURRENT = "current"
    WOULD_UPDATE = "would-update"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass(frozen=True)
class PreviewResult:
    """Dry-run classification for one planned target."""

    target: BatchTarget
    destination: Path
    status: PreviewStatus
    detail: str = ""


def preview_targets(planned: Sequence[PlannedTarget]) -> tuple[PreviewResult, ...]:
    """Classify a dry run over the same plan an application would use."""
    results: list[PreviewResult] = []
    for item in planned:
        state = item.state
        if item.error is not None or state is None:
            detail = item.error if item.error is not None else "target could not be planned"
            results.append(
                PreviewResult(item.target, item.destination, PreviewStatus.ERROR, detail)
            )
        elif is_unmanaged(state):
            results.append(
                PreviewResult(
                    item.target,
                    item.destination,
                    PreviewStatus.BLOCKED,
                    _unmanaged_detail(state),
                )
            )
        elif state.changed:
            results.append(PreviewResult(item.target, item.destination, PreviewStatus.WOULD_UPDATE))
        else:
            results.append(PreviewResult(item.target, item.destination, PreviewStatus.CURRENT))
    return tuple(results)


class ApplyStatus(StrEnum):
    """Application outcome for one target."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    UNATTEMPTED = "unattempted"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ApplyResult:
    """Application outcome for one planned target."""

    target: BatchTarget
    destination: Path
    status: ApplyStatus
    detail: str = ""


def apply_targets(planned: Sequence[PlannedTarget]) -> tuple[ApplyResult, ...]:
    """Apply planned installations sequentially, stopping at the first failure.

    Any planning error or unmanaged target blocks every write. A failed write
    stops the run while retaining completed updates.
    """
    blocked = any(
        item.error is not None or (item.state is not None and is_unmanaged(item.state))
        for item in planned
    )
    if blocked:
        return _blocked_results(planned)
    results: list[ApplyResult] = []
    stopped = False
    for item in planned:
        state = item.state
        if stopped:
            results.append(ApplyResult(item.target, item.destination, ApplyStatus.UNATTEMPTED))
            continue
        if state is None:
            results.append(
                ApplyResult(
                    item.target,
                    item.destination,
                    ApplyStatus.FAILED,
                    item.error or "target could not be planned",
                )
            )
            stopped = True
            continue
        if not state.changed:
            results.append(ApplyResult(item.target, item.destination, ApplyStatus.UNCHANGED))
            continue
        try:
            install_target(state)
        except (InstallError, OSError) as error:
            results.append(
                ApplyResult(item.target, item.destination, ApplyStatus.FAILED, str(error))
            )
            stopped = True
        else:
            results.append(ApplyResult(item.target, item.destination, ApplyStatus.UPDATED))
    return tuple(results)


def _blocked_results(planned: Sequence[PlannedTarget]) -> tuple[ApplyResult, ...]:
    results: list[ApplyResult] = []
    for item in planned:
        state = item.state
        if item.error is not None:
            detail = item.error
        elif state is not None and is_unmanaged(state):
            detail = _unmanaged_detail(state)
        else:
            detail = "blocked by another target's failed preflight"
        results.append(ApplyResult(item.target, item.destination, ApplyStatus.BLOCKED, detail))
    return tuple(results)


def _unmanaged_detail(state: TargetState) -> str:
    return (
        f"refusing to replace unmanaged file: {state.path}; "
        "adopt it with a single-agent --force install"
    )
