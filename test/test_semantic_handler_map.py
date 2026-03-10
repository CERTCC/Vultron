from vultron.core.models.events import MessageSemantics
from vultron.semantic_handler_map import get_semantics_handlers
from vultron.api.v2.backend.handler_map import SEMANTICS_HANDLERS


def test_all_message_semantics_have_handlers():
    """Ensure every MessageSemantics member is present as a key in the semantics handler map."""
    handler_map = get_semantics_handlers()
    missing = [
        member for member in MessageSemantics if member not in handler_map
    ]
    assert not missing, f"Missing handlers for semantics: {missing}"


def test_handler_map_importable_from_new_location():
    """SEMANTICS_HANDLERS is importable directly from the adapter layer."""
    missing = [
        member
        for member in MessageSemantics
        if member not in SEMANTICS_HANDLERS
    ]
    assert not missing, f"Missing handlers in SEMANTICS_HANDLERS: {missing}"


def test_shim_returns_same_object():
    """get_semantics_handlers() returns the same dict as SEMANTICS_HANDLERS."""
    assert get_semantics_handlers() is SEMANTICS_HANDLERS
