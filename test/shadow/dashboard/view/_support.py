"""What the dashboard's view tests share: the actors they name and the
narrative lines they build."""

from test.shadow.dashboard._support import VENDOR
from vultron.measure.history import NarrativeLine

VENDOR_2 = "https://other.example/actors/vendor2"
NAMES = {VENDOR: "Vendor", VENDOR_2: "Vendor2"}


def narrative_line(**fields) -> NarrativeLine:
    """A narrative line at log index 0, with *fields* over its defaults."""
    return NarrativeLine(
        **{"log_index": 0, "phrase": "Vendor did a thing", **fields}
    )


__all__ = ["NAMES", "VENDOR", "VENDOR_2", "narrative_line"]
