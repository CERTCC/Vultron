"""SpecRegistry and loader for ``specs/*.yaml`` files.

Loader requirements: specs/spec-registry.md SR-03.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, PrivateAttr

from vultron.metadata.specs.schema import Spec, SpecFile, SpecGroup, SpecIdStr

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pyyaml is required for the spec registry loader. "
        "Install it with: pip install pyyaml"
    ) from exc


class SpecRegistry(BaseModel):
    """Registry of all loaded spec files with ID-based lookup (SR-03-002)."""

    files: list[SpecFile]

    _index: dict[SpecIdStr, Spec] = PrivateAttr(default_factory=dict)
    _group_index: dict[SpecIdStr, SpecGroup] = PrivateAttr(
        default_factory=dict
    )

    def model_post_init(self, __context: object) -> None:
        for file in self.files:
            for group in file.groups:
                self._register_group(group)
                for spec in group.specs:
                    self._register_spec(spec)

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

    def validate_cross_references(self) -> list[str]:
        """Return error strings for any dangling relationship targets
        (SR-03-004)."""
        errors = []
        for spec_id, spec in self._index.items():
            for rel in spec.relationships:
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
