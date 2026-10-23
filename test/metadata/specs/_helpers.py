"""Helpers shared by the ``test/metadata/specs/`` modules."""

from pathlib import Path

import yaml


def write_yaml(path: Path, data: dict, filename: str = "specs.yaml") -> None:
    """Dump *data* as YAML to ``path / filename``."""
    (path / filename).write_text(yaml.dump(data))
