"""Spec registry linter.

Linter requirements: specs/spec-registry.yaml SR-04.

Usage::

    python -m vultron.metadata.specs.lint specs/

Submodules, by concern: ``adr_refs`` (ADR status and reference checks),
``phantom_paths`` (path citations and the tree they resolve against),
``phantom_symbols`` (code-symbol and spec-id citations), ``structure``
(prefix, lifecycle, kind and scenario-group checks), ``advisories``
(story traceability and per-spec advisory warnings) and ``driver``
(the ``lint()`` driver and the CLI).
"""

from vultron.metadata.specs.lint.advisories import sr_11_003_gate_applies
from vultron.metadata.specs.lint.driver import lint, main
from vultron.metadata.specs.lint.phantom_paths import (
    SPEC_DIR_RE,
    SPEC_PATH_RE,
    PathResolver,
)
from vultron.metadata.specs.lint.phantom_symbols import (
    SOURCE_SYMBOL_RE,
    iter_python_sources,
    path_is_under,
)

__all__ = [
    "PathResolver",
    "SOURCE_SYMBOL_RE",
    "SPEC_DIR_RE",
    "SPEC_PATH_RE",
    "iter_python_sources",
    "lint",
    "main",
    "path_is_under",
    "sr_11_003_gate_applies",
]
