"""SpecRegistry and loader for ``specs/*.yaml`` files.

Loader requirements: specs/spec-registry.yaml SR-03.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pydantic import BaseModel, PrivateAttr

from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Scope,
    Spec,
    SpecFile,
    SpecGroup,
    SpecIdStr,
    SpecKind,
    SpecTag,
)

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pyyaml is required for the spec registry loader. "
        "Install it with: pip install pyyaml"
    ) from exc


def effective_kind(spec: Spec, group: SpecGroup, file: SpecFile) -> SpecKind:
    """Resolve the effective ``kind`` for *spec* via inheritance."""
    if spec.kind is not None:
        return spec.kind
    if group.kind is not None:
        return group.kind
    return file.kind


def effective_scope(
    spec: Spec, group: SpecGroup, file: SpecFile
) -> list[Scope]:
    """Resolve the effective ``scope`` for *spec* via inheritance."""
    if spec.scope is not None:
        return spec.scope
    if group.scope is not None:
        return group.scope
    return file.scope


def effective_tags(spec: Spec) -> list[SpecTag]:
    """Return tags for *spec*, defaulting to empty list when absent."""
    return spec.tags if spec.tags is not None else []


class SpecRegistry(BaseModel):
    """Registry of all loaded spec files with ID-based lookup (SR-03-002)."""

    files: list[SpecFile]

    _index: dict[SpecIdStr, Spec] = PrivateAttr(default_factory=dict)
    _group_index: dict[SpecIdStr, SpecGroup] = PrivateAttr(
        default_factory=dict
    )
    _spec_context: dict[SpecIdStr, tuple[SpecGroup, SpecFile]] = PrivateAttr(
        default_factory=dict
    )
    _graph: nx.DiGraph = PrivateAttr(default_factory=nx.DiGraph)

    def model_post_init(self, __context: object) -> None:
        for file in self.files:
            for group in file.groups:
                self._register_group(group)
                for spec in group.specs:
                    self._register_spec(spec)
                    self._spec_context[spec.id] = (group, file)

        # Build the requirements graph after all specs are indexed.
        self._build_graph()

    def _build_graph(self) -> None:
        """Populate ``_graph`` with spec nodes and relationship edges."""
        g = self._graph
        for spec_id, spec in self._index.items():
            group, file = self._spec_context[spec_id]
            spec_type = (
                "behavioral"
                if isinstance(spec, BehavioralSpec)
                else "statement"
            )
            g.add_node(
                spec_id,
                priority=spec.priority.value,
                kind=effective_kind(spec, group, file).value,
                scope=[s.value for s in effective_scope(spec, group, file)],
                file_id=file.id,
                group_id=group.id,
                type=spec_type,
                statement=spec.statement,
            )

        for spec_id, spec in self._index.items():
            for rel in spec.relationships or []:
                note = rel.note if rel.note else None
                g.add_edge(
                    spec_id,
                    rel.spec_id,
                    rel_type=rel.rel_type.value,
                    note=note,
                )

    @property
    def graph(self) -> nx.DiGraph:
        """The requirements graph (specs as nodes, relationships as edges)."""
        return self._graph

    def subgraph_for_topic(self, file_id: str) -> nx.DiGraph:
        """Return the subgraph containing only specs from file *file_id*."""
        nodes = [
            n
            for n, d in self._graph.nodes(data=True)
            if d.get("file_id") == file_id
        ]
        return self._graph.subgraph(nodes).copy()

    def transitive_deps(self, spec_id: SpecIdStr) -> set[str]:
        """Return all spec IDs reachable from *spec_id* via outgoing edges."""
        if spec_id not in self._graph:
            return set()
        return set(nx.descendants(self._graph, spec_id))

    def _register_spec(self, spec: Spec) -> None:
        if spec.id in self._index:
            raise ValueError(f"Duplicate spec ID: {spec.id}")
        self._index[spec.id] = spec

    def _register_group(self, group: SpecGroup) -> None:
        if group.id in self._group_index:
            raise ValueError(f"Duplicate group ID: {group.id}")
        self._group_index[group.id] = group

    def get(self, spec_id: SpecIdStr) -> Spec:
        """Return the spec for the given ID (SR-03-003).

        Raises:
            KeyError: If the spec ID is not found in the registry.
        """
        if spec_id not in self._index:
            raise KeyError(f"Unknown spec ID: {spec_id}")
        return self._index[spec_id]

    def get_effective_kind(self, spec_id: SpecIdStr) -> SpecKind:
        """Return the resolved ``kind`` for *spec_id* via inheritance."""
        spec = self.get(spec_id)
        group, file = self._spec_context[spec_id]
        return effective_kind(spec, group, file)

    def get_effective_scope(self, spec_id: SpecIdStr) -> list[Scope]:
        """Return the resolved ``scope`` for *spec_id* via inheritance."""
        spec = self.get(spec_id)
        group, file = self._spec_context[spec_id]
        return effective_scope(spec, group, file)

    def validate_cross_references(self) -> list[str]:
        """Return error strings for any dangling relationship targets
        (SR-03-004)."""
        errors = []
        for spec_id, spec in self._index.items():
            rels = spec.relationships or []
            for rel in rels:
                if rel.spec_id not in self._index:
                    errors.append(
                        f"{spec_id}: relationship target "
                        f"'{rel.spec_id}' not found"
                    )
        return errors

    @property
    def all_specs(self) -> dict[SpecIdStr, Spec]:
        """Read-only view of the full spec index."""
        return dict(self._index)

    @property
    def all_groups(self) -> dict[SpecIdStr, SpecGroup]:
        """Read-only view of the full group index."""
        return dict(self._group_index)


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``
    (SR-03-007)."""
    origin = start or Path.cwd()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) "
        f"starting from {origin}"
    )


def load_registry(
    spec_dir: Path | None = None,
) -> SpecRegistry:
    """Discover and validate all ``*.yaml`` files in ``spec_dir`` (SR-03-001).

    Args:
        spec_dir: Directory containing ``*.yaml`` spec files.  When ``None``
            the repository root is resolved automatically and ``specs/`` is
            used.

    Returns:
        A fully-indexed :class:`SpecRegistry`.

    Raises:
        ValueError: If any spec file fails validation or contains duplicate IDs.
        FileNotFoundError: If the repository root cannot be resolved.
    """
    if spec_dir is None:
        root = _find_repo_root()
        spec_dir = root / "specs"

    files = []
    for yaml_path in sorted(spec_dir.glob("*.yaml")):
        raw = yaml.safe_load(yaml_path.read_text())
        files.append(SpecFile.model_validate(raw))

    return SpecRegistry(files=files)
