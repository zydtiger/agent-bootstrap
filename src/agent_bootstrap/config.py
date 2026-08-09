"""Manifest parsing and fragment-path validation."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from agent_bootstrap.agent import Agent


class ManifestError(ValueError):
    """Raised when a manifest is invalid or incomplete."""


@dataclass(frozen=True)
class HostConfig:
    """Ordered fragments selected for one host."""

    fragments: tuple[Path, ...]


@dataclass(frozen=True)
class AgentConfig:
    """Ordered fragments selected for one agent."""

    fragments: tuple[Path, ...]


@dataclass(frozen=True)
class Manifest:
    """Validated manifest with paths resolved relative to its directory."""

    path: Path
    root: Path
    fragments: tuple[Path, ...]
    agents: Mapping[Agent, AgentConfig]
    hosts: Mapping[str, HostConfig]

    def fragments_for(self, host: str, agent: Agent) -> tuple[Path, ...]:
        """Return common, agent, and host fragments in composition order."""
        try:
            host_config = self.hosts[host]
        except KeyError as error:
            choices = ", ".join(sorted(self.hosts)) or "none"
            raise ManifestError(f"unknown host {host!r}; configured hosts: {choices}") from error

        try:
            agent_config = self.agents[agent]
        except KeyError as error:
            choices = ", ".join(
                item.value for item in sorted(self.agents, key=lambda item: item.value)
            )
            raise ManifestError(
                f"agent {agent.value!r} is not configured; configured agents: {choices or 'none'}"
            ) from error

        selected = self.fragments + agent_config.fragments + host_config.fragments
        duplicates = _duplicates(selected)
        if duplicates:
            names = ", ".join(path.relative_to(self.root).as_posix() for path in duplicates)
            raise ManifestError(
                f"duplicate fragments selected for host {host!r} and agent {agent.value!r}: {names}"
            )
        return selected

    def display_path(self, fragment: Path) -> str:
        """Return a stable manifest-relative fragment name."""
        return fragment.relative_to(self.root).as_posix()


def load_manifest(path: Path) -> Manifest:
    """Parse and validate a schema-v2 manifest."""
    manifest_path = path.expanduser().resolve()
    if not manifest_path.is_file():
        raise ManifestError(f"manifest does not exist: {manifest_path}")

    try:
        with manifest_path.open("rb") as stream:
            raw = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"invalid TOML in {manifest_path}: {error}") from error

    _reject_unknown_keys(raw, {"schema_version", "fragments", "agents", "hosts"}, "manifest")
    if raw.get("schema_version") != 2:
        raise ManifestError("schema_version must be 2")

    root = manifest_path.parent
    fragments = _parse_fragments(raw.get("fragments"), root, "fragments")
    agents = _parse_agents(raw.get("agents"), root)
    hosts = _parse_hosts(raw.get("hosts"), root)
    return Manifest(
        path=manifest_path,
        root=root,
        fragments=fragments,
        agents=MappingProxyType(agents),
        hosts=MappingProxyType(hosts),
    )


def _parse_agents(raw: Any, root: Path) -> dict[Agent, AgentConfig]:
    if not isinstance(raw, dict) or not raw:
        raise ManifestError("agents must be a non-empty table")

    agents: dict[Agent, AgentConfig] = {}
    for name, value in raw.items():
        try:
            agent = Agent(name)
        except ValueError as error:
            choices = ", ".join(item.value for item in Agent)
            raise ManifestError(f"unknown agent {name!r}; supported agents: {choices}") from error
        if not isinstance(value, dict):
            raise ManifestError(f"agents.{name} must be a table")
        _reject_unknown_keys(value, {"fragments"}, f"agents.{name}")
        agents[agent] = AgentConfig(
            fragments=_parse_fragments(value.get("fragments"), root, f"agents.{name}.fragments")
        )
    return agents


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
