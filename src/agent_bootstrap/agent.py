"""Supported instruction agents and their global targets."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path


class Agent(StrEnum):
    """An instruction consumer supported by agent-bootstrap."""

    CODEX = "codex"
    PI = "pi"
    ZCODE = "zcode"
    CLAUDE = "claude"
    CURSOR = "cursor"


AGENT_TARGETS: dict[Agent, Path] = {
    Agent.CODEX: Path(".codex/AGENTS.md"),
    Agent.PI: Path(".pi/agent/AGENTS.md"),
    Agent.ZCODE: Path(".zcode/AGENTS.md"),
    Agent.CLAUDE: Path(".claude/CLAUDE.md"),
    Agent.CURSOR: Path(".cursor/rules/global.mdc"),
}


def target_for(agent: Agent) -> Path:
    """Return the global target path relative to the user's home directory."""
    return AGENT_TARGETS[agent]


def display_target(agent: Agent) -> str:
    """Return a stable home-relative display path for an agent target."""
    return f"~/{target_for(agent).as_posix()}"
