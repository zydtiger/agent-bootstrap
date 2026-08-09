"""Manifest parsing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_bootstrap.agent import Agent
from agent_bootstrap.config import ManifestError, load_manifest


def _write_config(root: Path, manifest: str) -> Path:
    (root / "shared.md").write_text("shared\n", encoding="utf-8")
    (root / "agent.md").write_text("agent\n", encoding="utf-8")
    (root / "host.md").write_text("host\n", encoding="utf-8")
    path = root / "manifest.toml"
    path.write_text(manifest, encoding="utf-8")
    return path


def test_loads_common_agent_and_host_fragments_in_order(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    manifest = load_manifest(path)

    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.CODEX)
    ] == [
        "shared.md",
        "agent.md",
        "host.md",
    ]


def test_rejects_fragment_outside_manifest_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    root = tmp_path / "config"
    root.mkdir()
    path = _write_config(
        root,
        """
schema_version = 2
fragments = ["../outside.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="escapes the manifest directory"):
        load_manifest(path)


def test_rejects_unknown_host(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="unknown host 'laptop'"):
        load_manifest(path).fragments_for("laptop", Agent.CODEX)


def test_rejects_selected_agent_without_configuration(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="agent 'pi' is not configured"):
        load_manifest(path).fragments_for("workstation", Agent.PI)


def test_rejects_duplicate_selected_fragment(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["shared.md"]
""",
    )

    with pytest.raises(ManifestError, match="duplicate fragments"):
        load_manifest(path).fragments_for("workstation", Agent.CODEX)


def test_rejects_duplicate_agent_fragment(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["shared.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="duplicate fragments"):
        load_manifest(path).fragments_for("workstation", Agent.CODEX)


def test_rejects_unknown_manifest_key(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]
output = "somewhere"

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="unknown keys in manifest: output"):
        load_manifest(path)


def test_rejects_unknown_agent_configuration(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.claude]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="unknown agent 'claude'"):
        load_manifest(path)


def test_rejects_schema_version_one(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 1
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="schema_version must be 2"):
        load_manifest(path)
