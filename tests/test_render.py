"""Instruction rendering tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_bootstrap.config import ManifestError, load_manifest
from agent_bootstrap.render import GENERATED_MARKER, render_instructions


def _manifest(tmp_path: Path, shared: str = "# Shared\r\n\r\nText\r\n") -> Path:
    (tmp_path / "shared.md").write_bytes(shared.encode())
    (tmp_path / "host.md").write_text("# Host\n\nSetting\n\n", encoding="utf-8")
    path = tmp_path / "manifest.toml"
    path.write_text(
        """
schema_version = 1
fragments = ["shared.md"]

[hosts.workstation]
fragments = ["host.md"]
""",
        encoding="utf-8",
    )
    return path


def test_render_is_deterministic_and_normalizes_newlines(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path))

    first = render_instructions(manifest, "workstation")
    second = render_instructions(manifest, "workstation")

    assert first == second
    assert GENERATED_MARKER in first
    assert "Host: workstation" in first
    assert "- shared.md\n- host.md" in first
    assert "\r" not in first
    assert first.endswith("Setting\n")
    assert not first.endswith("\n\n")


def test_render_rejects_empty_fragment(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path, shared="\n\n"))

    with pytest.raises(ManifestError, match=r"fragment is empty: shared\.md"):
        render_instructions(manifest, "workstation")
