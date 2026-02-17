from vultron.enums import MessageSemantics
from vultron.semantic_handler_map import get_semantics_handlers


def test_all_message_semantics_have_handlers():
    """Ensure every MessageSemantics member is present as a key in the semantics handler map."""
    handler_map = get_semantics_handlers()
    missing = [
        member
        for member in MessageSemantics
        if member not in handler_map
    ]

    assert not missing, f"Missing handlers for semantics: {missing}"
