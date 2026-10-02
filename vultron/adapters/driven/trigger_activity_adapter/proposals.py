#!/usr/bin/env python

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

"""CaseProposal trigger activity methods for :class:`TriggerActivityAdapter`.

The ``Create(as_CaseProposal)`` a report receiver sends to a case-actor service,
the ``Accept``/``Reject`` the CASE_MANAGER answers with, and the prepared
``Create(VulnerabilityCase)`` it re-sends after a crash (CP-05, CP-09).
Split from ``cases.py`` at the CS-18-001 module-size cap.
"""

import logging
from typing import Any

from pydantic import ValidationError

from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.actor import CoreActor
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import (
    VultronActivityConstructionError,
    VultronAlreadyExistsError,
)
from vultron.wire.as2.factories.case import (
    accept_case_proposal_activity,
    create_case_proposal_activity,
    reject_case_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._base import _seal, _to_wire

logger = logging.getLogger(__name__)


class _ProposalsMixin:
    """CaseProposal round-trip methods (CP-05-002/003/004/005)."""

    _dl: CaseOutboxPersistence

    def create_case_proposal(
        self,
        actor: str,
        report_id: str,
        case_actor_id: str,
        summary: str | None = None,
        to: list[str] | None = None,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Create(as_CaseProposal)`` activity.

        Reads the ``as_VulnerabilityReport`` identified by ``report_id``,
        constructs an ``as_CaseProposal``, and persists
        ``Create(as_CaseProposal)`` to the DataLayer.

        ``offer_id``/``offer_actor_id`` are the report's offer provenance and are
        carried through when supplied (CP-01-007).  When this store holds the
        ``Offer(VulnerabilityReport)`` itself, it is carried whole under
        ``inReplyTo`` (CP-01-008): the case-actor has never seen it, and a
        sender inlines what it introduces (ADR-0107).  That is how the
        Reporter's proposed embargo terms reach case creation (EP-04-004).

        The sending actor's own profile, read from this store with its
        ``embargo_policy`` when it has published one, travels inline as the
        Create's ``actor`` (CP-01-010): it is the only place the CASE_MANAGER
        reads the CASE_OWNER's actor default from.

        Per CP-04-001, CP-04-002.

        Raises:
            ValueError: when the report, or the sending actor's own profile,
                is not in this store.
            TypeError: when the sending actor's record is not an actor.
        """
        report_obj = self._dl.read(report_id)
        if report_obj is None:
            raise ValueError(
                f"create_case_proposal: report '{report_id}' not found"
                " in DataLayer"
            )
        report = _to_wire(report_obj, as_VulnerabilityReport)
        # Before anything is persisted: a proposal without the profile would
        # be refused at the CASE_MANAGER's parse edge (CP-01-010).
        sender = self._sender_profile(actor)
        offer: as_Offer | None = None
        if offer_id is not None:
            stored_offer = self._dl.read(offer_id)
            if isinstance(stored_offer, as_Offer):
                offer = stored_offer
            else:
                logger.warning(
                    "create_case_proposal: offer '%s' for report '%s' is not"
                    " in this store as an Offer (got %s); the proposal carries"
                    " the bare provenance only (CP-01-007)",
                    offer_id,
                    report_id,
                    type(stored_offer).__name__,
                )
        proposal = as_CaseProposal(
            attributed_to=actor,
            object_=report,
            target=case_actor_id,
            summary=summary,
            offer_id=offer_id,
            offer_actor_id=offer_actor_id,
            in_reply_to=offer,
        )
        # Persist the proposal so the outbox expansion path can find it
        # when the as_Create activity is read back from the DataLayer.
        try:
            self._dl.create(proposal)
        except VultronAlreadyExistsError:
            logger.debug(
                "create_case_proposal: proposal '%s' already exists"
                " — skipping",
                proposal.id_,
            )
        recipients = to if to is not None else [case_actor_id]
        activity = create_case_proposal_activity(
            actor=sender,
            proposal=proposal,
            to=recipients,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "create_case_proposal: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def _sender_profile(self, actor_id: str) -> CoreActor | as_Actor:
        """Return *actor_id*'s own profile from this store (CP-01-010).

        Raises:
            ValueError: when the store holds no record for *actor_id*.
            TypeError: when the record for *actor_id* is not an actor.

        A proposal without the profile would be refused at the CASE_MANAGER's
        parse edge, so it is not built.
        """
        profile = self._dl.read(actor_id)
        if profile is None:
            raise ValueError(
                f"create_case_proposal: the proposing actor '{actor_id}' has"
                " no actor record in its own store to send inline as the"
                " Create's actor (CP-01-010)"
            )
        if not isinstance(profile, (CoreActor, as_Actor)):
            raise TypeError(
                f"create_case_proposal: the record for '{actor_id}' is a"
                f" {type(profile).__name__}, not an actor profile to send"
                " inline as the Create's actor (CP-01-010)"
            )
        return profile

    def reject_case_proposal(
        self,
        actor: str,
        proposal: dict,
        to: list[str] | None = None,
        summary: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(as_CaseProposal)`` activity.

        Rebuilds the ``as_CaseProposal`` from the wire dict the inbound
        ``Create`` carried, so the Reject embeds the proposal inline exactly as
        the vendor sent it (CP-05-004, AKM-03-001).

        The proposal is persisted alongside the activity for the same reason
        ``create_case_proposal`` persists it: storage dehydrates an inline
        Activity sub-field to its URI, so the outbox expansion path resolves the
        proposal by reading it back. Without the stored object the vendor would
        receive a Reject whose ``object_`` is a bare URI it cannot dereference —
        the AKM-03-001 failure that #2482 found on the Create side.  Storing an
        activity payload is not case state; declining still creates no case,
        participant, or ledger entry.

        Per CP-05-002, CP-05-004.
        """
        # `attributed_to` is a required `NonEmptyString` (CP-01-003), so a
        # proposal with no proposer is refused here rather than needing a
        # downstream guard for a case that cannot reach one.
        #
        # Wrapped as a VultronError, the way the sibling factory wraps its own
        # construction failures: the proposal is peer-supplied, so a malformed
        # one is a protocol outcome.  A bare ValidationError crosses the port
        # boundary as a non-VultronError, which BTBridge classifies as
        # internal_error=True — reporting someone else's bad message as a fault
        # in this service.
        try:
            wire_proposal = as_CaseProposal.model_validate(proposal)
        except ValidationError as exc:
            raise VultronActivityConstructionError(
                "reject_case_proposal: the proposal to embed is not a valid"
                " as_CaseProposal"
            ) from exc
        try:
            self._dl.create(wire_proposal)
        except VultronAlreadyExistsError:
            logger.debug(
                "reject_case_proposal: proposal '%s' already exists — skipping",
                wire_proposal.id_,
            )
        # The proposing vendor is the only party owed the refusal.
        recipients = (
            to if to is not None else [str(wire_proposal.attributed_to)]
        )
        extra: dict[str, Any] = {}
        if summary is not None:
            extra["summary"] = summary
        activity = reject_case_proposal_activity(
            actor_id=actor,
            proposal=wire_proposal,
            to=recipients,
            **extra,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "reject_case_proposal: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def accept_case_proposal(
        self,
        actor: str,
        proposal: dict,
        to: list[str],
        result: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(as_CaseProposal)`` activity.

        The CASE_MANAGER sends this to acknowledge that it will open (or has
        already opened) a case for the vendor's proposal (CP-05-002).  The
        proposal is embedded inline exactly as the vendor sent it (AKM-03-001),
        and *result* carries the URI of the case the Accept ties to — the
        existing case for a duplicate proposal (CP-05-006), the new one
        otherwise.
        """
        try:
            wire_proposal = as_CaseProposal.model_validate(proposal)
        except ValidationError as exc:
            raise VultronActivityConstructionError(
                "accept_case_proposal: the proposal to embed is not a valid"
                " as_CaseProposal"
            ) from exc
        # Persisted alongside the activity for the reason ``reject_case_proposal``
        # gives: storage dehydrates an inline sub-object to its URI, and a
        # read-back of the Accept should still show the proposal it answers.
        # Delivery does not depend on this — the sealed body carries the
        # proposal inline regardless (VM-08-003).
        try:
            self._dl.create(wire_proposal)
        except VultronAlreadyExistsError:
            logger.debug(
                "accept_case_proposal: proposal '%s' already exists — skipping",
                wire_proposal.id_,
            )
        extra: dict[str, Any] = {}
        if result is not None:
            extra["result"] = result
        activity = accept_case_proposal_activity(
            actor_id=actor,
            proposal=wire_proposal,
            to=to,
            **extra,
        )
        try:
            self._dl.create(activity)
        except VultronAlreadyExistsError:
            logger.warning(
                "accept_case_proposal: activity '%s' already exists — skipping",
                activity.id_,
            )
        return _seal(self._dl, activity)

    def emit_prepared_create_case(self, payload: dict) -> tuple[str, str]:
        """Persist and seal a ``Create(VulnerabilityCase)`` prepared earlier.

        The CASE_MANAGER pre-builds this activity when it writes the
        ``PendingCreateCaseActivity`` marker, so that a crash between the
        ``Accept`` and the ``Create`` can be recovered by re-sending the *same*
        activity under the *same* id (CP-05-005).  *payload* is that stored
        AS2 document.  Rebuilding it here rather than in the emitting node keeps
        the persist-and-seal step in the adapter, where every other outbound
        activity gets it, so the body the outbox delivers is the body sealed
        here (VM-08-003).

        Persisting is idempotent on the activity id: a replay after a crash
        finds the record already present and seals nothing new.
        """
        try:
            activity = VultronCreateCaseActivity.model_validate(payload)
        except ValidationError as exc:
            raise VultronActivityConstructionError(
                "emit_prepared_create_case: the stored payload is not a valid"
                " Create(VulnerabilityCase)"
            ) from exc
        if self._dl.read(activity.id_) is None:
            self._dl.create(activity)
        return _seal(self._dl, activity)
