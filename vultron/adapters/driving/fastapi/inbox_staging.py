#!/usr/bin/env python
"""Staging for the inline objects of an inbound activity (#3763).

A received activity is archived as it arrived (``inbox_storage``), but the
objects it carries inline are not the receiver's records: a case, note or
embargo a sender inlines is a claim, and only the handler, after its guards,
writes the core record it gives rise to (CLP-10-017, CLP-10-019; ADR-0111 as
amended).  Writing them at receipt let a sender seed a case replica ahead of
the trust check that should refuse it (PCR-03-004, CBT-01-011).

Routing still needs them.  The by-id re-read that rebuilds the routed
activity (``FastAPIIngressAdapter.rehydrate``) resolves ``object_`` from the
store it reads, and the stored activity holds that object as an id.  So each
delivery's inline objects are staged in a :class:`_StagingStore`: an
in-memory store, emptied before and after each use, that answers a read from
the receiver's own store first and from the staged rows only when that store
holds nothing under the id.  The re-read runs against it, and nothing staged
reaches the receiver's store.

An activity deferred until its case is known is replayed later, by id, after
the staging store has been emptied.  Its staged rows are held for that replay
in a :class:`~vultron.core.models.pending_inline_objects.PendingInlineObjects`
record (:meth:`InlineObjectStaging.hold_for_replay`), which the replay stages
again and deletes.
"""

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

import json
import logging
import threading
from collections.abc import Callable
from typing import Any, cast

from pydantic import ValidationError
from sqlmodel import select

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    VultronObjectRecord,
)
from vultron.adapters.driven.datalayer_sqlite.engine import scratch_memory_url
from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.pending_inline_objects import PendingInlineObjects
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)

#: Every actor's staging store is emptied around each use, so two uses must
#: never overlap.  The per-actor inbox lock already serialises a production
#: actor's deliveries; this lock also covers callers that run the pipeline
#: without it, as the tests do.
_STAGING_LOCK = threading.Lock()


class _StagingStore(SqliteDataLayer):
    """An in-memory store that reads through to the receiver's own store.

    Reads of anything but the activity being rebuilt go to *held* first, so
    an object the receiver already holds is always the one routing sees, as it
    was when ingress wrote inline objects and a duplicate was skipped.  The
    activity itself is read from the copy staged here, because the read that
    rebuilds it resolves its references through the store that returned it.
    """

    def __init__(self, held: DataLayer, activity_id: str) -> None:
        # Every SqliteDataLayer names its deployment and its actor; a store
        # that names neither still gets a staging store of its own.
        super().__init__(
            scratch_memory_url(
                getattr(held, "db_url", "sqlite:///:memory:"), "inbox-staging"
            ),
            actor_id=getattr(held, "actor_id", None) or "inbox-staging",
        )
        self._held = held
        self._activity_id = activity_id

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None:
        """Read from the receiver's store first, except for the activity."""
        if object_id != self._activity_id:
            held = self._held.read(object_id)
            if held is not None:
                return held
        return super().read(object_id, raise_on_missing)

    def staged_rows(self) -> list[dict[str, object]]:
        """Return every row staged here except the activity's own."""
        with self._session() as session:
            rows = session.exec(
                select(VultronObjectRecord).where(
                    VultronObjectRecord.id_ != self._activity_id
                )
            ).all()
            return [
                {"id_": row.id_, "type_": row.type_, "data_": row.data}
                for row in rows
            ]


def _stage_inline_object(store: DataLayer, activity: as_Activity) -> None:
    """Stage the inline nested ``object_`` of an inbox activity in *store*.

    Stages the class the parser produced for the inline object, unchanged.
    ``parse_activity`` already resolves every inline dict to its most specific
    wire class and refuses the activity when that class's validation fails
    (MV-04-003), so the parsed object graph is the authority for what arrived
    in each slot (MV-11-005).  The raw request body is received evidence
    (VM-08-002), not a second source to parse from: re-validating an inline
    object from it would see again the unknown keys the parse edge set aside
    (MV-11-003), fail on a core class's ``extra="forbid"``, and stage a less
    specific type in its place.  That is what the retired
    ``_reparse_as_specific_type`` did (#3922).

    Ledger entries are exempt: per SYNC-13-003 routing an
    ``Announce(CaseLedgerEntry)`` never depends on a stored entry, so
    ``FastAPIIngressAdapter.rehydrate`` carries the typed inline entry forward
    in memory instead (SYNC-13-002).

    Args:
        store: The delivery's staging store, never the receiver's own.
        activity: The parsed AS2 activity whose ``object_`` to stage.
    """
    nested = getattr(activity, "object_", None)
    if nested is None or isinstance(nested, str):
        return
    if not (
        hasattr(nested, "id_")
        and hasattr(nested, "type_")
        and nested.type_ is not None
        and not nested.type_.startswith("as_")
    ):
        return
    if nested.type_ == "CaseLedgerEntry":
        return

    typed_nested = cast(PersistableModel, nested)

    if isinstance(nested, VulnerabilityCase):
        # EMB-18-003: a case is staged only with the embargo it names, so the
        # rebuilt case never names one routing cannot read.  The handler then
        # refuses a case naming an embargo nobody holds, with nothing staged.
        try:
            store_carried_embargo(nested, store)
        except (VultronNotFoundError, VultronValidationError) as exc:
            logger.warning(
                "Not staging inline VulnerabilityCase %s from ingress: it"
                " names an active embargo this store cannot read"
                " (EMB-18-003): %s",
                getattr(nested, "id_", "<no id>"),
                exc,
            )
            return

    try:
        # Normalise case_participants to string IDs in the *serialised record*
        # so the staged VulnerabilityCase row carries only ID refs (#2233).
        # The Python object is never mutated — downstream BT nodes must see the
        # original inline objects so they can project them to core and create
        # standalone DataLayer records.
        record: StorableRecord | PersistableModel = object_to_record(
            typed_nested
        )
        if (
            hasattr(typed_nested, "case_participants")
            and isinstance(record, dict)
            and isinstance(record.get("case_participants"), list)
        ):
            record["case_participants"] = [
                (
                    entry["id_"]
                    if isinstance(entry, dict) and "id_" in entry
                    else entry
                )
                for entry in record["case_participants"]
                if isinstance(entry, (str, dict))
            ]
        store.create(record)
    except (VultronValidationError, ValidationError):
        # A shape/projection failure, NOT an "already exists" collision — the
        # object cannot be held in the canonical core shape at all (#2232).
        # Under ``extra="forbid"`` (#2940) that can surface as a bare Pydantic
        # ``ValidationError`` as well as a core guard's error.  Routing then
        # sees a bare id, so it is logged loudly rather than swallowed.
        logger.exception(
            "Not staging inline %s %s from ingress: it cannot be projected"
            " to the canonical core shape.",
            nested.type_,
            getattr(nested, "id_", "<no id>"),
        )
    except VultronAlreadyExistsError:
        logger.debug(
            "Inline object %s already staged; skipping.",
            getattr(nested, "id_", "<no id>"),
        )


def _stored_activity_row(
    held: DataLayer, activity_id: str
) -> StorableRecord | None:
    """Return the receiver's stored row for *activity_id*, as stored."""
    stored = held.read(activity_id)
    type_ = getattr(stored, "type_", None)
    if not isinstance(stored, as_Activity) or not isinstance(type_, str):
        return None
    row = held.get(table=type_, id_=activity_id)
    if not isinstance(row, dict):
        return None
    return StorableRecord(id_=activity_id, type_=type_, data_=row["data_"])


class InlineObjectStaging:
    """One actor's inbox staging: rebuild, hold for replay, release.

    Shared by the ingress adapters and the pending-case queue port of one
    inbox run, so a delivery the queue defers can hand its staged rows to the
    replay that later routes it.

    Args:
        dl: The receiving actor's own DataLayer (ADR-0073).
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl
        self._staged: dict[str, list[dict[str, object]]] = {}

    def rehydrate_parsed(self, activity: as_Activity) -> as_Activity | None:
        """Rebuild the stored *activity* with its own inline objects staged."""
        return self._rehydrate(
            activity.id_, lambda store: _stage_inline_object(store, activity)
        )

    def rehydrate_deferred(self, activity_id: str) -> as_Activity | None:
        """Rebuild a deferred activity with the rows held for its replay.

        The held rows are released once staged: a replay the queue defers
        again holds them afresh (:meth:`hold_for_replay`).
        """
        held_id = PendingInlineObjects.build_id(activity_id)
        pending = self._dl.read(held_id)
        rows: list[dict[str, Any]] = (
            json.loads(pending.rows_json)
            if isinstance(pending, PendingInlineObjects)
            else []
        )

        def _restage(store: DataLayer) -> None:
            for row in rows:
                store.create(
                    StorableRecord(
                        id_=str(row["id_"]),
                        type_=str(row["type_"]),
                        data_=row["data_"],
                    )
                )

        # The replay has already taken the activity off the pending queue,
        # so the held rows are released even when the rebuild raises: no
        # later replay or queue expiry could reach them (CBT-03-003).
        try:
            return self._rehydrate(activity_id, _restage)
        finally:
            if isinstance(pending, PendingInlineObjects):
                self._dl.delete(pending.type_, held_id)

    def hold_for_replay(self, activity_id: str) -> None:
        """Keep *activity_id*'s staged rows until its deferred replay."""
        rows = self._staged.get(activity_id)
        if not rows:
            return
        self._dl.save(
            PendingInlineObjects(
                activity_id=activity_id, rows_json=json.dumps(rows)
            )
        )

    def _rehydrate(
        self,
        activity_id: str,
        stage: Callable[[DataLayer], None],
    ) -> as_Activity | None:
        activity_row = _stored_activity_row(self._dl, activity_id)
        if activity_row is None:
            # Nothing stored to rebuild: the plain re-read reports that as it
            # always has.
            plain = rehydrate(activity_id, dl=self._dl)
            return plain if isinstance(plain, as_Activity) else None
        with _STAGING_LOCK:
            store = _StagingStore(self._dl, activity_id)
            store.clear_all()
            try:
                store.create(activity_row)
                stage(store)
                self._staged[activity_id] = store.staged_rows()
                result = rehydrate(activity_id, dl=store)
            finally:
                store.clear_all()
        return result if isinstance(result, as_Activity) else None
