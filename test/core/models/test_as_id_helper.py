"""``_as_id`` names an inline stored object by its URI."""

from vultron.core.models._helpers import _as_id


def test_as_id_reads_id_from_an_inline_mapping() -> None:
    assert _as_id({"id": "urn:uuid:1", "type": "VulnerabilityCase"}) == (
        "urn:uuid:1"
    )
    assert _as_id({"id_": "urn:uuid:2"}) == "urn:uuid:2"


def test_as_id_keeps_string_and_none_behavior() -> None:
    assert _as_id("urn:uuid:3") == "urn:uuid:3"
    assert _as_id(None) is None
