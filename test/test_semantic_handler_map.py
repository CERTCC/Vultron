from vultron.core.models.events import MessageSemantics
from vultron.api.v2.backend.handler_map import SEMANTICS_HANDLERS


def test_all_message_semantics_have_handlers():
    """Ensure every MessageSemantics member is present as a key in SEMANTICS_HANDLERS."""
    missing = [
        member
        for member in MessageSemantics
        if member not in SEMANTICS_HANDLERS
    ]
    assert not missing, f"Missing handlers for semantics: {missing}"
