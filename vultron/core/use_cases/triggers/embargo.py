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

"""
Class-based use cases for embargo-level trigger behaviors.

No HTTP framework imports permitted here.
"""

import logging

from transitions import MachineError

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.states.em import EM, EMAdapter, create_em_machine
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    find_embargo_proposal,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    EvaluateEmbargoTriggerRequest,
    ProposeEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import (
    VultronConflictError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.activities.embargo import (
    AnnounceEmbargoActivity,
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

logger = logging.getLogger(__name__)


class SvcProposeEmbargoUseCase:
    """Propose an embargo on a case."""

    def __init__(
        self, dl: DataLayer, request: ProposeEmbargoTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: ProposeEmbargoTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        end_time = request.end_time
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.as_id

        case = resolve_case(case_id, dl)

        em_state = case.current_status.em_state

        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            adapter.propose()
        except MachineError:
            raise VultronConflictError(
                f"Cannot propose embargo: case '{case.as_id}' EM state"
                f" '{em_state}' does not allow a PROPOSE transition."
            )

        new_em_state = EM(adapter.state)

        embargo_kwargs: dict = {"context": case.as_id}
        if end_time is not None:
            embargo_kwargs["end_time"] = end_time

        embargo = EmbargoEvent(**embargo_kwargs)

        try:
            dl.create(embargo)
        except ValueError:
            logger.warning("EmbargoEvent '%s' already exists", embargo.as_id)

        proposal = EmProposeEmbargoActivity(
            actor=actor_id,
            object=embargo.as_id,
            context=case.as_id,
        )

        try:
            dl.create(proposal)
        except ValueError:
            logger.warning(
                "EmProposeEmbargoActivity '%s' already exists", proposal.as_id
            )

        case.current_status.em_state = new_em_state
        if new_em_state != em_state:
            logger.info(
                "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s)",
                actor_id,
                embargo.as_id,
                case.as_id,
                em_state,
                new_em_state,
            )
        else:
            logger.info(
                "Actor '%s' counter-proposed embargo '%s' on case '%s'"
                " (EM %s, no state change)",
                actor_id,
                embargo.as_id,
                case.as_id,
                em_state,
            )

        case.proposed_embargoes.append(embargo.as_id)
        dl.update(case.as_id, object_to_record(case))

        add_activity_to_outbox(actor_id, proposal.as_id, dl)

        activity = proposal.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}


class SvcEvaluateEmbargoUseCase:
    """Accept an embargo proposal (evaluate-embargo)."""

    def __init__(
        self, dl: DataLayer, request: EvaluateEmbargoTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: EvaluateEmbargoTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        proposal_id = request.proposal_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.as_id

        case = resolve_case(case_id, dl)

        if proposal_id:
            proposal_raw = dl.read(proposal_id)
            if proposal_raw is None:
                raise VultronNotFoundError("EmbargoProposal", proposal_id)
            proposal = proposal_raw
        else:
            proposal = find_embargo_proposal(case.as_id, dl)
            if proposal is None:
                raise VultronNotFoundError(
                    "EmbargoProposal",
                    f"(pending for case '{case.as_id}')",
                )

        if str(getattr(proposal, "as_type", "")) != "Invite":
            raise VultronValidationError(
                f"Expected an Invite (embargo proposal), got "
                f"{type(proposal).__name__}."
            )

        embargo_ref = getattr(proposal, "as_object", None)
        embargo_id = (
            embargo_ref
            if isinstance(embargo_ref, str)
            else getattr(embargo_ref, "as_id", None)
        )
        if not embargo_id:
            raise VultronValidationError(
                "Proposal is missing an embargo event reference."
            )

        embargo = dl.read(embargo_id)
        if embargo is None or str(getattr(embargo, "as_type", "")) != "Event":
            raise VultronValidationError(
                f"Could not resolve EmbargoEvent '{embargo_id}'."
            )

        accept = EmAcceptEmbargoActivity(
            actor=actor_id,
            object=proposal.as_id,
            context=case.as_id,
        )

        try:
            dl.create(accept)
        except ValueError:
            logger.warning(
                "EmAcceptEmbargoActivity '%s' already exists", accept.as_id
            )

        case.set_embargo(embargo_id)
        case.current_status.em_state = EM.ACTIVE
        dl.update(case.as_id, object_to_record(case))

        add_activity_to_outbox(actor_id, accept.as_id, dl)

        logger.info(
            "Actor '%s' accepted embargo proposal '%s'; activated embargo '%s' "
            "on case '%s' (EM → ACTIVE)",
            actor_id,
            proposal.as_id,
            embargo_id,
            case.as_id,
        )

        activity = accept.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}


class SvcTerminateEmbargoUseCase:
    """Terminate the active embargo on a case."""

    def __init__(
        self, dl: DataLayer, request: TerminateEmbargoTriggerRequest
    ) -> None:
        self._dl = dl
        self._request: TerminateEmbargoTriggerRequest = request

    def execute(self) -> dict:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.as_id

        case = resolve_case(case_id, dl)

        if case.active_embargo is None:
            raise VultronConflictError(
                f"Case '{case.as_id}' has no active embargo to terminate."
            )

        em_state = case.current_status.em_state
        adapter = EMAdapter(em_state)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_state)

        try:
            adapter.terminate()
        except MachineError:
            raise VultronConflictError(
                f"Cannot terminate embargo: case '{case.as_id}' EM state"
                f" '{em_state}' does not allow a TERMINATE transition."
            )

        embargo_id = (
            case.active_embargo
            if isinstance(case.active_embargo, str)
            else case.active_embargo.as_id
        )

        announce = AnnounceEmbargoActivity(
            actor=actor_id,
            object=embargo_id,
            context=case.as_id,
        )

        try:
            dl.create(announce)
        except ValueError:
            logger.warning(
                "AnnounceEmbargoActivity '%s' already exists", announce.as_id
            )

        case.current_status.em_state = EM(adapter.state)
        case.active_embargo = None
        dl.update(case.as_id, object_to_record(case))

        add_activity_to_outbox(actor_id, announce.as_id, dl)

        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (EM %s → %s)",
            actor_id,
            embargo_id,
            case.as_id,
            em_state,
            adapter.state,
        )

        activity = announce.model_dump(by_alias=True, exclude_none=True)
        return {"activity": activity}
