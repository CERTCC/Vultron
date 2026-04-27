"""Spec registry for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.md SR-02, SR-03.
"""

from vultron.metadata.specs.registry import SpecRegistry, load_registry

__all__ = ["SpecRegistry", "load_registry"]
