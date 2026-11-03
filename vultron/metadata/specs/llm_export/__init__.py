"""LLM-optimized export for the spec registry.

Produces a flat, inheritance-resolved JSON projection designed for
coding agent consumption.  Requirements become primary objects with
denormalized group/file provenance and resolved kind/scope/tags.

Usage::

    from vultron.metadata.specs.registry import load_registry
    from vultron.metadata.specs.llm_export import to_llm_json

    registry = load_registry()
    # All specs
    print(to_llm_json(registry))
    # Single topic
    print(to_llm_json(registry, topic="CM"))
    # Specific IDs with transitive dependencies
    print(to_llm_json(registry, spec_ids=["EP-04-001"], include_deps=True))
    # Several topics plus a group, slimmed down
    print(to_llm_json(registry, topic=["CM", "EP"], groups=["ARCH-01"],
                      slim=True))
    # Plain-text topic/group map
    print(to_index_text(registry))

Submodules, by concern: ``records`` (one requirement, relationship, step or
topic as an export record), ``selection`` (which requirements a selector
picks) and ``formats`` (the JSON, requirements-text and index outputs).
"""

from vultron.metadata.specs.llm_export.formats import (
    to_index_text,
    to_llm_json,
    to_requirements_text,
)
from vultron.metadata.specs.llm_export.records import CROSS_CUTTING_TOPICS
from vultron.metadata.specs.llm_export.selection import (
    select_spec_ids,
    uncited_adrs,
    unknown_selectors,
)

__all__ = [
    "CROSS_CUTTING_TOPICS",
    "select_spec_ids",
    "to_index_text",
    "to_llm_json",
    "to_requirements_text",
    "uncited_adrs",
    "unknown_selectors",
]
