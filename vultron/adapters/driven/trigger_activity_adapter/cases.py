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

"""Case-domain trigger activity construction for TriggerActivityAdapter."""

import logging
from typing import Any, cast

from pydantic import ValidationError

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.errors import VultronActivityConstructionError
from vultron.wire.as2.factories import (
    create_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.factories.case import (
    add_status_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_proposal_activity,
    reject_case_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ._base import _DUMP_KWARGS, _case_for_wire, _to_wire

logger = logging.getLogger(__name__)


class _CasesMixin:
    """Trigger activity methods for as_VulnerabilityCase objects."""

    _dl: CaseOutboxPersistence

    def create_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Create(as_VulnerabilityCase)`` activity."""
        case = _case_for_wire(self._dl, case_id)
        activity = create_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "create_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

    def engage_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(as_VulnerabilityCase)`` engage activity."""
        case = _case_for_wire(self._dl, case_id)
        activity = rm_engage_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "engage_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

    def defer_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``TentativeReject(as_VulnerabilityCase)`` activity."""
        case = _case_for_wire(self._dl, case_id)
        activity = rm_defer_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "defer_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

    def close_case(
        self,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Leave(as_VulnerabilityCase)`` close-case activity."""
        from vultron.wire.as2.factories import rm_close_case_activity

        case = _case_for_wire(self._dl, case_id)
        activity = rm_close_case_activity(case=case, actor=actor, to=to)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "close_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

    def reject_close_case(
        self,
        case_id: str,
        actor: str,
        close_sender: str,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Leave(VulnerabilityCase))`` activity.

        Declines an owner's close while an embargo is active (CM-23-011).
        The declined Leave is reconstructed from the case attributed to the
        ``close_sender`` (the Case Owner), then wrapped in an ``as:Reject``
        sent by ``actor`` (the Case Actor) back to the owner.  The inbound
        Leave is not yet persisted when this runs (``StoreActivityNode`` runs
        later in the tree), so the decline is threaded to it via
        ``in_reply_to`` rather than read back from the DataLayer.
        """
        from vultron.wire.as2.factories import (
            reject_close_case_activity,
            rm_close_case_activity,
        )

        case = _case_for_wire(self._dl, case_id)
        leave = rm_close_case_activity(case=case, actor=close_sender)
        kwargs: dict[str, Any] = {"actor": actor, "to": [close_sender]}
        if in_reply_to is not None:
            kwargs["in_reply_to"] = in_reply_to
        activity = reject_close_case_activity(leave=leave, **kwargs)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "reject_close_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

    def add_object_to_case(
        self,
        actor: str,
        object_id: str,
        case_id: str,
    ) -> tuple[str, str]:
        """Create and persist an ``Add(object, Case)`` activity."""
        case = _case_for_wire(self._dl, case_id)
        obj = cast(Any, self._dl.read(object_id))
        activity = as_Add(actor=actor, object_=obj, target=case)
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_object_to_case: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

    def add_case_status_to_case(
        self,
        status_id: str,
        case_id: str,
        actor: str,
        to: list[str] | None = None,
    ) -> str:
        """Create and persist an ``Add(CaseStatus, VulnerabilityCase)`` activity.

        Used by ``EmitAddCaseStatusToSelfNode`` to emit a self-addressed
        ``Add(CaseStatus)`` from the receiving actor to the CaseActor
        (RSH-01-003).  Returns the activity ID for outbox queueing.
        """
        status = _to_wire(self._dl.read(status_id), as_CaseStatus)
        case = _case_for_wire(self._dl, case_id)
        activity = add_status_to_case_activity(
            status=status, target=case, actor=actor, to=to
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "add_case_status_to_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

    def announce_vulnerability_case(
        self,
        case_id: str,
        actor: str,
        context_id: str,
        to: list[str],
    ) -> str:
        """Create and persist an ``Announce(as_VulnerabilityCase)`` activity.

        Reads the full case from the DataLayer, constructs the activity with
        the case inline, and persists it.  Returns the activity ID for outbox
        queueing.

        Per MV-10-003: the case owner sends this after an ``Accept(Invite)``
        is received and the invitee's embargo consent has been verified.

        Per CBT-01-007: all nested domain objects are embedded as full inline
        objects — bare URI string references MUST NOT be used.  Each report
        listed in ``case.vulnerability_reports`` is read from the DataLayer
        and embedded as a full ``as_VulnerabilityReport`` object so that
        receiving handlers (``SeedAnnouncedCaseNode``) can store the objects
        by iterating the embedded collection.
        """
        case = _case_for_wire(self._dl, case_id)
        embedded_reports: list[Any] = []
        for report_ref in case.vulnerability_reports:
            report_id = (
                report_ref
                if isinstance(report_ref, str)
                else getattr(report_ref, "id_", str(report_ref))
            )
            report_obj = _to_wire(
                self._dl.read(report_id), as_VulnerabilityReport
            )
            if report_obj is not None:
                embedded_reports.append(report_obj)
            else:
                logger.warning(
                    "announce_vulnerability_case: report '%s' not found in"
                    " DataLayer — embedding bare ref (CBT-01-007 degraded)",
                    report_id,
                )
                embedded_reports.append(report_ref)
        object.__setattr__(case, "vulnerability_reports", embedded_reports)
        activity = announce_vulnerability_case_activity(
            case=case,
            actor=actor,
            context=context_id,
            to=to,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "announce_vulnerability_case: activity '%s' already exists"
                " — skipping",
                activity.id_,
            )
        return activity.id_

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
        carried through when supplied (CP-01-007).

        Per CP-04-001, CP-04-002.
        """
        from vultron.wire.as2.vocab.objects.case_proposal import (
            as_CaseProposal,
        )

        report_obj = self._dl.read(report_id)
        if report_obj is None:
            raise ValueError(
                f"create_case_proposal: report '{report_id}' not found"
                " in DataLayer"
            )
        report = _to_wire(report_obj, as_VulnerabilityReport)
        proposal = as_CaseProposal(
            attributed_to=actor,
            object_=report,
            target=case_actor_id,
            summary=summary,
            offer_id=offer_id,
            offer_actor_id=offer_actor_id,
        )
        # Persist the proposal so the outbox expansion path can find it
        # when the as_Create activity is read back from the DataLayer.
        try:
            self._dl.create(proposal)
        except ValueError:
            logger.debug(
                "create_case_proposal: proposal '%s' already exists"
                " — skipping",
                proposal.id_,
            )
        recipients = to if to is not None else [case_actor_id]
        activity = create_case_proposal_activity(
            actor_id=actor,
            proposal=proposal,
            to=recipients,
        )
        try:
            self._dl.create(activity)
        except ValueError:
            logger.warning(
                "create_case_proposal: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)

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
        from vultron.wire.as2.vocab.objects.case_proposal import (
            as_CaseProposal,
        )

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
        except ValueError:
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
        except ValueError:
            logger.warning(
                "reject_case_proposal: activity '%s' already exists — skipping",
                activity.id_,
            )
        return activity.id_, activity.model_dump_json(**_DUMP_KWARGS)
