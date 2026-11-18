#!/usr/bin/env python3
"""Check that the case shadow tool's live reader reads a case off a node.

The case shadow tool's CI job starts the demo stack's ``case-actor`` node and
the shadow image side by side, creates one case on the node, and runs this
script inside the shadow container (``python - … < shadow_live_read.py``),
so it runs the image's own installed reader over the Compose network
(#6642).  It builds the reader the way the page does for a node the analyst
types: the typed values are checked by the ``shadow:`` settings' rules, and
the reader is the one the running-node source reads through.  It then
follows the case, as the page does, until a reading with at least one
ledger entry arrives.

A node commits a new case's first ledger entry a moment after it answers
the request that created it, so a follow that is refused (no such case yet)
or that ends with no entry is tried again until the deadline.

Exit status: 0 when a reading with at least one ledger entry arrives before
the deadline, with its size on stdout; 1 when none does, with the last
reason on stdout; 2 when the node or actor id is refused before any request
is sent.

Usage: shadow_live_read.py NODE_URL ACTOR_ID CASE_ID [--deadline SECONDS]
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence

from vultron.config.shadow import ShadowConfig
from vultron.core.models.case_reading import CaseReading
from vultron.errors import VultronConfigError
from vultron.shadow.readers import (
    CaseSource,
    VultronNode,
    configured_case_reader,
    typed_node,
)
from vultron.shadow.readers.following import CaseFollower

#: Seconds the check waits for a reading by default.
DEFAULT_DEADLINE = 60.0
#: Seconds between one follow that read nothing and the next.
RETRY_PAUSE = 1.0


class NoReading(Exception):
    """No reading with a ledger entry arrived before the deadline."""


def page_reader(node: VultronNode) -> CaseFollower:
    """The reader the page's running-node source reads *node* through."""
    reader = configured_case_reader(ShadowConfig(), CaseSource.NODE, node=node)
    if not isinstance(reader, CaseFollower):
        raise TypeError("the running-node source's reader cannot follow")
    return reader


def first_reading(
    reader: CaseFollower,
    case_id: str,
    deadline: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> CaseReading:
    """The first reading of *case_id* with a ledger entry, by *deadline*.

    Raises:
        NoReading: The deadline, a *clock* time, passed first; the message
            gives the last reason a follow read nothing.
    """
    last = "the follow sent no ledger entry"

    def beat() -> None:
        # A quiet stream beats; past the deadline, stop the follow.
        if clock() >= deadline:
            raise NoReading(f"timed out; {last}")

    while clock() < deadline:
        for item in reader.follow_case(case_id, heartbeat=beat):
            if not isinstance(item, CaseReading):
                last = str(item)
            elif item.ledger:
                return item
        pause(RETRY_PAUSE)
    raise NoReading(f"timed out; {last}")


def main(
    argv: Sequence[str] | None = None,
    *,
    reader_for: Callable[[VultronNode], CaseFollower] = page_reader,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n")[0]
    )
    parser.add_argument("node_url", help="the node's API root")
    parser.add_argument("actor_id", help="the CASE_MANAGER's actor id")
    parser.add_argument("case_id", help="the case's id on the node")
    parser.add_argument(
        "--deadline",
        type=float,
        default=DEFAULT_DEADLINE,
        help="seconds to wait for a reading",
    )
    args = parser.parse_args(argv)
    try:
        node = typed_node(args.node_url, args.actor_id)
    except VultronConfigError as exc:
        print(f"Refused before any request: {exc}")
        return 2
    try:
        reading = first_reading(
            reader_for(node),
            args.case_id,
            clock() + args.deadline,
            clock=clock,
            pause=pause,
        )
    except NoReading as exc:
        print(f"No reading of case {args.case_id} from {node.url}: {exc}")
        return 1
    print(
        f"Read case {args.case_id} from {node.url}:"
        f" ledger entries: {len(reading.ledger)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
