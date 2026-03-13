"""
Backward-compatibility re-export shim.

``SEMANTICS_HANDLERS`` has moved to ``vultron.core.use_cases.use_case_map``.
Import from there for new code.
"""

from vultron.core.use_cases.use_case_map import (
    USE_CASE_MAP as SEMANTICS_HANDLERS,
)  # noqa: F401

__all__ = ["SEMANTICS_HANDLERS"]
