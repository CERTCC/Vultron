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
from typing import Any, Protocol

from vultron.core.models.case_log_entry import VultronCaseLogEntry


class TriggerServicePort(Protocol):
    """Inbound port for all actor-initiated trigger operations.

    Adapters (FastAPI, CLI, MCP) type-hint against this Protocol; tests
    inject a ``Mock(spec=TriggerServicePort)``.

    Every method raises bare ``VultronError`` subclasses — callers are
    responsible for translating to their own error format (e.g.
    ``domain_error_translation()`` in FastAPI routers).
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
    ) -> dict[str, Any]: ...

    def validate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]: ...

    def invalidate_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]: ...

    def reject_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]: ...

    def close_report(
        self,
        actor_id: str,
        offer_id: str,
        note: str | None = None,
    ) -> dict[str, Any]: ...

    # -----------------------------------------------------------------------
    # Case triggers
    # -----------------------------------------------------------------------

    def create_case(
        self,
        actor_id: str,
        name: str,
        content: str,
        report_id: str | None = None,
    ) -> dict[str, Any]: ...

    def engage_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> dict[str, Any]: ...

    def defer_case(
        self,
        actor_id: str,
        case_id: str,
    ) -> dict[str, Any]: ...

    def add_object_to_case(
        self,
        actor_id: str,
        case_id: str,
        object_id: str,
    ) -> dict[str, Any]: ...

    def add_report_to_case(
        self,
        actor_id: str,
        case_id: str,
        report_id: str,
    ) -> dict[str, Any]: ...

    def add_note_to_case(
        self,
        actor_id: str,
        case_id: str,
        note_name: str,
        note_content: str,
        in_reply_to: str | None = None,
    ) -> dict[str, Any]: ...

    def add_participant_status(
        self,
        actor_id: str,
        case_id: str,
        rm_state: Any = None,
        vfd_state: Any = None,
        pxa_state: Any = None,
    ) -> dict[str, Any]: ...

    # -----------------------------------------------------------------------
    # Embargo triggers
    # -----------------------------------------------------------------------

    def propose_embargo(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> dict[str, Any]: ...

    def accept_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> dict[str, Any]: ...

    def reject_embargo(
        self,
        actor_id: str,
        case_id: str,
        proposal_id: str | None = None,
    ) -> dict[str, Any]: ...

    def propose_embargo_revision(
        self,
        actor_id: str,
        case_id: str,
        end_time: datetime,
        note: str | None = None,
    ) -> dict[str, Any]: ...

    def terminate_embargo(
        self,
        actor_id: str,
        case_id: str,
    ) -> dict[str, Any]: ...

    # -----------------------------------------------------------------------
    # Actor / participant triggers
    # -----------------------------------------------------------------------

    def suggest_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        suggested_actor_id: str,
    ) -> dict[str, Any]: ...

    def accept_case_invite(
        self,
        actor_id: str,
        invite_id: str,
    ) -> dict[str, Any]: ...

    def invite_actor_to_case(
        self,
        actor_id: str,
        case_id: str,
        invitee_id: str,
    ) -> dict[str, Any]: ...

    # -----------------------------------------------------------------------
    # Sync / log-replication triggers
    # -----------------------------------------------------------------------

    def commit_log_entry(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        actor_id: str,
        payload_snapshot: dict[str, Any] | None = None,
        term: int | None = None,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        disposition: str = "recorded",
    ) -> VultronCaseLogEntry: ...
