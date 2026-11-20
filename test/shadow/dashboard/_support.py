"""What the case shadow tool's dashboard tests share: the committed
recordings they read and the headless page run's timeout and text reader.
"""

from __future__ import annotations

from vultron.demo.recordings.layout import RECORDINGS_DIR

#: Seconds one script run may take; the first run imports the measures.
TIMEOUT = 60

#: The rv recording of the case actor's ledger.
RV = RECORDINGS_DIR / "rv" / "case-actor.jsonl"

#: The rcvv-embargo recording of the case actor's ledger.
RCVV = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"


def texts(elements) -> list[str]:
    """Each page element's value, as text."""
    return [str(element.value) for element in elements]
