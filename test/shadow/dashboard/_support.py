"""What the case shadow tool's dashboard tests share: the committed
recordings they read and the readings and analyses of them, the vendor
they name, and the headless page run's timeout and text reader.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vultron.core.models.case_reading import CaseReading, UnobservableFact
from vultron.core.states.cs_invariants import CSEvent
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.shadow.analysis import CaseAnalysis, analyse
from vultron.shadow.readers import VultronCaseReader

if TYPE_CHECKING:
    from pathlib import Path

#: Seconds one script run may take; the first run imports the measures.
TIMEOUT = 60

#: The rv recording of the case actor's ledger.
RV = RECORDINGS_DIR / "rv" / "case-actor.jsonl"

#: The rcvv-embargo recording of the case actor's ledger.
RCVV = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"

VENDOR = "https://vendor.example/actors/vendor"


def texts(elements) -> list[str]:
    """Each page element's value, as text."""
    return [str(element.value) for element in elements]


def read_recording(path: Path = RCVV) -> CaseReading:
    """The Vultron case reader's reading of the recording at *path*."""
    return VultronCaseReader(root=RECORDINGS_DIR).read_case(str(path))


def recording_analysis(path: Path = RCVV) -> CaseAnalysis:
    """The analysis of the recording at *path*."""
    return analyse(read_recording(path))


def reading_with_d_unobservable() -> CaseReading:
    """The rcvv-embargo reading, from a source that cannot observe a fix
    being deployed (D)."""
    recorded = read_recording(RCVV)
    return CaseReading(
        ledger=recorded.ledger,
        citations=recorded.citations,
        unobservable=(
            UnobservableFact(
                fact="Fix Deployed (D)",
                why="no field",
                events=frozenset({CSEvent.D}),
            ),
        ),
    )
