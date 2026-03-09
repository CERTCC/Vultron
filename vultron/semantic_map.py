"""
Backward-compatibility shim. All content has moved to vultron.wire.as2.extractor.
"""

# Re-export everything from the canonical location so existing imports continue to work.
from vultron.wire.as2.extractor import (  # noqa: F401
    SEMANTICS_ACTIVITY_PATTERNS,
    find_matching_semantics,
)
