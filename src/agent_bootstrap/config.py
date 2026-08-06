"""Manifest parsing and fragment-path validation."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


class ManifestError(ValueError):
    """Raised when a manifest is invalid or incomplete."""


@dataclass(frozen=True)
class HostConfig:
    """Ordered fragments selected for one host."""

    fragments: tuple[Path, ...]


@dataclass(frozen=True)
class Manifest:
    """Validated manifest with paths resolved relative to its directory."""

    path: Path
    root: Path
    fragments: tuple[Path, ...]
    hosts: Mapping[str, HostConfig]

    def fragments_for(self, host: str) -> tuple[Path, ...]:
        """Return global and host fragments in composition order."""
        try:
            host_config = self.hosts[host]
        except KeyError as error:
            choices = ", ".join(sorted(self.hosts)) or "none"
            raise ManifestError(f"unknown host {host!r}; configured hosts: {choices}") from error

        selected = self.fragments + host_config.fragments
        duplicates = _duplicates(selected)
        if duplicates:
            names = ", ".join(path.relative_to(self.root).as_posix() for path in duplicates)
            raise ManifestError(f"duplicate fragments selected for host {host!r}: {names}")
        return selected

    def display_path(self, fragment: Path) -> str:
        """Return a stable manifest-relative fragment name."""
        return fragment.relative_to(self.root).as_posix()


def load_manifest(path: Path) -> Manifest:
    """Parse and validate a schema-v1 manifest."""
    manifest_path = path.expanduser().resolve()
    if not manifest_path.is_file():
        raise ManifestError(f"manifest does not exist: {manifest_path}")

    try:
        with manifest_path.open("rb") as stream:
            raw = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"invalid TOML in {manifest_path}: {error}") from error

    _reject_unknown_keys(raw, {"schema_version", "fragments", "hosts"}, "manifest")
    if raw.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")

    root = manifest_path.parent
    fragments = _parse_fragments(raw.get("fragments"), root, "fragments")
    hosts = _parse_hosts(raw.get("hosts"), root)
    return Manifest(
        path=manifest_path,
        root=root,
        fragments=fragments,
        hosts=MappingProxyType(hosts),
    )


def _parse_hosts(raw: Any, root: Path) -> dict[str, HostConfig]:
    if not isinstance(raw, dict) or not raw:
        raise ManifestError("hosts must be a non-empty table")

    hosts: dict[str, HostConfig] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ManifestError("host names must be non-empty strings")
        if not isinstance(value, dict):
            raise ManifestError(f"hosts.{name} must be a table")
        _reject_unknown_keys(value, {"fragments"}, f"hosts.{name}")
        hosts[name] = HostConfig(
            fragments=_parse_fragments(value.get("fragments"), root, f"hosts.{name}.fragments")
        )
    return hosts


def _parse_fragments(raw: Any, root: Path, field: str) -> tuple[Path, ...]:
    if not isinstance(raw, list) or not raw:
        raise ManifestError(f"{field} must be a non-empty array of paths")

    fragments: list[Path] = []
    for index, value in enumerate(raw):
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"{field}[{index}] must be a non-empty string")
        declared = Path(value)
        if declared.is_absolute():
            raise ManifestError(f"{field}[{index}] must be relative to the manifest")
        resolved = (root / declared).resolve()
        if not resolved.is_relative_to(root):
            raise ManifestError(f"{field}[{index}] escapes the manifest directory: {value}")
        if not resolved.is_file():
            raise ManifestError(f"fragment does not exist: {value}")
        fragments.append(resolved)
    return tuple(fragments)


def _reject_unknown_keys(raw: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ManifestError(f"unknown keys in {context}: {', '.join(unknown)}")


def _duplicates(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    duplicates: list[Path] = []
    for path in paths:
        if path in seen and path not in duplicates:
            duplicates.append(path)
        seen.add(path)
    return tuple(duplicates)
