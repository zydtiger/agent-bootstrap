"""Manifest parsing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_bootstrap.agent import Agent
from agent_bootstrap.config import ManifestError, load_manifest


def _write_config(root: Path, manifest: str) -> Path:
    (root / "shared.md").write_text("shared\n", encoding="utf-8")
    (root / "agent.md").write_text("agent\n", encoding="utf-8")
    (root / "pi.md").write_text("pi\n", encoding="utf-8")
    (root / "zcode.md").write_text("zcode\n", encoding="utf-8")
    (root / "claude.md").write_text("claude\n", encoding="utf-8")
    (root / "host.md").write_text("host\n", encoding="utf-8")
    (root / "other.md").write_text("other\n", encoding="utf-8")
    (root / "host-agent.md").write_text("host-agent\n", encoding="utf-8")
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

[agents.cursor]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    with pytest.raises(ManifestError, match="unknown agent 'cursor'"):
        load_manifest(path)


def test_rejects_unsupported_schema_version(tmp_path: Path) -> None:
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

    with pytest.raises(ManifestError, match="schema_version must be 2 or 3"):
        load_manifest(path)


def test_loads_schema_v3_host_agent_fragments_only_for_the_matching_selection(
    tmp_path: Path,
) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[agents.pi]
fragments = ["pi.md"]

[hosts.workstation]
fragments = ["host.md"]

[hosts.laptop]
fragments = ["other.md"]

[host_agents.workstation.codex]
fragments = ["host-agent.md"]
""",
    )

    manifest = load_manifest(path)

    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.CODEX)
    ] == ["shared.md", "agent.md", "host.md", "host-agent.md"]
    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.PI)
    ] == ["shared.md", "pi.md", "host.md"]
    assert [
        manifest.display_path(item) for item in manifest.fragments_for("laptop", Agent.CODEX)
    ] == ["shared.md", "agent.md", "other.md"]
    assert [
        manifest.display_path(item) for item in manifest.fragments_for("laptop", Agent.PI)
    ] == ["shared.md", "pi.md", "other.md"]


def test_loads_schema_v3_zcode_agent_and_intersection_fragments(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[agents.zcode]
fragments = ["zcode.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.zcode]
fragments = ["host-agent.md"]
""",
    )

    manifest = load_manifest(path)

    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.ZCODE)
    ] == ["shared.md", "zcode.md", "host.md", "host-agent.md"]
    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.CODEX)
    ] == ["shared.md", "agent.md", "host.md"]


def test_loads_schema_v3_claude_agent_and_intersection_fragments(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[agents.claude]
fragments = ["claude.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.claude]
fragments = ["host-agent.md"]
""",
    )

    manifest = load_manifest(path)

    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.CLAUDE)
    ] == ["shared.md", "claude.md", "host.md", "host-agent.md"]
    assert [
        manifest.display_path(item) for item in manifest.fragments_for("workstation", Agent.CODEX)
    ] == ["shared.md", "agent.md", "host.md"]


def test_schema_v3_allows_omitting_host_agents(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
    )

    manifest = load_manifest(path)

    assert manifest.host_agents == {}


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.laptop.codex]
fragments = ["host-agent.md"]
""",
            "host_agents references undeclared host 'laptop'",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.cursor]
fragments = ["host-agent.md"]
""",
            "unknown agent 'cursor' in host_agents.workstation",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.pi]
fragments = ["host-agent.md"]
""",
            "agent 'pi' in host_agents.workstation is not configured",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
extra = true
fragments = ["host-agent.md"]
""",
            "unknown keys in host_agents.workstation.codex: extra",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
""",
            "host_agents.workstation.codex.fragments must be a non-empty array",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
fragments = []
""",
            "host_agents.workstation.codex.fragments must be a non-empty array",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
fragments = "host-agent.md"
""",
            "host_agents.workstation.codex.fragments must be a non-empty array",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
fragments = ["../outside.md"]
""",
            r"host_agents.workstation.codex.fragments\[0\] escapes the manifest directory",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]
host_agents = ["workstation"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
            "host_agents must be a table",
        ),
        (
            """
schema_version = 3
fragments = ["shared.md"]
host_agents.workstation.codex = ["host-agent.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
            "host_agents.workstation.codex must be a table",
        ),
    ],
)
def test_rejects_invalid_schema_v3_host_agents(
    tmp_path: Path, manifest: str, message: str
) -> None:
    path = _write_config(tmp_path, manifest)

    with pytest.raises(ManifestError, match=message):
        load_manifest(path)


def test_rejects_host_agents_in_schema_v2_with_upgrade_error(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
schema_version = 2
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
fragments = ["host-agent.md"]
""",
    )

    with pytest.raises(ManifestError, match="host_agents requires schema_version 3"):
        load_manifest(path)


@pytest.mark.parametrize(
    "host_agent_fragments",
    [
        '["shared.md"]',
        '["agent.md"]',
        '["host.md"]',
        '["host-agent.md", "host-agent.md"]',
    ],
)
def test_rejects_duplicate_fragments_across_all_schema_v3_layers(
    tmp_path: Path, host_agent_fragments: str
) -> None:
    path = _write_config(
        tmp_path,
        f"""
schema_version = 3
fragments = ["shared.md"]

[agents.codex]
fragments = ["agent.md"]

[hosts.workstation]
fragments = ["host.md"]

[host_agents.workstation.codex]
fragments = {host_agent_fragments}
""",
    )

    with pytest.raises(ManifestError, match="duplicate fragments"):
        load_manifest(path).fragments_for("workstation", Agent.CODEX)
