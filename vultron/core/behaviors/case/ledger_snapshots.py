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

"""Canonical ``payloadSnapshot`` builders for case-initialization entries.

Supporting module (BTND-07-003) for the CaseActor-authoritative case
initialization tree,
:mod:`vultron.core.behaviors.case.case_proposal_received_tree`.  Each builder
returns a plain ``dict`` shaped for
:func:`~vultron.core.behaviors.sync.nodes.canonical_entry._validate_canonical_entry`:
an AS2 ``type``/``actor``/``object``/``published`` quadruple with ``context``
set to the case URI and every nested object embedded inline rather than as a
bare ID string (DEMOMA-08-005, CLP-07).

``published`` is the CaseActor's own clock at snapshot-build time, not a
timestamp lifted off the object being described.  These are CaseActor-authored
assertions, so the CaseActor's clock *is* the claimed event time (CLP-14-002,
ADR-0079 § "CaseActor Timestamp Obligation").  Omitting it made every
native-initialization entry fail CLP-07-011 once the commit-boundary timestamp
guard was wired (ISSUE-2824), because a snapshot with no ``published`` is not
the verbatim AS2 activity that requirement demands.

These helpers were previously private to the now-deleted
``nodes/prologue.py`` (``WritePrologueLedgerEntriesNode``, Issue #1688).
ADR-0041 removes the vendor-authored back-fill; the builders themselves are
retained because the CaseActor uses the same snapshot shapes when it commits
those entries natively (CM-22-003).
"""

from typing import TYPE_CHECKING, Any

from vultron.core.models._helpers import _now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort


def build_create_case_snapshot(
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
    wire_render_port: "WireRenderPort",
) -> dict[str, Any]:
    """Build the ``create_case`` snapshot (``Create(VulnerabilityCase)``)."""
    case_dict = wire_render_port.render(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Create",
        "actor": actor_id,
        "published": _now_utc().isoformat(),
        "object": case_dict,
        "context": case_id,
    }


def build_add_report_to_case_snapshot(
    report: VulnerabilityReport,
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
    wire_render_port: "WireRenderPort",
    offer_id: str | None = None,
    offer_actor_id: str | None = None,
) -> dict[str, Any]:
    """Build the ``add_report_to_case`` snapshot (``Add(VulnerabilityReport)``).

    ``offer_id`` and ``offer_actor_id`` are embedded when provided so that
    invited actors can reconstruct a ``VultronOfferRecord`` from the SYNC
    backfilled entry (ISSUE-2134, SYNC-02-002).
    """
    report_dict = wire_render_port.render(report)
    report_dict.setdefault("type", "VulnerabilityReport")
    case_dict = wire_render_port.render(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    snapshot: dict[str, Any] = {
        "type": "Add",
        "actor": actor_id,
        "published": _now_utc().isoformat(),
        "object": report_dict,
        "target": case_dict,
        "context": case_id,
    }
    if offer_id:
        snapshot["offerId"] = offer_id
    if offer_actor_id:
        snapshot["offerActorId"] = offer_actor_id
    return snapshot


def build_add_participant_status_snapshot(
    status: ParticipantStatus,
    participant: CaseParticipant,
    actor_id: str,
    case_id: str,
    wire_render_port: "WireRenderPort",
) -> dict[str, Any]:
    """Build the ``add_participant_status_to_participant`` snapshot."""
    status_dict = wire_render_port.render(status)
    status_dict.setdefault("type", "ParticipantStatus")
    participant_dict = wire_render_port.render(participant)
    participant_dict.setdefault("type", "CaseParticipant")
    return {
        "type": "Add",
        "actor": actor_id,
        "published": _now_utc().isoformat(),
        "object": status_dict,
        "target": participant_dict,
        "context": case_id,
    }


def build_add_case_status_snapshot(
    status: CaseStatus,
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
    wire_render_port: "WireRenderPort",
) -> dict[str, Any]:
    """Build the ``add_case_status_to_case`` snapshot (``Add(CaseStatus)``)."""
    status_dict = wire_render_port.render(status)
    status_dict.setdefault("type", "CaseStatus")
    case_dict = wire_render_port.render(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Add",
        "actor": actor_id,
        "published": _now_utc().isoformat(),
        "object": status_dict,
        "target": case_dict,
        "context": case_id,
    }
