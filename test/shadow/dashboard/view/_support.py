"""What the dashboard's view tests share: the actors they name and the
readings and narrative lines they build."""

from test.shadow.dashboard._support import RCVV
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.history import NarrativeLine
from vultron.shadow.analysis import CaseAnalysis, analyse
from vultron.shadow.readers import VultronCaseReader

VENDOR = "https://vendor.example/actors/vendor"
VENDOR_2 = "https://other.example/actors/vendor2"
NAMES = {VENDOR: "Vendor", VENDOR_2: "Vendor2"}


def rcvv_analysis() -> CaseAnalysis:
    """The analysis of the rcvv-embargo recording."""
    return analyse(VultronCaseReader(root=RECORDINGS_DIR).read_case(str(RCVV)))


def narrative_line(**fields) -> NarrativeLine:
    """A narrative line at log index 0, with *fields* over its defaults."""
    return NarrativeLine(
        **{"log_index": 0, "phrase": "Vendor did a thing", **fields}
    )
