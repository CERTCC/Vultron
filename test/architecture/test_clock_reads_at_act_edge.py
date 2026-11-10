#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Architecture ratchet: an act reads the clock once, at its edge (ADR-0176).

Every clock read under ``vultron/`` (``_clock_reads.py`` says what counts as
one and what is not scanned) must be listed below, one item per read, and
every item must still be a read: the comparison is an exact multiset
(ARCH-18-001, ARCH-18-006).  So a new clock read anywhere fails here, and so
does an item a fix left behind.

Two kinds of list:

- :data:`CLOCK_EDGE_EXEMPTIONS` is a **pinned exemption set**: the reads
  ADR-0176 permits for good — the wall-clock read the act clock is built on,
  the two system clocks behind the clock ports, and the stopwatch reads at
  named sites.
- Each ``KNOWN_*_CLOCK_READS`` constant is a **ratchet**: today's reads below
  an act's edge, grouped by the slice of #5676 that removes them.  A slice
  deletes its own items as it moves each read to the act's instant
  (``read_act_instant()`` in a node, a required argument elsewhere).
  :data:`KNOWN_UNSLICED_CLOCK_READS` holds the reads no slice names yet.

Each read appears in exactly one list, so each has one owner.

A second check keeps the clocks themselves at the edge: the modules that
name a clock port or a system clock are a pinned exemption set too
(:data:`CLOCK_HOLDER_EXEMPTIONS`), because only an act's entry point and the
composition root that wires it may hold the act clock, and only an adapter
may hold the bookkeeping clock.

Spec: CS-13-002 (time enters through the act clock), ARCH-18-001.
"""

from collections import Counter

import pytest

from test.architecture import _corpus
from test.architecture._clock_reads import (
    ClockRead,
    clock_reads,
    reads_in_source,
)

# Pinned exemption set: the reads ADR-0176 permits at the act's edge.
# permanent: ADR-0176 (the act clock's one wall-clock read, the system clocks
# behind the two clock ports, and stopwatch reads at named sites)
CLOCK_EDGE_EXEMPTIONS: tuple[ClockRead, ...] = (
    (
        "vultron/adapters/driven/clock.py",
        "SystemBookkeepingClock.bookkeeping_now",
        "datetime.now",
    ),
    (
        "vultron/adapters/driven/clock.py",
        "SystemClock.now",
        "now_utc",
    ),
    (
        "vultron/core/models/_helpers/clock.py",
        "now_utc",
        "datetime.now",
    ),
    (
        "vultron/demo/helpers/polling/_poll.py",
        "ProgressDeadline.__init__",
        "time.monotonic",
    ),
    (
        "vultron/demo/helpers/polling/_poll.py",
        "ProgressDeadline.expired",
        "time.monotonic",
    ),
    (
        "vultron/demo/helpers/polling/_poll.py",
        "ProgressDeadline.observe",
        "time.monotonic",
    ),
    (
        "vultron/demo/helpers/polling/_poll.py",
        "SharedBudget.__init__",
        "time.monotonic",
    ),
    (
        "vultron/demo/helpers/polling/_poll.py",
        "SharedBudget.remaining",
        "time.monotonic",
    ),
    (
        "vultron/demo/helpers/polling/participant.py",
        "_poll_participant",
        "time.monotonic",
    ),
    (
        "vultron/demo/helpers/polling/participant.py",
        "_poll_participant",
        "time.monotonic",
    ),
    (
        "vultron/demo/recordings/compare.py",
        "_record",
        "time.monotonic",
    ),
    (
        "vultron/demo/recordings/compare.py",
        "_record",
        "time.monotonic",
    ),
    (
        "vultron/demo/recordings/compare.py",
        "main",
        "time.monotonic",
    ),
    (
        "vultron/demo/recordings/compare.py",
        "main",
        "time.monotonic",
    ),
)

# Core models and time helpers take the act's instant; a caller of a helper
# whose signature changes is listed with the helper.
# owner: #5758
KNOWN_CORE_MODEL_CLOCK_READS: tuple[ClockRead, ...] = (
    (
        "vultron/core/behaviors/case/nodes/embargo.py",
        "CreateEmbargoEventNode.update",
        "from_now_utc",
    ),
    (
        "vultron/core/behaviors/case/nodes/embargo_revision.py",
        "ResolveCreationTimeRevisionNode._losing_candidate",
        "from_now_utc",
    ),
    (
        "vultron/core/behaviors/case_status_snapshot.py",
        "EmitCaseStatusUpdateNode.update",
        "now_utc_after",
    ),
    (
        "vultron/core/models/_helpers/clock.py",
        "days_from_now_utc",
        "from_now_utc",
    ),
    (
        "vultron/core/models/_helpers/clock.py",
        "from_now_utc",
        "now_utc",
    ),
    (
        "vultron/core/models/_helpers/clock.py",
        "now_utc_after",
        "now_utc",
    ),
    (
        "vultron/core/models/_helpers/clock.py",
        "require_future_aware",
        "now_utc",
    ),
    (
        "vultron/core/models/_helpers/timestamps.py",
        "claimed_published_iso",
        "now_utc",
    ),
    (
        "vultron/core/models/base/core_object.py",
        "CoreObject.published",
        "now_utc",
    ),
    (
        "vultron/core/models/base/core_object.py",
        "CoreObject.updated",
        "now_utc",
    ),
    (
        "vultron/core/models/case/_construction.py",
        "_genesis_published",
        "now_utc",
    ),
    (
        "vultron/core/models/case/_statuses.py",
        "CaseStatusHistoryMixin.append_case_status",
        "now_utc_after",
    ),
    (
        "vultron/core/models/case_ledger/record.py",
        "HashChainLedgerRecord._compute_entry_hash",
        "now_utc",
    ),
    (
        "vultron/core/models/case_ledger/record.py",
        "HashChainLedgerRecord.received_at",
        "now_utc",
    ),
    (
        "vultron/core/models/case_ledger_entry.py",
        "CaseLedgerEntry.published",
        "now_utc",
    ),
    (
        "vultron/core/models/case_ledger_entry.py",
        "CaseLedgerEntry.received_at",
        "now_utc",
    ),
    (
        "vultron/core/models/case_status.py",
        "CaseStatus.published",
        "now_utc",
    ),
    (
        "vultron/core/models/dead_letter.py",
        "DeadLetterRecord.received_at",
        "now_utc",
    ),
    (
        "vultron/core/models/embargo_event.py",
        "EmbargoEvent.start_time",
        "now_utc",
    ),
    (
        "vultron/core/models/pending_assertion/store.py",
        "PendingAssertion.emitted_at",
        "now_utc",
    ),
    (
        "vultron/core/models/pending_assertion/store.py",
        "PendingAssertionStore.expire_timed_out",
        "now_utc",
    ),
    (
        "vultron/core/models/pending_case_inbox.py",
        "VultronPendingCaseInbox.queued_at",
        "now_utc",
    ),
    (
        "vultron/core/models/received_activity_record.py",
        "ReceivedActivityRecord.received_at",
        "now_utc",
    ),
    (
        "vultron/core/models/replication_state.py",
        "VultronReplicationState.updated_at",
        "now_utc",
    ),
    (
        "vultron/core/use_cases/triggers/request_bodies/actor.py",
        "OfferCaseOwnershipTransferRequest.end_time_must_be_tz_aware_and_future",
        "require_future_aware",
    ),
    (
        "vultron/core/use_cases/triggers/request_bodies/embargo.py",
        "ProposeEmbargoRequest.end_time_must_be_tz_aware_and_future",
        "require_future_aware",
    ),
    (
        "vultron/core/use_cases/triggers/request_bodies/report.py",
        "SubmitReportFields.proposed_end_must_be_tz_aware_and_future",
        "require_future_aware",
    ),
    (
        "vultron/demo/exchange/embargo_lifecycle.py",
        "_end_time",
        "days_from_now_utc",
    ),
    (
        "vultron/demo/exchange/report_with_embargo_demo.py",
        "_run_negotiated_submission",
        "from_now_utc",
    ),
    (
        "vultron/demo/exchange/transfer_ownership_demo.py",
        "demo_transfer_ownership_accept",
        "from_now_utc",
    ),
    (
        "vultron/demo/helpers/seeding/participants.py",
        "_seed_active_embargo",
        "from_now_utc",
    ),
    (
        "vultron/wire/as2/vocab/base/objects/base.py",
        "as_Object.published",
        "now_utc",
    ),
    (
        "vultron/wire/as2/vocab/base/objects/base.py",
        "as_Object.updated",
        "now_utc",
    ),
)

# The parse edge, and the RSVP and pre-bootstrap-queue reads beside it.
# owner: #5652
KNOWN_PARSE_EDGE_CLOCK_READS: tuple[ClockRead, ...] = (
    (
        "vultron/adapters/driving/fastapi/inbox_pending_queue.py",
        "_expire_pending_case_activities",
        "now_utc",
    ),
    (
        "vultron/adapters/driving/fastapi/inbox_pending_queue.py",
        "_queue_pending_case_activity",
        "now_utc",
    ),
)

# Reads below an act's edge that no slice names yet: the epic routes each one.
# owner: #5676
KNOWN_UNSLICED_CLOCK_READS: tuple[ClockRead, ...] = (
    (
        "vultron/core/use_cases/received/embargo/reject.py",
        "RejectInviteToEmbargoOnCaseReceivedUseCase.execute",
        "now_utc",
    ),
    (
        "vultron/demo/helpers/embargo.py",
        "make_embargo_event",
        "now_utc",
    ),
    (
        "vultron/wire/as2/signing.py",
        "sign",
        "now_utc",
    ),
)

_ALL_LISTS: dict[str, tuple[ClockRead, ...]] = {
    "CLOCK_EDGE_EXEMPTIONS": CLOCK_EDGE_EXEMPTIONS,
    "KNOWN_CORE_MODEL_CLOCK_READS": KNOWN_CORE_MODEL_CLOCK_READS,
    "KNOWN_PARSE_EDGE_CLOCK_READS": KNOWN_PARSE_EDGE_CLOCK_READS,
    "KNOWN_UNSLICED_CLOCK_READS": KNOWN_UNSLICED_CLOCK_READS,
}

# Pinned exemption set: the modules that may name a clock port or a system
# clock — the ports, their adapters, the act entry points and the
# composition roots that wire them.
# permanent: ADR-0176 (only an act's entry point holds the act clock; only an
# adapter holds the bookkeeping clock)
CLOCK_HOLDER_EXEMPTIONS: frozenset[str] = frozenset(
    {
        # The ports and the system clocks behind them.
        "vultron/core/ports/clock.py",
        "vultron/adapters/driven/clock.py",
        # open_act: the one place an act reads its clock.
        "vultron/core/behaviors/bridge/act_instant.py",
        # Act entry points: a delivery, a trigger, a sweep.
        "vultron/core/behaviors/inbox/_process_payload.py",
        "vultron/core/use_cases/triggers/_base/bt.py",
        "vultron/core/use_cases/triggers/actor/participant_role.py",
        "vultron/core/use_cases/triggers/actor/ownership.py",
        "vultron/core/use_cases/triggers/actor/recommendation.py",
        "vultron/core/use_cases/triggers/case/leave.py",
        "vultron/core/use_cases/triggers/sync.py",
        "vultron/adapters/driving/fastapi/sender_sequence_holds.py",
        "vultron/adapters/driving/fastapi/inbox_handler.py",
        "vultron/demo/fuzzer/stochastic_demo.py",
        # Composition roots that hand the clock to an entry point.
        "vultron/core/trigger_dispatcher.py",
        "vultron/adapters/driving/fastapi/deps.py",
        "vultron/adapters/driving/fastapi/inbox_orchestration/pipeline.py",
        "vultron/adapters/driving/fastapi/inbox_queue_drain.py",
        "vultron/adapters/driving/fastapi/ledger_position_statements.py",
        "vultron/adapters/driving/cli.py",
        # The bookkeeping clock's one holder.
        "vultron/adapters/driven/datalayer_sqlite/datalayer.py",
    }
)

_CLOCK_NAMES = (
    "ClockPort",
    "BookkeepingClockPort",
    "SystemClock",
    "SystemBookkeepingClock",
)


def _listed() -> Counter[ClockRead]:
    listed: Counter[ClockRead] = Counter()
    for items in _ALL_LISTS.values():
        listed.update(items)
    return listed


def _describe(items: Counter[ClockRead]) -> str:
    return "\n".join(
        f"  {path} :: {scope} :: {read}"
        + (f" (x{count})" if count > 1 else "")
        for (path, scope, read), count in sorted(items.items())
    )


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("ARCH-18-001")
def test_every_clock_read_is_listed_and_every_listed_read_exists() -> None:
    found = clock_reads()
    listed = _listed()

    new = found - listed
    stale = listed - found
    assert not new, (
        "A clock read below an act's edge (ADR-0176).  Take the act's"
        " instant instead: read_act_instant() in a tree node, a required"
        " argument elsewhere.  A read the ADR permits at the edge goes in"
        " CLOCK_EDGE_EXEMPTIONS:\n" + _describe(new)
    )
    assert not stale, (
        "Listed clock reads that are no longer reads; delete them from"
        " their list (ARCH-18-002, ARCH-18-006):\n" + _describe(stale)
    )


@pytest.mark.spec("ARCH-18-001")
def test_each_clock_read_has_one_owner() -> None:
    owners: dict[ClockRead, set[str]] = {}
    for name, items in _ALL_LISTS.items():
        for item in items:
            owners.setdefault(item, set()).add(name)
    shared = {item: names for item, names in owners.items() if len(names) > 1}
    assert not shared, f"A read is listed under two owners: {shared}"


@pytest.mark.spec("CS-13-002")
def test_only_the_act_edge_holds_a_clock() -> None:
    holders = {
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, _ in _corpus.sources_mentioning(
            *_CLOCK_NAMES, under=_corpus.REPO_ROOT / "vultron"
        )
    }
    assert holders == CLOCK_HOLDER_EXEMPTIONS, (
        "A module that names a clock port or a system clock is not an act's"
        " entry point or the composition root that wires one (ADR-0176)."
        f"\n  new: {sorted(holders - CLOCK_HOLDER_EXEMPTIONS)}"
        f"\n  stale: {sorted(CLOCK_HOLDER_EXEMPTIONS - holders)}"
    )


_EVERY_SHAPE = """
import time
import time as _t
import datetime as _dt
from datetime import datetime as _when
from datetime import date, datetime
from time import monotonic
from vultron.core.models._helpers import now_utc as _now
from vultron.core.models import _helpers

from pydantic import BaseModel, Field


class Stamped(BaseModel):
    at: datetime = Field(default_factory=_helpers.now_utc)


def reads(clock):
    clock.now()
    datetime.now()
    _dt.datetime.utcnow()
    date.today()
    time.time()
    monotonic()
    _t.perf_counter()
    _when.now()
    _now()
    from_now_utc(delta)
"""


@pytest.mark.spec("CS-13-002")
def test_the_finder_names_each_read_shape_and_not_a_port_read() -> None:
    found = Counter(reads_in_source(_EVERY_SHAPE, "m.py"))

    assert found == Counter(
        {
            ("m.py", "Stamped.at", "now_utc"): 1,
            ("m.py", "reads", "datetime.now"): 2,
            ("m.py", "reads", "datetime.utcnow"): 1,
            ("m.py", "reads", "time.perf_counter"): 1,
            ("m.py", "reads", "date.today"): 1,
            ("m.py", "reads", "time.time"): 1,
            ("m.py", "reads", "time.monotonic"): 1,
            ("m.py", "reads", "now_utc"): 1,
            ("m.py", "reads", "from_now_utc"): 1,
        }
    )
