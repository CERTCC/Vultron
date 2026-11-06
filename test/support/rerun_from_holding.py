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
from vultron.core.models.case_ledger_entry import CaseLedgerEntry


@dataclass(frozen=True)
class Effects:
    """What a store committed and queued, by content.

    Attributes:
        ledger: Every ledger entry the store holds, as JSON, in log order
            per case.
        outbox: Every activity the store's outbox holds, as JSON, keyed by
            its id, in queue order.
    """

    ledger: tuple[str, ...]
    outbox: tuple[tuple[str, str], ...]


def _dump(obj: Any) -> str:
    return json.dumps(obj.model_dump(mode="json"), sort_keys=True)


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
        (activity_id, _dump(dl.read(activity_id)))
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


__all__ = ["Effects", "Rerun", "effects", "rerun_from_holding"]
