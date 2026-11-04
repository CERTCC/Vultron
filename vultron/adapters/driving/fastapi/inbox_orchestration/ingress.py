"""Inbox ingress adapter: parse (wire) and rehydrate (staged) one delivery.

:class:`FastAPIIngressAdapter` implements the
:mod:`vultron.core.behaviors.inbox` ingress protocol, with the helpers that
carry received evidence and refuse a reused activity id with a different
body.
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

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Literal

from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import VultronReusedActivityIdError, VultronWiringError
from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.parser import parse_activity as _parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

logger = logging.getLogger(__name__)


def _is_inline_ledger_entry_announce(activity: as_Activity) -> bool:
    """Return True for an ``Announce`` carrying an inline ``CaseLedgerEntry``.

    Used to select the in-memory rehydration path that does not depend on the
    entry being pre-stored (SYNC-13-002/003).  Detected structurally via the
    inline object's ``type_`` so no domain import is needed here.
    """
    if getattr(activity, "type_", None) != "Announce":
        return False
    nested = getattr(activity, "object_", None)
    return getattr(nested, "type_", None) == "CaseLedgerEntry"


def _carry_received_evidence(
    artifact: as_Activity, routing_copy: as_Activity
) -> as_Activity:
    """Give the hydrated routing copy (B) its artifact's (A) received evidence.

    The rebuild reads B back through the store's read pipeline, which never
    keeps the body, so without this the evidence sealed at parse would stop at
    the first pipeline step and core would only ever see the rebuilt form
    (VM-08-002, ISSUE-3584).
    The evidence is the artifact's; B only carries it, which is why the text is
    copied rather than re-derived from B.
    """
    evidence = artifact.received_evidence_json
    if evidence is not None:
        routing_copy.seal_received_evidence(evidence)
    return routing_copy


@dataclass(frozen=True)
class _HeldBody:
    """The sealed body the receiver holds for an activity id, and where."""

    kind: Literal["deferred", "archived"]
    body: str


def _sender_id(activity: as_Activity) -> str | None:
    """The id of the actor *activity* names as its sender, if any."""
    actor = activity.actor
    if actor is None:
        return None
    return str(getattr(actor, "id_", actor))


def _body_digest(sealed_text: str) -> str:
    """The SHA-256 digest of a sealed received text (IE-10-002)."""
    return hashlib.sha256(sealed_text.encode("utf-8")).hexdigest()


def _refuse_a_different_body(activity: as_Activity, held: _HeldBody) -> None:
    """Refuse *activity* unless its sealed body is exactly *held*'s.

    The match is exact, digest against digest, with no normalisation
    (IE-10-002).  A same-body delivery returns, to be routed as a
    redelivery (IE-10-001).

    Raises:
        VultronWiringError: When *activity* carries no sealed body.  Every
            delivery the inbox parses is sealed (VM-08-002), so only an
            activity handed to the inbox in process can lack one.
        VultronReusedActivityIdError: When the bodies differ.  It is logged
            here, at WARNING, with the activity id and the sender.
    """
    evidence = activity.received_evidence_json
    if evidence is None:
        raise VultronWiringError(
            f"a delivery of held activity '{activity.id_}' carries no sealed"
            " body, so it cannot be compared with the held one (VM-08-002,"
            " IE-10-002)"
        )
    if _body_digest(evidence) == _body_digest(held.body):
        return
    sender = _sender_id(activity)
    logger.warning(
        "FastAPIIngressAdapter.rehydrate: refusing activity %s (actor %s):"
        " its id is already held (%s) with a different body, so neither"
        " body is routed and nothing is written (IE-10-002 to IE-10-005).",
        activity.id_,
        sender,
        held.kind,
    )
    raise VultronReusedActivityIdError(activity.id_, sender)


class FastAPIIngressAdapter:
    """Ingress adapter for the FastAPI driving adapter.

    ``parse`` parses a raw JSON request-body dict into a typed
    ``as_Activity``.  It writes nothing to the receiving actor's DataLayer
    (ADR-0073: the ``dl`` handed in is already one actor's own): not the
    activity, which the receiver never holds under the id its sender chose
    (DL-06-006), and not the objects it carries inline, from which only the
    handler, after its guards, writes a record (CLP-10-017, #3763).  Intake
    archives the activity under the receiver's key once it is routed.

    ``rehydrate`` rebuilds the parsed activity with it and its inline objects
    staged in a throwaway store (:mod:`.inbox_staging`).  A redelivery is
    detected there, from what the receiver holds under a key it derives from
    the activity id (IE-10-001): the deferred record when the first delivery
    is still waiting on its case, else intake's ``ReceivedActivityRecord``.

    Args:
        dl: The receiving actor's own DataLayer, read to rebuild the activity.
        staging: The inbox run's inline-object staging, shared with its queue
            port so a deferred delivery is held whole for replay.
    """

    def __init__(
        self, dl: DataLayer, staging: InlineObjectStaging | None = None
    ) -> None:
        self._dl = dl
        self._staging = staging or InlineObjectStaging(dl)

    def parse(
        self,
        payload: dict[str, Any] | bytes | str | Any,
    ) -> as_Activity | None:
        """Parse *payload* as an AS2 activity, writing nothing.

        Returns ``None`` on parse failure; never raises.
        """
        if isinstance(payload, as_Activity):
            # Already parsed (e.g., passed directly from the router DI).
            return payload

        if not isinstance(payload, dict):
            logger.warning(
                "FastAPIIngressAdapter.parse: unsupported payload type %s",
                type(payload).__name__,
            )
            return None

        try:
            return _parse_activity(payload)
        except VultronParseError as exc:
            logger.warning(
                "FastAPIIngressAdapter.parse: parse failed — %s", exc
            )
            return None

    def rehydrate(self, activity: as_Activity) -> as_Activity:
        """Resolve nested object references for the activity.

        For most activities this stages the parsed activity's row and its
        inline objects in a throwaway store and reads the activity back by id
        through the canonical DataLayer pipeline (``_from_row`` → field
        expansion → semantic coercion).  The staging store reads through to
        the receiver's own store for every other id, so an object the
        receiver already holds is the one routing sees
        (:class:`~.inbox_staging.InlineObjectStaging`).  Nothing staged
        reaches the receiver's store (DL-06-006, IO-03-004).

        When the receiver already holds the activity id, under a key it
        derives from it, this delivery's sealed body is compared with the
        body held for it first, by the SHA-256 digest of each text, exactly
        (IE-10-002, #3762):

        - a different body is not a redelivery: it is refused with
          :exc:`~vultron.errors.VultronReusedActivityIdError`, logged at
          WARNING with the activity id and the sender.  Neither body is
          routed and nothing is written, so the held record stays as it was.
          No normalisation precedes the match, so a body re-serialized with
          another key order is refused too (IE-10-002 ``note:``);
        - the same body is a redelivery, routed in place of this one as the
          copy the receiver already holds (VM-08-009, VM-08-010, IE-10-001).  When the
          first delivery is still deferred, its held copy is routed without
          received evidence, and the record holding it is kept for the
          replay, which carries it.  When intake already archived it, the
          archived body is parsed and routed (ADR-0149) with that body as its
          received evidence: it is the first delivery's sealed body.  The
          handlers' own idempotency guards answer the repeat (ID-04): a
          committed act is ``SKIPPED``, and an act that never committed, such
          as one that failed, runs as a first delivery and commits with the
          archived body (ADR-0151).

        Production deliveries always carry a sealed body, and a held record
        always holds one, so meeting either side without one is a wiring
        fault (ARCH-15-001), as is a held copy that does not rebuild: it is
        the same text as this delivery's.

        An ``Announce(CaseLedgerEntry)`` is the exception to the staged
        rebuild: per SYNC-13-002 the inline entry is deliberately NOT staged,
        so a by-ID re-read would collapse ``object_`` to a bare ID string and
        mis-route the message (SYNC-13-004).  For that case the already-typed
        in-memory activity is hydrated in place (:meth:`DataLayer.hydrate`
        expands any scalar/list ID references) and returned, so routing sees
        the typed ``CaseLedgerEntry`` without the adapter ever writing the
        ledger.

        The same hazard bit ``Create(CaseProposal)``, which inlines the
        vulnerability report inside the proposal (CP-01-004): the report was never
        staged, so the by-ID re-read collapsed it and the receiver had no report
        (#2482). That is fixed neither here nor at ingress, but in *storage*: the
        proposal declares ``object_`` in ``inline_required_refs``, so persistence
        keeps the report inline instead of dehydrating it to an id that nothing
        could resolve. The re-read is correct once the staged row is faithful to
        what the sender inlined.

        Resist adding activity types to the exception above. An in-place hydration
        skips the wire→core normalisation the by-ID path performs, so routing
        downstream sees `as_`-prefixed types and fails with "Expected
        VulnerabilityCase, got as_VulnerabilityCase". Fix what the store keeps, not
        the read.
        """
        held = self._held_body(activity.id_)
        if held is not None:
            _refuse_a_different_body(activity, held)

        if _is_inline_ledger_entry_announce(activity):
            # A repeat entry is the SYNC-12-003 already-stored gate's to
            # answer, not this adapter's (SYNC-13-004).  The inbox may still
            # defer it, so the staging keeps it to hold for the replay.
            self._staging.note_routed_in_place(activity)
            return _carry_received_evidence(
                activity, self._hydrate_in_place(activity)
            )

        if held is None:
            result = self._staging.rehydrate_parsed(activity)
            if result is None:
                return activity
            return _carry_received_evidence(activity, result)

        routed = (
            self._staging.rehydrate_held(activity.id_)
            if held.kind == "deferred"
            else self._staging.rehydrate_archived(activity.id_)
        )
        if routed is None:
            # The held copy is this delivery's own text, so this body would
            # not rebuild either.
            raise VultronWiringError(
                f"redelivered activity '{activity.id_}' is held"
                f" ({held.kind}) but its held copy does not rebuild"
            )
        self._log_redelivery(activity, held.kind)
        return routed

    def _held_body(self, activity_id: str) -> _HeldBody | None:
        """The body held for *activity_id* under the receiver's key, if any.

        The deferred record's while the first delivery is still deferred,
        else the body intake archived (IE-10-001, IE-10-002).
        """
        pending = self._staging.held(activity_id)
        if pending is not None:
            return _HeldBody("deferred", pending.received_body)
        record = self._dl.read(ReceivedActivityRecord.build_id(activity_id))
        if isinstance(record, ReceivedActivityRecord):
            return _HeldBody("archived", record.received_body)
        return None

    @staticmethod
    def _log_redelivery(activity: as_Activity, kind: str) -> None:
        evidence = (
            "with the archived body as its received evidence"
            if kind == "archived"
            else "without received evidence"
        )
        logger.info(
            "FastAPIIngressAdapter.rehydrate: activity %s (actor %s) is"
            " already held (%s); routing the held copy, %s"
            " (IE-10-001, VM-08-002).",
            activity.id_,
            _sender_id(activity),
            kind,
            evidence,
        )

    def _hydrate_in_place(self, activity: as_Activity) -> as_Activity:
        """Expand reference fields on the *parsed* activity, without a re-read."""
        try:
            hydrated = self._dl.hydrate(activity)
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3326  # pragma: no cover - defensive
            logger.warning(
                "FastAPIIngressAdapter.rehydrate: hydrate failed (%s);"
                " returning parsed activity unchanged.",
                exc,
            )
            return activity
        if isinstance(hydrated, as_Activity):
            return hydrated
        return activity
