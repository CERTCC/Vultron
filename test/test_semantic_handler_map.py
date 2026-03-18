from vultron.core.models.events import MessageSemantics
from vultron.core.use_cases.use_case_map import USE_CASE_MAP


def test_all_message_semantics_have_handlers():
    """Ensure every MessageSemantics member is present as a key in USE_CASE_MAP."""
    missing = [
        member for member in MessageSemantics if member not in USE_CASE_MAP
    ]
    assert not missing, f"Missing handlers for semantics: {missing}"
