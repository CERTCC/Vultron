#!/usr/bin/env python
"""Staging for an inbound activity and its inline objects (#3763, #4871).

The receiver keeps no copy of a received activity under the id its sender
chose (DL-06-006), and no record of an object the activity carries inline: a
case, note or embargo a sender inlines is a claim, and only the handler, after
its guards, writes the core record it gives rise to (CLP-10-017, CLP-10-019;
ADR-0111 as amended).  Writing them at receipt let a sender seed a case
replica ahead of the trust check that should refuse it (PCR-03-004,
CBT-01-011), and let a received ``Create`` read as one the receiver sent
(#4866).

Routing still needs the activity rebuilt through the store's read pipeline
(``_from_row`` → field expansion → semantic coercion), which is what turns
the parsed wire graph into the shape the patterns match.  So each delivery is
staged in a :class:`_StagingStore`: an in-memory store, emptied before and
after each use, that holds the activity's row and its inline objects' rows,
and answers any other read from the receiver's own store, so an object the
receiver already holds is always the one routing sees.  The rebuild reads the
activity from it, and nothing staged reaches the receiver's store.

An activity deferred until its case is known is replayed later, by id, after
the staging store has been emptied.  It is held for that replay in one
:class:`~vultron.core.models.deferred_inbox_activity.DeferredInboxActivity`
record (:meth:`InlineObjectStaging.hold_for_replay`), keyed by the receiver:
the received body the parser sealed, beside the staged inline rows
(IO-03-004).  The replay parses that body again, stages it with the held rows
and deletes the record (:meth:`InlineObjectStaging.rehydrate_deferred`).
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
from dataclasses import dataclass
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
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronNotFoundError,
    VultronValidationError,
    VultronWiringError,
)
from vultron.wire.as2.parser import parse_received_body
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
    activity itself is read only from the copy staged here: the receiver holds
    none under its sender's id (DL-06-006), and the read that rebuilds it
    resolves its references through the store that returned it.
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

    def staged_rows(
        self,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
        """Return the activity's staged row and every other row staged here."""
        with self._session() as session:
            rows = session.exec(select(VultronObjectRecord)).all()
            as_dicts: list[dict[str, object]] = [
                {"id_": row.id_, "type_": row.type_, "data_": row.data}
                for row in rows
            ]
        own = [row for row in as_dicts if row["id_"] == self._activity_id]
        inline = [row for row in as_dicts if row["id_"] != self._activity_id]
        return (own[0] if own else None), inline


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


def _row_record(row: dict[str, Any]) -> StorableRecord:
    """A held storage row, as the record ``create`` accepts."""
    return StorableRecord(
        id_=str(row["id_"]), type_=str(row["type_"]), data_=row["data_"]
    )


@dataclass(frozen=True)
class _Staged:
    """What one rebuild staged, kept so a deferral can hold it."""

    received_body: str | None
    activity_row: dict[str, object]
    inline_rows: list[dict[str, object]]


class InlineObjectStaging:
    """One actor's inbox staging: rebuild, hold for replay, release.

    Shared by the ingress adapters and the pending-case queue port of one
    inbox run, so a delivery the queue defers can hand what it staged to the
    replay that later routes it.

    Args:
        dl: The receiving actor's own DataLayer (ADR-0073).
    """

    def __init__(self, dl: DataLayer) -> None:
        self._dl = dl
        self._staged: dict[str, _Staged] = {}
        self._routed_in_place: dict[str, as_Activity] = {}
        self._released: dict[str, DeferredInboxActivity] = {}

    def note_routed_in_place(self, activity: as_Activity) -> None:
        """Remember a parsed *activity* routed without a staged rebuild.

        An ``Announce(CaseLedgerEntry)`` is hydrated in place, not rebuilt
        here (SYNC-13-003), but the inbox may still defer it; this keeps it
        so :meth:`hold_for_replay` can hold it whole.
        """
        self._routed_in_place[activity.id_] = activity

    def rehydrate_parsed(self, activity: as_Activity) -> as_Activity | None:
        """Rebuild the parsed *activity* with its own inline objects staged.

        The rebuilt copy carries no received evidence; the caller decides
        whether this delivery's evidence is the one to carry (VM-08-002).
        """

        return self._rehydrate_with(
            activity, received_body=activity.received_evidence_json
        )

    def rehydrate_resend(self, activity: as_Activity) -> as_Activity | None:
        """Rebuild a resend of a held activity from its own body, as no delivery.

        For a redelivery whose held copy does not rebuild: this delivery's
        body is routed in its place, but staged with no received body, so a
        resend deferred again is held as its row and its replay carries no
        evidence (VM-08-002).
        """

        return self._rehydrate_with(activity, received_body=None)

    def _rehydrate_with(
        self, activity: as_Activity, *, received_body: str | None
    ) -> as_Activity | None:
        """Rebuild *activity*, holding *received_body* as what arrived."""

        def _stage(store: DataLayer) -> None:
            store.create(object_to_record(activity))
            _stage_inline_object(store, activity)

        return self._rehydrate(
            activity.id_, _stage, received_body=received_body
        )

    def can_hold(self, activity_id: str) -> bool:
        """Whether this staging rebuilt or released *activity_id*, so it can
        hold it again (:meth:`hold_for_replay`)."""
        return (
            activity_id in self._released
            or activity_id in self._staged
            or activity_id in self._routed_in_place
        )

    def hold_again(self, activity_id: str) -> bool:
        """Hold *activity_id* again before it is re-queued, if this staging
        can (:meth:`can_hold`).

        A retry or a dead letter needs the record the rebuild released, or
        the retry finds nothing to rebuild (DL-06-006).  Returns whether a
        record was written.
        """
        if not self.can_hold(activity_id):
            return False
        return self.hold_for_replay(activity_id)

    def held(self, activity_id: str) -> DeferredInboxActivity | None:
        """The record holding *activity_id* for its replay, if any."""
        record = self._dl.read(DeferredInboxActivity.build_id(activity_id))
        return record if isinstance(record, DeferredInboxActivity) else None

    def rehydrate_held(self, activity_id: str) -> as_Activity | None:
        """Rebuild a held deferred activity, keeping the record.

        For a redelivery of an activity still waiting on its case: the held
        copy is routed (IE-10-001), with no received evidence, because the
        delivery being processed is not the one held (VM-08-002).
        """
        pending = self.held(activity_id)
        if pending is None:
            return None
        return self._rebuild_from(pending)[0]

    def rehydrate_archived(self, activity_id: str) -> as_Activity | None:
        """Rebuild an archived received activity from the body intake kept.

        For a redelivery of an activity intake already archived: the archived
        body is parsed and routed in place of the redelivered one
        (IE-10-001, ADR-0149), with no received evidence, because the
        delivery being processed is not the one archived (VM-08-002).
        Returns ``None`` when nothing is archived under *activity_id*.
        """
        record = self._dl.read(ReceivedActivityRecord.build_id(activity_id))
        if not isinstance(record, ReceivedActivityRecord):
            return None
        # Rebuilt from the archived body, but held, should this resend be
        # deferred, as no delivery's body: its replay must not carry the
        # first delivery's evidence (VM-08-002).
        return self._rehydrate_with(
            parse_received_body(record.received_body), received_body=None
        )

    def rehydrate_deferred(self, activity_id: str) -> as_Activity | None:
        """Rebuild a deferred activity from its record, and release it.

        A held received body is parsed again, so the replay carries the
        evidence the first delivery did (VM-08-002); an activity held as its
        row carries none.  The record is deleted once read: a replay the
        queue defers again holds it afresh (:meth:`hold_for_replay`).

        Returns ``None`` when nothing is held for *activity_id*: the receiver
        keeps no other copy of a received activity (DL-06-006).
        """
        pending = self.held(activity_id)
        if pending is None:
            logger.warning(
                "No deferred record holds activity %s; nothing to replay"
                " (DL-06-006).",
                activity_id,
            )
            return None
        # The replay has already taken the activity off the pending queue,
        # so the record is released even when the rebuild raises: no later
        # replay or queue expiry could reach it (CBT-03-003).  A caller that
        # queues it again holds it again (:meth:`hold_for_replay`), from the
        # record as it was read.
        self._released[activity_id] = pending
        try:
            result, parsed = self._rebuild_from(pending)
        finally:
            self._dl.delete(pending.type_, pending.id_)
        if result is not None and parsed is not None:
            evidence = parsed.received_evidence_json
            if evidence is not None:
                result.seal_received_evidence(evidence)
        return result

    def hold_for_replay(self, activity_id: str) -> bool:
        """Hold *activity_id* whole until its deferred replay.

        Writes one :class:`DeferredInboxActivity` from what this run staged
        for it: the sealed received body (or, with none, the activity's row)
        and the inline rows, and nothing derived from them (ADR-0149).  A
        record already held is kept as it is, so a redelivery of a deferred
        activity is not held again (IE-10-001).

        An activity this staging rebuilt from its record and released
        (:meth:`rehydrate_deferred`) is held again as that record was, so a
        replay deferred again, or re-queued after a failure, keeps the body it
        was first held with.

        Hold before queueing: the record is the only copy of the activity, so
        an id queued with nothing held would be silently dropped.

        Returns whether this call wrote the record.

        Raises:
            VultronWiringError: When this staging neither rebuilt nor released
                *activity_id*, so it has nothing to hold.
        """
        released = self._released.pop(activity_id, None)
        if released is not None:
            return self._create(released)
        staged = self._staged.get(activity_id)
        if staged is None and activity_id in self._routed_in_place:
            self.rehydrate_parsed(self._routed_in_place.pop(activity_id))
            staged = self._staged.get(activity_id)
        if staged is None:
            # The record is the only copy the receiver keeps (DL-06-006), so
            # queueing an id with nothing held for it would drop the activity.
            raise VultronWiringError(
                f"Nothing staged for deferred activity {activity_id!r} in this"
                " inbox run: the queue port and the ingress adapter must"
                " share one InlineObjectStaging"
            )
        activity_row_json = (
            json.dumps(staged.activity_row)
            if staged.received_body is None
            else None
        )
        return self._create(
            DeferredInboxActivity(
                activity_id=activity_id,
                received_body=staged.received_body,
                activity_row_json=activity_row_json,
                rows_json=json.dumps(staged.inline_rows),
            )
        )

    def _create(self, record: DeferredInboxActivity) -> bool:
        """Write *record* unless one is already held; return whether written."""
        try:
            self._dl.create(record)
        except VultronAlreadyExistsError:
            logger.debug(
                "Deferred activity %s is already held; keeping the held copy.",
                record.activity_id,
            )
            return False
        return True

    def _rebuild_from(
        self, pending: DeferredInboxActivity
    ) -> tuple[as_Activity | None, as_Activity | None]:
        """Rebuild *pending*'s activity; also return the body's parse."""
        inline_rows: list[dict[str, Any]] = json.loads(pending.rows_json)
        parsed: as_Activity | None = None
        if pending.received_body is not None:
            parsed = parse_received_body(pending.received_body)
            activity_record: StorableRecord | PersistableModel = (
                object_to_record(parsed)
            )
        else:
            assert pending.activity_row_json is not None  # validator
            activity_record = _row_record(
                json.loads(pending.activity_row_json)
            )

        def _restage(store: DataLayer) -> None:
            store.create(activity_record)
            for row in inline_rows:
                store.create(_row_record(row))

        result = self._rehydrate(
            pending.activity_id,
            _restage,
            received_body=pending.received_body,
        )
        return result, parsed

    def _rehydrate(
        self,
        activity_id: str,
        stage: Callable[[DataLayer], None],
        *,
        received_body: str | None,
    ) -> as_Activity | None:
        with _STAGING_LOCK:
            store = _StagingStore(self._dl, activity_id)
            store.clear_all()
            try:
                stage(store)
                activity_row, inline_rows = store.staged_rows()
                if activity_row is None:
                    raise VultronWiringError(
                        f"Staging for {activity_id!r} staged no row for the"
                        " activity itself, so there is nothing to rebuild"
                    )
                self._staged[activity_id] = _Staged(
                    received_body=received_body,
                    activity_row=activity_row,
                    inline_rows=inline_rows,
                )
                result = rehydrate(activity_id, dl=store)
            finally:
                store.clear_all()
        return result if isinstance(result, as_Activity) else None


__all__ = ["InlineObjectStaging"]
