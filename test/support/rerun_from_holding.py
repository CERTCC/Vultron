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

"""Run a received message again from holding, and compare what it did.

A run that ends with no verdict, or a crash before the inbox's outcome stage,
leaves the message's record in holding, and the next delivery runs the
handling tree again from the body held (ADR-0154, CLP-10-074).  Every
handling tree must tolerate that re-run: nothing committed or sent twice.

:func:`rerun_from_holding` runs one received event twice on one store, as the
inbox would with the outcome stage's write lost in between, and returns what
the store committed and queued after each run, by content
(:class:`Effects`), so a test compares the two rather than a count.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from test.support.ledger_rebuild import run_use_case
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.received_activity_record import HOLDING_STAGES
from vultron.core.services.received_activity import (
    held_received_record,
    sealed_body_of,
)
from vultron.core.services.received_holding import (
    hold_for_replay,
    release_from_holding,
)


@dataclass(frozen=True)
class Effects:
    """What a store committed and queued, by content.

    Attributes:
        ledger: Every ledger entry the store holds, as JSON, in log order
            per case.
        outbox: Every activity the store's outbox holds, as its sealed
            body's JSON, keyed by its id, in queue order.
    """

    ledger: tuple[str, ...]
    outbox: tuple[tuple[str, str], ...]


def _dump(obj: Any) -> str:
    return json.dumps(obj.model_dump(mode="json"), sort_keys=True)


def _queued_body(dl: SqliteDataLayer, activity_id: str) -> str:
    """The body the outbox sends for *activity_id*: its sealed body.

    The sealed body is what is delivered (OX-07-001); an item queued with
    none is compared by the stored activity instead.
    """
    sealed = read_sealed_body_dict(dl, activity_id)
    if sealed is not None:
        return json.dumps(sealed, sort_keys=True)
    return _dump(dl.read(activity_id))


def effects(dl: SqliteDataLayer) -> Effects:
    """What *dl* has committed and queued, by content."""
    entries = sorted(
        (
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ),
        key=lambda e: (str(e.case_id), e.log_index),
    )
    outbox = tuple(
        (activity_id, _queued_body(dl, activity_id))
        for activity_id in dl.outbox_list()
    )
    return Effects(ledger=tuple(_dump(e) for e in entries), outbox=outbox)


@dataclass(frozen=True)
class Rerun:
    """The two runs of one message from holding, and what each left."""

    first: Any
    second: Any
    after_first: Effects
    after_second: Effects

    @property
    def doubled(self) -> list[str]:
        """What the second run committed or queued that the first did not."""
        new_entries = sorted(
            set(self.after_second.ledger) - set(self.after_first.ledger)
        )
        new_queued = sorted(
            set(self.after_second.outbox) - set(self.after_first.outbox)
        )
        return [f"ledger: {e}" for e in new_entries] + [
            f"outbox: {activity_id}" for activity_id, _ in new_queued
        ]


def rerun_from_holding(
    dl: SqliteDataLayer,
    event: Any,
    *,
    run: Callable[[SqliteDataLayer, Any], Any] = run_use_case,
) -> Rerun:
    """Run *event* on *dl*, then again with its record left in holding.

    Nothing settles the record between the runs, as when the inbox's outcome
    stage never ran: the second run is the re-run from holding a crash
    leaves to the next delivery (ADR-0154).
    """
    first = run(dl, event)
    after_first = effects(dl)
    second = run(dl, event)
    return Rerun(
        first=first,
        second=second,
        after_first=after_first,
        after_second=effects(dl),
    )


@dataclass(frozen=True)
class ReplayAfterRerun:
    """A re-run from holding, held for a replay, then the replay."""

    rerun: Rerun
    replay: Any
    after_replay: Effects

    @property
    def doubled(self) -> list[str]:
        """What the re-run or the replay committed or queued anew."""
        return Rerun(
            first=self.rerun.first,
            second=self.replay,
            after_first=self.rerun.after_first,
            after_second=self.after_replay,
        ).doubled


def rerun_then_replay(
    dl: SqliteDataLayer,
    event: Any,
    *,
    run: Callable[[SqliteDataLayer, Any], Any] = run_use_case,
) -> ReplayAfterRerun:
    """Run *event*, re-run it from holding, hold it for a replay, replay it.

    The re-run's own run then ends in a hold, as when it raises and the
    inbox's retry holds it (``hold_for_replay`` moves the ``HANDLED`` record
    back to ``HELD``, owing a replay).  The replay releases the record, which
    deletes it (``release_from_holding``), and runs the body as a delivery of
    its own: intake records it afresh, so the replay reads as a first run
    and its once-only answers are not skipped (ADR-0154).
    """
    rerun = rerun_from_holding(dl, event, run=run)
    record = held_received_record(dl, event.activity_id)
    assert record is not None and record.stage in HOLDING_STAGES, record
    assert hold_for_replay(dl, event.activity_id, sealed_body_of(record))
    released = release_from_holding(dl, event.activity_id)
    assert released is not None
    assert held_received_record(dl, event.activity_id) is None
    replay = run(dl, event)
    return ReplayAfterRerun(
        rerun=rerun, replay=replay, after_replay=effects(dl)
    )


def deliver_outbox(dl: SqliteDataLayer) -> None:
    """Empty *dl*'s outbox, as a drain that delivered every item does."""
    while dl.outbox_pop() is not None:
        pass


@dataclass(frozen=True)
class DrainedRerun:
    """A first run whose sends were delivered, then a later run, by content.

    Attributes:
        first: The first run's verdict.
        after_first: What the store held after the first run, undelivered.
        delivered: What it held once the outbox was delivered.
        last: The later run's verdict.
        after_last: What it held after the later run.
        rerun_queued: With a replay, what the re-run queued before it was
            delivered in turn.
    """

    first: Any
    after_first: Effects
    delivered: Effects
    last: Any
    after_last: Effects
    rerun_queued: tuple[tuple[str, str], ...] = ()

    @property
    def sent_again(self) -> list[str]:
        """What a later run committed anew or queued after the delivery."""
        new_entries = sorted(
            set(self.after_last.ledger) - set(self.delivered.ledger)
        )
        queued = (*self.rerun_queued, *self.after_last.outbox)
        return [f"ledger: {e}" for e in new_entries] + [
            f"outbox: {activity_id} {_kind(body)}"
            for activity_id, body in queued
        ]


def _kind(body: str) -> str:
    """``Type(ObjectType)`` of a queued body, for a readable failure."""
    sent = json.loads(body)
    obj = sent.get("object")
    if not isinstance(obj, dict):
        return f"{sent.get('type')}(ref)"
    entry = obj.get("semanticType")
    inner = f"{obj.get('type')}:{entry}" if entry else obj.get("type")
    return f"{sent.get('type')}({inner})"


def drained_rerun(
    dl: SqliteDataLayer,
    event: Any,
    *,
    replay: bool,
    run: Callable[[SqliteDataLayer, Any], Any] = run_use_case,
) -> DrainedRerun:
    """Run *event*, deliver the outbox, then run it again from holding.

    The inbox drains the outbox after every delivery's work, even work that
    raised (``_run_serialised``), and the outbox monitor may deliver before
    a crash, so a later run may find the first run's sends already gone.
    With *replay*, the re-run is delivered too and then held for a replay,
    as a re-run that raised is held for its retry, and the replay runs with
    its record released (:func:`rerun_then_replay`).
    """
    first = run(dl, event)
    after_first = effects(dl)
    deliver_outbox(dl)
    delivered = effects(dl)
    last = run(dl, event)
    rerun_queued: tuple[tuple[str, str], ...] = ()
    if replay:
        rerun_queued = effects(dl).outbox
        deliver_outbox(dl)
        record = held_received_record(dl, event.activity_id)
        assert record is not None and record.stage in HOLDING_STAGES, record
        assert hold_for_replay(dl, event.activity_id, sealed_body_of(record))
        assert release_from_holding(dl, event.activity_id) is not None
        last = run(dl, event)
    return DrainedRerun(
        first=first,
        after_first=after_first,
        delivered=delivered,
        last=last,
        after_last=effects(dl),
        rerun_queued=rerun_queued,
    )


__all__ = [
    "DrainedRerun",
    "Effects",
    "ReplayAfterRerun",
    "Rerun",
    "deliver_outbox",
    "drained_rerun",
    "effects",
    "rerun_from_holding",
    "rerun_then_replay",
]
