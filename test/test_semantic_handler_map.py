from vultron.enums import MessageSemantics
from vultron.semantic_handler_map import SEMANTICS_HANDLERS


def test_all_message_semantics_have_handlers():
    """Ensure every MessageSemantics member is present as a key in SEMANTICS_HANDLERS."""
    missing = [
        member
        for member in MessageSemantics
        if member not in SEMANTICS_HANDLERS
    ]

    assert not missing, f"Missing handlers for semantics: {missing}"
