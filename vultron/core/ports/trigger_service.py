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

"""Inbound (driving) port — actor-initiated trigger operations.

:class:`TriggerServicePort` is the Protocol that all adapters (FastAPI, CLI,
MCP) type-hint against.  Tests inject ``Mock(spec=TriggerServicePort)`` at
the ``get_trigger_service`` dependency.

The concrete implementation is :class:`~vultron.core.use_cases.triggers.service.TriggerService`.

Port direction: **inbound (driving)** — adapters call these methods to
initiate actor-side domain behaviors.  No adapter-layer types appear here.

See also: ``docs/adr/0009-hexagonal-architecture.md``
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from vultron.core.models.use_case_result import (
    ActivityResult,
    CaseResult,
    NoteResult,
    OfferResult,
    RoleOfferResult,
    StatusResult,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole


class TriggerServicePort(Protocol):
    """Inbound port for all actor-initiated trigger operations.

    Adapters (FastAPI, CLI, MCP) type-hint against this Protocol; tests
    inject a ``Mock(spec=TriggerServicePort)``.

    Every method raises bare ``VultronError`` subclasses — callers are
    responsible for translating to their own error format (e.g.
    ``domain_error_translation()`` in FastAPI routers).

    Every method returns its verb's :class:`TriggerResult` subtype
    (UCORG-05-005); the router serialises it with ``model_dump()`` so the
    response body is the subtype's exact key set.  This per-verb surface is
    the additive step of ADR-0110; the port collapses to one
    ``trigger(request) -> ResultT_co`` method in the step that follows.
    """

    # -----------------------------------------------------------------------
    # Report triggers
    # -----------------------------------------------------------------------

    def submit_report(
        self,
        actor_id: str,
        report_name: str,
        report_content: str,
        recipient_id: str,
    ) -> OfferResult: ...

    def validate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult: ...

    def invalidate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult: ...

    def reject_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult: ...

    def close_case(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult: ...

    def close_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> ActivityResult: ...

    # -----------------------------------------------------------------------
    # Case triggers
    # -----------------------------------------------------------------------

    def create_case(
        self,
        actor_id: str,
        name: str,
        content: str,
        report_id: str | None = None,
        to: list[str] | None = None,
    ) -> CaseResult: ...

    def engage_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult: ...

    def defer_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult: ...

    def leave_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult: ...

    def add_object_to_case(
        self,
        actor_id: str,
        case_id: str,
        object_id: str,
    ) -> ActivityResult: ...

    def add_report_to_case(
        self,
        actor_id: str,
        case_id: str,
        report_id: str,
    ) -> ActivityResult: ...

    def add_note_to_case(
        self,
        actor_id: str,
        case_id: str,
        note_name: str,
        note_content: str,
        in_reply_to: str | None = None,
    ) -> NoteResult: ...

    def add_participant_status(
        self,
        actor_id: str,
        case_id: str,
        rm_state: RM | None = None,
        vf_state: CS_vf | None = None,
        d_state: CS_d | None = None,
        pxa_state: CS_pxa | None = None,
    ) -> StatusResult: ...

    # -----------------------------------------------------------------------
    # Embargo triggers
    # -----------------------------------------------------------------------

    def propose_embargo(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> ActivityResult: ...

    def accept_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> ActivityResult: ...

    def reject_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> ActivityResult: ...

    def propose_embargo_revision(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> ActivityResult: ...

    def terminate_embargo(
        self,
        actor_id: str,
        case_id: str,
    ) -> ActivityResult: ...

    # -----------------------------------------------------------------------
    # Actor / participant triggers
    # -----------------------------------------------------------------------

    def suggest_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        suggested_actor_id: str,
        roles: list | None = None,
    ) -> ActivityResult: ...

    def accept_case_invite(
        self,
        actor_id: str,
        invite_id: str,
    ) -> ActivityResult: ...

    def reject_case_invite(
        self,
        actor_id: str,
        invite_id: str,
    ) -> ActivityResult: ...

    def accept_actor_recommendation(
        self,
        actor_id: str,
        cp_offer_id: str,
        case_actor_id: str,
    ) -> ActivityResult: ...

    def invite_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        invitee_id: str,
        roles: list | None = None,
    ) -> ActivityResult: ...

    def offer_case_participant_role(
        self,
        actor_id: str,
        case_id: str,
        target_actor_id: str,
        role: CVDRole = CVDRole.CASE_MANAGER,
    ) -> RoleOfferResult: ...

    def offer_case_ownership_transfer(
        self,
        actor_id: str,
        case_id: str,
        transferee_id: str,
        content: str | None = None,
    ) -> ActivityResult: ...

    def accept_case_ownership_transfer(
        self,
        actor_id: str,
        offer_id: str,
    ) -> ActivityResult: ...
