"""Global instruction installation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_bootstrap.install import InstallError, inspect_target, install_target
from agent_bootstrap.render import GENERATED_MARKER


def _rendered(body: str = "content") -> str:
    return f"<!--\n{GENERATED_MARKER}\n-->\n\n{body}\n"


def test_installs_and_checks_generated_target(tmp_path: Path) -> None:
    state = inspect_target(_rendered(), home=tmp_path)

    assert install_target(state)
    target = tmp_path / ".codex/AGENTS.md"
    assert target.read_text(encoding="utf-8") == _rendered()
    assert target.stat().st_mode & 0o777 == 0o600
    assert not inspect_target(_rendered(), home=tmp_path).changed


def test_refuses_unmanaged_target_without_force(tmp_path: Path) -> None:
    target = tmp_path / ".codex/AGENTS.md"
    target.parent.mkdir()
    target.write_text("hand-written\n", encoding="utf-8")
    state = inspect_target(_rendered(), home=tmp_path)

    with pytest.raises(InstallError, match="refusing to replace unmanaged file"):
        install_target(state)

    assert target.read_text(encoding="utf-8") == "hand-written\n"


def test_force_replaces_unmanaged_target(tmp_path: Path) -> None:
    target = tmp_path / ".codex/AGENTS.md"
    target.parent.mkdir()
    target.write_text("hand-written\n", encoding="utf-8")

    assert install_target(inspect_target(_rendered(), home=tmp_path), force=True)
    assert target.read_text(encoding="utf-8") == _rendered()


def test_diff_describes_missing_target(tmp_path: Path) -> None:
    state = inspect_target(_rendered(), home=tmp_path)

    diff = state.diff()

    assert f"--- {state.path}" in diff
    assert f"+++ {state.path} (rendered)" in diff
    assert f"+{GENERATED_MARKER}" in diff
