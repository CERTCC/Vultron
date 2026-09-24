"""SpecRegistry and loader for ``specs/*.yaml`` files.

Loader requirements: specs/spec-registry.yaml SR-03.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pydantic import BaseModel, PrivateAttr

from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import (
    FailureCollector,
    load_yaml,
    validate,
)
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

# libyaml-backed loader when the wheel provides it, else the pure-Python one.
# Same SafeLoader semantics either way; the C loader parses the ~1.2 MB spec
# corpus about 10x faster, which matters because ``load_registry()`` is
# uncached and several tests run under a 5 s per-test timeout.
_SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def effective_scope(
    spec: Spec, group: SpecGroup, file: SpecFile
) -> list[Scope]:
    """Resolve the effective ``scope`` for *spec* via inheritance."""
    if spec.scope is not None:
        return spec.scope
    if group.scope is not None:
        return group.scope
    return file.scope


def effective_tags(spec: Spec, file: SpecFile | None = None) -> list[SpecTag]:
    """Return effective tags for *spec*, inheriting from *file* when absent.

    Spec-level tags take priority; when a spec has no tags, the file-level
    tags are returned so that a file-level ``tags:`` entry satisfies the
    per-item lint check for all specs in the file.
    """
    if spec.tags is not None:
        return spec.tags
    if file is not None and file.tags is not None:
        return file.tags
    return []


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
                kind=spec.kind.value,
                scope=[s.value for s in effective_scope(spec, group, file)],
                tags=[t.value for t in effective_tags(spec, file)],
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
        """Return the ``kind`` for *spec_id* (required on every spec item)."""
        return self.get(spec_id).kind

    def get_effective_scope(self, spec_id: SpecIdStr) -> list[Scope]:
        """Return the resolved ``scope`` for *spec_id* via inheritance."""
        spec = self.get(spec_id)
        group, file = self._spec_context[spec_id]
        return effective_scope(spec, group, file)

    def get_effective_tags(self, spec_id: SpecIdStr) -> list[SpecTag]:
        """Return the resolved ``tags`` for *spec_id* via file inheritance."""
        spec = self.get(spec_id)
        _, file = self._spec_context[spec_id]
        return effective_tags(spec, file)

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


#: Re-exported under this module's historical public name (SR-03-007). The
#: implementation is the shared one in ``vultron.metadata.base``; this was the
#: sixth copy, and the only public one, so the sweep that consolidated the five
#: private ``_find_repo_root`` copies did not name it. Kept as an alias because
#: ``specs/coverage.py`` and ``test/metadata/specs/test_coverage.py`` import it
#: from here.
find_repo_root = repo_root


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
        MetadataLoadErrors: If any spec file fails to parse or validate. Every
            failing file is reported in the one error and kept on its
            ``failures`` attribute (SR-03-008, SR-03-009). A ``ValueError``
            subclass, so the documented contract holds.
        ValueError: If the corpus contains duplicate IDs.
        FileNotFoundError: If the repository root cannot be resolved.
    """
    if spec_dir is None:
        root = find_repo_root()
        spec_dir = root / "specs"

    # Paths display relative to the directory holding specs/, which is the
    # repository root for the real corpus (MS-17-001).
    files = []
    collector = FailureCollector()
    for yaml_path in sorted(spec_dir.glob("*.yaml")):
        with collector.attempt():
            raw = load_yaml(
                yaml_path, root=spec_dir.parent, loader=_SafeLoader
            )
            files.append(
                validate(SpecFile, raw, path=yaml_path, root=spec_dir.parent)
            )
    collector.raise_if_any(
        summary=f"{len(collector.failures)} spec file(s) failed to load:"
    )

    return SpecRegistry(files=files)
