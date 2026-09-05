"""Batch selection, planning, and application tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

import agent_bootstrap.batch as batch
from agent_bootstrap.agent import Agent, target_for
from agent_bootstrap.config import ManifestError, load_manifest
from agent_bootstrap.install import TargetState, inspect_target, install_target
from agent_bootstrap.render import GENERATED_MARKER, render_instructions

FRAGMENTS: dict[str, str] = {
    "shared.md": "# Shared\n",
    "codex.md": "# Codex\n",
    "pi.md": "# Pi\n",
    "zcode.md": "# Zcode\n",
    "claude.md": "# Claude\n",
    "cursor.md": "# Cursor\n",
    "workstation.md": "# Workstation\n",
    "laptop.md": "# Laptop\n",
    "workstation-codex.md": "# Workstation Codex\n",
}

MATRIX_MANIFEST = """
schema_version = 3
fragments = ["shared.md"]

[agents.pi]
fragments = ["pi.md"]

[agents.zcode]
fragments = ["zcode.md"]

[agents.claude]
fragments = ["claude.md"]

[agents.cursor]
fragments = ["cursor.md"]

[agents.codex]
fragments = ["codex.md"]

[hosts.workstation]
fragments = ["workstation.md"]

[hosts.laptop]
fragments = ["laptop.md"]

[host_agents.workstation.codex]
fragments = ["workstation-codex.md"]
"""

FOUR_AGENT_MANIFEST = """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["codex.md"]

[agents.pi]
fragments = ["pi.md"]

[agents.zcode]
fragments = ["zcode.md"]

[agents.claude]
fragments = ["claude.md"]

[hosts.workstation]
fragments = ["workstation.md"]
"""

TWO_AGENT_MANIFEST = """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["codex.md"]

[agents.pi]
fragments = ["pi.md"]

[hosts.workstation]
fragments = ["workstation.md"]
"""


def _config(root: Path, manifest: str, fragments: dict[str, str | bytes] | None = None) -> Path:
    for name, content in {**FRAGMENTS, **(fragments or {})}.items():
        path = root / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    manifest_path = root / "manifest.toml"
    manifest_path.write_text(manifest, encoding="utf-8")
    return manifest_path


def _rendered(manifest_path: Path, agent: Agent, host: str = "workstation") -> str:
    return render_instructions(load_manifest(manifest_path), host, agent)


def _install_current(manifest_path: Path, agent: Agent, home: Path) -> None:
    install_target(inspect_target(_rendered(manifest_path, agent), agent, home=home))


def _planned(
    manifest_path: Path, home: Path, host: str = "workstation"
) -> tuple[batch.PlannedTarget, ...]:
    manifest = load_manifest(manifest_path)
    return batch.plan_targets(batch.select_targets(manifest, host, None), manifest, home=home)


def test_select_targets_defaults_to_all_declared_pairs_sorted(tmp_path: Path) -> None:
    manifest = load_manifest(_config(tmp_path, MATRIX_MANIFEST))

    selected = batch.select_targets(manifest, None, None)

    assert [(item.host, item.agent) for item in selected] == [
        ("laptop", Agent.CLAUDE),
        ("laptop", Agent.CODEX),
        ("laptop", Agent.CURSOR),
        ("laptop", Agent.PI),
        ("laptop", Agent.ZCODE),
        ("workstation", Agent.CLAUDE),
        ("workstation", Agent.CODEX),
        ("workstation", Agent.CURSOR),
        ("workstation", Agent.PI),
        ("workstation", Agent.ZCODE),
    ]


def test_select_targets_narrows_each_dimension(tmp_path: Path) -> None:
    manifest = load_manifest(_config(tmp_path, MATRIX_MANIFEST))

    by_host = batch.select_targets(manifest, "workstation", None)
    by_agent = batch.select_targets(manifest, None, Agent.PI)
    single = batch.select_targets(manifest, "workstation", Agent.PI)

    assert [(item.host, item.agent) for item in by_host] == [
        ("workstation", Agent.CLAUDE),
        ("workstation", Agent.CODEX),
        ("workstation", Agent.CURSOR),
        ("workstation", Agent.PI),
        ("workstation", Agent.ZCODE),
    ]
    assert [(item.host, item.agent) for item in by_agent] == [
        ("laptop", Agent.PI),
        ("workstation", Agent.PI),
    ]
    assert [(item.host, item.agent) for item in single] == [("workstation", Agent.PI)]


def test_select_targets_rejects_unknown_host_or_agent(tmp_path: Path) -> None:
    manifest = load_manifest(_config(tmp_path, TWO_AGENT_MANIFEST))

    with pytest.raises(ManifestError, match="unknown host 'server'"):
        batch.select_targets(manifest, "server", None)
    with pytest.raises(ManifestError, match="agent 'zcode' is not configured"):
        batch.select_targets(manifest, None, Agent.ZCODE)


@pytest.mark.parametrize(
    ("fragments", "manifest", "invalid"),
    [
        (
            {"claude.md": "\n  \n"},
            MATRIX_MANIFEST,
            [("laptop", Agent.CLAUDE), ("workstation", Agent.CLAUDE)],
        ),
        (
            {"workstation-codex.md": b"\xff"},
            MATRIX_MANIFEST,
            [("workstation", Agent.CODEX)],
        ),
        (
            None,
            MATRIX_MANIFEST.replace(
                '[host_agents.workstation.codex]\nfragments = ["workstation-codex.md"]',
                '[host_agents.workstation.pi]\nfragments = ["shared.md"]',
            ),
            [("workstation", Agent.PI)],
        ),
    ],
)
def test_validate_targets_collects_invalid_renderings(
    tmp_path: Path,
    fragments: dict[str, str | bytes] | None,
    manifest: str,
    invalid: list[tuple[str, Agent]],
) -> None:
    loaded = load_manifest(_config(tmp_path, manifest, fragments))

    results = batch.validate_targets(loaded, batch.select_targets(loaded, None, None))

    assert [(item.target.host, item.target.agent) for item in results if item.detail] == invalid
    assert len(results) == 10
    assert all(item.status is batch.ValidateStatus.VALID for item in results if item.detail == "")
    assert all(item.status is batch.ValidateStatus.INVALID for item in results if item.detail)


def test_plan_targets_reads_without_creating_destinations(tmp_path: Path) -> None:
    manifest_path = _config(tmp_path, TWO_AGENT_MANIFEST)
    home = tmp_path / "home"
    home.mkdir()

    planned = _planned(manifest_path, home)

    assert [item.destination for item in planned] == [
        home / ".codex/AGENTS.md",
        home / ".pi/agent/AGENTS.md",
    ]
    assert all(item.error is None for item in planned)
    assert all(item.state is not None and item.state.current is None for item in planned)
    assert list(home.iterdir()) == []


def test_check_targets_classifies_each_state(tmp_path: Path) -> None:
    manifest_path = _config(tmp_path, FOUR_AGENT_MANIFEST)
    home = tmp_path / "home"
    home.mkdir()
    _install_current(manifest_path, Agent.CODEX, home)
    (home / ".zcode").mkdir()
    (home / ".zcode/AGENTS.md").write_text(f"<!--\n{GENERATED_MARKER}\n-->\n\nold\n", "utf-8")
    (home / ".claude").mkdir()
    (home / ".claude/CLAUDE.md").write_text("hand-written\n", "utf-8")

    results = batch.check_targets(_planned(manifest_path, home))

    assert [(item.target.agent, item.status) for item in results] == [
        (Agent.CLAUDE, batch.CheckStatus.UNMANAGED),
        (Agent.CODEX, batch.CheckStatus.CURRENT),
        (Agent.PI, batch.CheckStatus.MISSING),
        (Agent.ZCODE, batch.CheckStatus.STALE),
    ]
    unmanaged = next(item for item in results if item.status is batch.CheckStatus.UNMANAGED)
    assert "refusing to replace unmanaged file" in unmanaged.detail


def test_check_targets_collects_results_after_render_error(tmp_path: Path) -> None:
    manifest_path = _config(tmp_path, FOUR_AGENT_MANIFEST, {"claude.md": b"\xff"})
    home = tmp_path / "home"
    home.mkdir()
    _install_current(manifest_path, Agent.CODEX, home)

    results = batch.check_targets(_planned(manifest_path, home))

    assert [(item.target.agent, item.status) for item in results] == [
        (Agent.CLAUDE, batch.CheckStatus.ERROR),
        (Agent.CODEX, batch.CheckStatus.CURRENT),
        (Agent.PI, batch.CheckStatus.MISSING),
        (Agent.ZCODE, batch.CheckStatus.MISSING),
    ]
    error = next(item for item in results if item.status is batch.CheckStatus.ERROR)
    assert "not valid UTF-8" in error.detail


def test_preview_targets_labels_current_would_update_blocked_and_error(
    tmp_path: Path,
) -> None:
    manifest_path = _config(tmp_path, FOUR_AGENT_MANIFEST)
    home = tmp_path / "home"
    home.mkdir()
    _install_current(manifest_path, Agent.CODEX, home)
    (home / ".claude").mkdir()
    (home / ".claude/CLAUDE.md").write_text("hand-written\n", "utf-8")

    results = batch.preview_targets(_planned(manifest_path, home))

    assert [(item.target.agent, item.status) for item in results] == [
        (Agent.CLAUDE, batch.PreviewStatus.BLOCKED),
        (Agent.CODEX, batch.PreviewStatus.CURRENT),
        (Agent.PI, batch.PreviewStatus.WOULD_UPDATE),
        (Agent.ZCODE, batch.PreviewStatus.WOULD_UPDATE),
    ]


def test_apply_targets_blocked_by_unmanaged_writes_nothing(tmp_path: Path) -> None:
    manifest_path = _config(tmp_path, FOUR_AGENT_MANIFEST)
    home = tmp_path / "home"
    home.mkdir()
    _install_current(manifest_path, Agent.CODEX, home)
    current = home / ".codex/AGENTS.md"
    os.utime(current, ns=(1_000_000, 1_000_000))
    (home / ".claude").mkdir()
    unmanaged = home / ".claude/CLAUDE.md"
    unmanaged.write_text("hand-written\n", "utf-8")

    results = batch.apply_targets(_planned(manifest_path, home))

    assert all(item.status is batch.ApplyStatus.BLOCKED for item in results)
    assert unmanaged.read_text("utf-8") == "hand-written\n"
    assert current.stat().st_mtime_ns == 1_000_000
    assert not (home / ".pi").exists()
    assert not (home / ".zcode").exists()


def test_apply_targets_updates_only_changed_targets(tmp_path: Path) -> None:
    manifest_path = _config(tmp_path, FOUR_AGENT_MANIFEST)
    home = tmp_path / "home"
    home.mkdir()
    _install_current(manifest_path, Agent.CODEX, home)
    current = home / ".codex/AGENTS.md"
    os.utime(current, ns=(1_000_000, 1_000_000))

    results = batch.apply_targets(_planned(manifest_path, home))

    assert [(item.target.agent, item.status) for item in results] == [
        (Agent.CLAUDE, batch.ApplyStatus.UPDATED),
        (Agent.CODEX, batch.ApplyStatus.UNCHANGED),
        (Agent.PI, batch.ApplyStatus.UPDATED),
        (Agent.ZCODE, batch.ApplyStatus.UPDATED),
    ]
    assert current.stat().st_mtime_ns == 1_000_000
    for agent in (Agent.CLAUDE, Agent.PI, Agent.ZCODE):
        target = home / target_for(agent)
        assert target.read_text("utf-8") == _rendered(manifest_path, agent)
        assert target.stat().st_mode & 0o777 == 0o600


def test_apply_targets_stops_at_failure_and_rerun_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = _config(tmp_path, FOUR_AGENT_MANIFEST)
    home = tmp_path / "home"
    home.mkdir()
    real_install: Callable[[TargetState], bool] = install_target

    def failing_install(state: TargetState) -> bool:
        if "Agent: pi" in state.rendered:
            raise OSError("simulated write failure")
        return real_install(state)

    planned = _planned(manifest_path, home)
    monkeypatch.setattr(batch, "install_target", failing_install)
    failed = batch.apply_targets(planned)

    assert [(item.target.agent, item.status) for item in failed] == [
        (Agent.CLAUDE, batch.ApplyStatus.UPDATED),
        (Agent.CODEX, batch.ApplyStatus.UPDATED),
        (Agent.PI, batch.ApplyStatus.FAILED),
        (Agent.ZCODE, batch.ApplyStatus.UNATTEMPTED),
    ]
    assert next(item for item in failed if item.status is batch.ApplyStatus.FAILED).detail
    assert not (home / ".pi/agent/AGENTS.md").exists()
    assert not (home / ".zcode/AGENTS.md").exists()

    monkeypatch.undo()
    rerun = batch.apply_targets(_planned(manifest_path, home))

    assert [(item.target.agent, item.status) for item in rerun] == [
        (Agent.CLAUDE, batch.ApplyStatus.UNCHANGED),
        (Agent.CODEX, batch.ApplyStatus.UNCHANGED),
        (Agent.PI, batch.ApplyStatus.UPDATED),
        (Agent.ZCODE, batch.ApplyStatus.UPDATED),
    ]
    for agent in (Agent.CLAUDE, Agent.CODEX, Agent.PI, Agent.ZCODE):
        assert (home / target_for(agent)).read_text("utf-8") == _rendered(manifest_path, agent)
