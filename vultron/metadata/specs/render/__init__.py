"""Context generation tool for the spec registry.

Provides a markdown renderer, a JSON exporter, and a YAML exporter for
agent/human consumption.

Context generation requirements: specs/spec-registry.yaml SR-07.

Usage::

    from pathlib import Path
    from vultron.metadata.specs import load_registry
    from vultron.metadata.specs.render import render_markdown, export_json

    registry = load_registry(Path("specs/"))
    md = render_markdown(registry.files[0])
    js = export_json(registry)

Submodules, by concern: ``markdown`` (Markdown rendering), ``export`` (the
YAML and JSON exports), ``cli`` (the ``python -m`` renderer CLI) and
``dump`` (the ``spec-dump`` CLI).
"""

from vultron.metadata.specs.render.cli import main
from vultron.metadata.specs.render.dump import main_llm_json
from vultron.metadata.specs.render.export import export_json, export_yaml
from vultron.metadata.specs.render.markdown import (
    render_markdown,
    render_registry_markdown,
)

__all__ = [
    "export_json",
    "export_yaml",
    "main",
    "main_llm_json",
    "render_markdown",
    "render_registry_markdown",
]
