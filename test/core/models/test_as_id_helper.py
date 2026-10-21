"""``_as_id`` names an inline stored object by its URI."""

from types import MappingProxyType

from vultron.core.models._helpers import _as_id


def test_as_id_reads_id_from_an_inline_mapping() -> None:
    assert _as_id({"id": "urn:uuid:1", "type": "VulnerabilityCase"}) == (
        "urn:uuid:1"
    )
    assert _as_id({"id_": "urn:uuid:2"}) == "urn:uuid:2"


def test_as_id_reads_id_from_a_read_only_mapping() -> None:
    """A received activity's view hands an inline dict out read-only."""
    inline = MappingProxyType(
        {"id": "urn:uuid:4", "type": "VulnerabilityCase"}
    )
    assert _as_id(inline) == "urn:uuid:4"


def test_as_id_keeps_string_and_none_behavior() -> None:
    assert _as_id("urn:uuid:3") == "urn:uuid:3"
    assert _as_id(None) is None
