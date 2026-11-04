"""Command-line entry point for ``python -m vultron.metadata.specs.render``."""

from __future__ import annotations

import sys
from pathlib import Path

from vultron.metadata.specs.llm_export import to_llm_json
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.render.export import export_json, export_yaml
from vultron.metadata.specs.render.markdown import render_registry_markdown


def main() -> None:
    """CLI entry point for context generation.

    Usage::

        python -m vultron.metadata.specs.render --format md specs/
        python -m vultron.metadata.specs.render --format json specs/
        python -m vultron.metadata.specs.render --format yaml specs/
        python -m vultron.metadata.specs.render --format llm-json specs/
        python -m vultron.metadata.specs.render --format llm-json --topic CM specs/
    """
    fmt = "md"
    topic = None
    args = sys.argv[1:]
    if "--format" in args:
        idx = args.index("--format")
        fmt = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]
    if "--topic" in args:
        idx = args.index("--topic")
        topic = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if not args:
        print(
            f"Usage: {sys.argv[0]} [--format md|json|yaml|llm-json]"
            " [--topic FILEID] <spec_dir>",
            file=sys.stderr,
        )
        sys.exit(2)

    spec_dir = Path(args[0])
    registry = load_registry(spec_dir)

    if fmt == "json":
        print(export_json(registry))
    elif fmt == "yaml":
        for sf in registry.files:
            print(export_yaml(sf))
            print("---")
    elif fmt == "llm-json":
        print(to_llm_json(registry, topic=topic))
    else:
        print(render_registry_markdown(registry))
