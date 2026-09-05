"""Safe publication and drift checking for global agent instructions."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from agent_bootstrap.agent import Agent, target_for
from agent_bootstrap.render import GENERATED_MARKER


class InstallError(RuntimeError):
    """Raised when an instruction file cannot be safely installed."""


@dataclass(frozen=True)
class TargetState:
    """Current comparison between rendered and installed instructions."""

    path: Path
    current: str | None
    rendered: str

    @property
    def changed(self) -> bool:
        """Whether installation would alter the target."""
        return self.current != self.rendered

    def diff(self) -> str:
        """Return a unified diff from the current target to rendered content."""
        before = "" if self.current is None else self.current
        return "".join(
            unified_diff(
                before.splitlines(keepends=True),
                self.rendered.splitlines(keepends=True),
                fromfile=str(self.path),
                tofile=f"{self.path} (rendered)",
            )
        )


def inspect_target(rendered: str, agent: Agent, *, home: Path | None = None) -> TargetState:
    """Read the current global instruction target for an agent."""
    base = Path.home() if home is None else home
    target = base / target_for(agent)
    try:
        current = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = None
    except UnicodeDecodeError as error:
        raise InstallError(f"existing target is not valid UTF-8: {target}") from error
    return TargetState(path=target, current=current, rendered=rendered)


def is_unmanaged(state: TargetState) -> bool:
    """Return whether an existing target lacks the generated marker."""
    return state.current is not None and GENERATED_MARKER not in state.current


def install_target(state: TargetState, *, force: bool = False) -> bool:
    """Atomically install rendered instructions and return whether they changed."""
    if not state.changed:
        return False
    if is_unmanaged(state) and not force:
        raise InstallError(
            f"refusing to replace unmanaged file: {state.path}; rerun with --force after review"
        )

    state.path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=state.path.parent,
            prefix=f".{state.path.name}.",
            delete=False,
        ) as stream:
            stream.write(state.rendered)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_path = Path(stream.name)
        temporary_path.chmod(0o600)
        os.replace(temporary_path, state.path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return True
