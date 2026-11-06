"""One actor's inbox staging: rebuild, hold for replay, release.

:class:`InlineObjectStaging` stages a delivery's activity and inline objects
in the scratch store, rebuilds the activity through the store's read pipeline,
and holds a deferred activity for replay on the activity's one
``ReceivedActivityRecord`` (IO-03-009, ADR-0154).
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
from collections.abc import Callable
from typing import Any, cast

from pydantic import ValidationError

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.inbox_staging.store import (
    _STAGING_LOCK,
    _row_record,
    _Staged,
    _StagingStore,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.core.services.received_activity import (
    held_received_record,
    sealed_body_of,
)
from vultron.core.services.received_holding import (
    held_for_replay,
    hold_for_replay as hold_body_for_replay,
    release_from_holding,
)
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronNotFoundError,
    VultronValidationError,
    VultronWiringError,
)
from vultron.wire.as2.parser import parse_received_body
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
)

logger = logging.getLogger(__name__)


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
    if isinstance(nested, as_VulnerabilityCaseReference):
        # A case reference names a case and is no object to stage: the
        # activity row keeps it inline, and the case is read from the
        # receiver's store or not at all (ADR-0165).
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
        # The holding services take the narrow core port; the full DataLayer
        # satisfies it structurally but is not assignable to it, because
        # ``clone_for_actor`` returns the wider type (the cast every adapter
        # at this seam makes).
        self._store = cast(CasePersistence, dl)
        self._staged: dict[str, _Staged] = {}
        self._routed_in_place: dict[str, as_Activity] = {}
        self._released: dict[str, ReceivedActivityRecord] = {}

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
        whether this delivery's evidence is the one to carry (VM-08-007).
        """

        return self._rehydrate_with(
            activity, received_body=activity.received_evidence_json
        )

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

    def held(self, activity_id: str) -> ReceivedActivityRecord | None:
        """The record owing a replay of *activity_id*, if one does.

        Not every record holding the activity: only one whose replay the
        inbox still owes (ADR-0154).  An archived record with nothing owed is
        answered by :meth:`rehydrate_archived` instead, which is the
        distinction that decides whether a routed copy carries received
        evidence.
        """
        return held_for_replay(self._store, activity_id)

    def rehydrate_held(self, activity_id: str) -> as_Activity | None:
        """Rebuild a held activity, leaving the replay still owed.

        For a redelivery of an activity still waiting on its case: the held
        copy is routed (IE-10-001), with no received evidence, because the
        delivery being processed is not the one held (VM-08-010).
        """
        pending = self.held(activity_id)
        if pending is None:
            return None
        return self._rebuild_from(pending)[0]

    def rehydrate_archived(self, activity_id: str) -> as_Activity | None:
        """Rebuild an archived received activity from the body it holds.

        For a redelivery of an activity the receiver already holds: the held
        body is parsed and routed in place of the redelivered one
        (IE-10-001, ADR-0149).  It carries that body as its received
        evidence: the body is the first delivery's, sealed at its parse, so
        the copy routed is that delivery and not this one (VM-08-009).  Only
        a resend of exactly that body gets here; ingress refuses a different
        body under the same id before any copy is rebuilt (IE-10-002).  Held
        for a replay, should the copy be deferred, it keeps the same body.
        Returns ``None`` when the receiver holds nothing under
        *activity_id*.  It reads the one body-bearing record whatever stage
        that record is in, because the only caller reaches this branch when
        no replay is owed: an archived record, or a ``HELD`` one a run left
        with no verdict (CLP-10-074), whose body is the first delivery's
        either way.  The seen-before door of the tree that copy reaches
        answers it from that stage (ADR-0154).
        """
        record = held_received_record(self._store, activity_id)
        if record is None or record.is_receipt_stub:
            # A receipt stub holds no body to rebuild: a refusal gave it up
            # (CLP-10-018).
            return None
        archived = parse_received_body(sealed_body_of(record))
        evidence = archived.received_evidence_json
        result = self._rehydrate_with(archived, received_body=evidence)
        if result is not None and evidence is not None:
            result.seal_received_evidence(evidence)
        return result

    def rehydrate_deferred(self, activity_id: str) -> as_Activity | None:
        """Rebuild a held activity from its record, and release it.

        The held received body is parsed again, so the replay carries the
        evidence the first delivery did (VM-08-008).  The record goes once
        read, because a message owed a replay was never archived, so a
        replay the queue defers again holds it afresh
        (:meth:`hold_for_replay`), and the replay's seen-before door finds
        no record and lets it through (ADR-0154).

        Returns ``None`` when no replay is owed for *activity_id*: the
        receiver keeps no other copy of a received activity (DL-06-006).
        """
        pending = self.held(activity_id)
        if pending is None:
            logger.warning(
                "No held record owes a replay of activity %s; nothing to"
                " replay (DL-06-006).",
                activity_id,
            )
            return None
        # The replay has already taken the activity off the pending queue,
        # so the record is released even when the rebuild raises: no later
        # replay or queue expiry could reach it (CBT-03-003).  A caller that
        # queues it again holds it again (:meth:`hold_for_replay`), from the
        # record as it was read.  The queue drain runs the pop, this release
        # and its settlement in one transaction (IE-06-005), so a raise it
        # does not settle restores both the queued id and this record.
        self._released[activity_id] = pending
        try:
            result, parsed = self._rebuild_from(pending)
        finally:
            release_from_holding(self._store, activity_id)
        if result is not None:
            evidence = parsed.received_evidence_json
            if evidence is not None:
                result.seal_received_evidence(evidence)
        return result

    def hold_for_replay(
        self, activity_id: str, *, awaiting_case_id: str | None = None
    ) -> bool:
        """Hold *activity_id* whole until its deferred replay.

        Marks the activity's one
        :class:`~vultron.core.models.received_activity_record.ReceivedActivityRecord`
        as owing a replay, from what this run staged for it: the sealed
        received body and the inline rows, and nothing derived from them
        (ADR-0149).  A record already owing a replay is kept as it is, so a
        redelivery of a held activity is not held again (IE-10-001).
        *awaiting_case_id* names the case the activity waits on, when that is
        what it waits for (IO-03-009).

        An activity this staging rebuilt from its record and released
        (:meth:`rehydrate_deferred`) is held again as that record was, so a
        replay deferred again, or re-queued after a failure, keeps the body it
        was first held with.

        Hold before queueing: the record is the only copy of the activity, so
        an id queued with nothing held would be silently dropped.

        Returns whether this call wrote the record.

        Raises:
            VultronWiringError: When this staging neither rebuilt nor released
                *activity_id*, so it has nothing to hold, or when what it
                rebuilt carries no sealed body (VM-08-002).
        """
        released = self._released.pop(activity_id, None)
        if released is not None:
            return hold_body_for_replay(
                self._store,
                activity_id,
                sealed_body_of(released),
                replay_rows_json=released.replay_rows_json,
                awaiting_case_id=awaiting_case_id or released.awaiting_case_id,
            )
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
        if staged.received_body is None:
            # Every delivery is sealed at its parse (VM-08-002), and the
            # record holds the activity only as that body (ADR-0149).
            raise VultronWiringError(
                f"Deferred activity {activity_id!r} carries no sealed body to"
                " hold for its replay: only a parsed delivery can be deferred"
                " (VM-08-002)"
            )
        return hold_body_for_replay(
            self._store,
            activity_id,
            staged.received_body,
            replay_rows_json=json.dumps(staged.inline_rows),
            awaiting_case_id=awaiting_case_id,
        )

    def _rebuild_from(
        self, pending: ReceivedActivityRecord
    ) -> tuple[as_Activity | None, as_Activity]:
        """Rebuild *pending*'s activity; also return the body's parse."""
        inline_rows: list[dict[str, Any]] = json.loads(
            pending.replay_rows_json
        )
        body = sealed_body_of(pending)
        parsed = parse_received_body(body)
        activity_record = object_to_record(parsed)

        def _restage(store: DataLayer) -> None:
            store.create(activity_record)
            if not inline_rows:
                # Held inside the tree, where no staged rows exist: a body
                # the CASE_MANAGER holds for its sender's number
                # (SYNC-21-010) or a held ledger Announce.  Its inline
                # objects are staged from the body, as a first delivery's
                # are, so the replay is routed as that delivery was.
                _stage_inline_object(store, parsed)
            for row in inline_rows:
                store.create(_row_record(row))

        result = self._rehydrate(
            pending.activity_id,
            _restage,
            received_body=body,
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
                    inline_rows=inline_rows,
                )
                result = rehydrate(activity_id, dl=store)
            finally:
                store.clear_all()
        return result if isinstance(result, as_Activity) else None
