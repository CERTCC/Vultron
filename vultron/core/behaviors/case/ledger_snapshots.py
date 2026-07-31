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
an AS2 ``type``/``actor``/``object`` triple with ``context`` set to the case
URI and every nested object embedded inline rather than as a bare ID string
(DEMOMA-08-005, CLP-07).

These helpers were previously private to the now-deleted
``nodes/prologue.py`` (``WritePrologueLedgerEntriesNode``, Issue #1688).
ADR-0041 removes the vendor-authored back-fill; the builders themselves are
retained because the CaseActor uses the same snapshot shapes when it commits
those entries natively (CM-22-003).
"""

from typing import Any

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport


def obj_to_inline_dict(obj: Any) -> dict[str, Any]:
    """Return a JSON-serializable dict for *obj* suitable for payloadSnapshot.

    For Pydantic models, calls ``model_dump(mode="json", by_alias=True,
    exclude_none=True)``.  For plain dicts, returns a copy.  Returns an
    empty dict for ``None``.
    """
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        result = obj.model_dump(mode="json", by_alias=True, exclude_none=True)
        return result if isinstance(result, dict) else {}
    if isinstance(obj, dict):
        return dict(obj)
    return {}


def build_create_case_snapshot(
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
) -> dict[str, Any]:
    """Build the ``create_case`` snapshot (``Create(VulnerabilityCase)``)."""
    case_dict = obj_to_inline_dict(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Create",
        "actor": actor_id,
        "object": case_dict,
        "context": case_id,
    }


def build_add_report_to_case_snapshot(
    report: VulnerabilityReport,
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
) -> dict[str, Any]:
    """Build the ``add_report_to_case`` snapshot (``Add(VulnerabilityReport)``)."""
    report_dict = obj_to_inline_dict(report)
    report_dict.setdefault("type", "VulnerabilityReport")
    case_dict = obj_to_inline_dict(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Add",
        "actor": actor_id,
        "object": report_dict,
        "target": case_dict,
        "context": case_id,
    }


def build_add_participant_status_snapshot(
    status: ParticipantStatus,
    participant: CaseParticipant,
    actor_id: str,
    case_id: str,
) -> dict[str, Any]:
    """Build the ``add_participant_status_to_participant`` snapshot."""
    status_dict = obj_to_inline_dict(status)
    # model_dump renders the PEC dimension as {"consent": {"state": "VALUE"}}.
    # Invariant 9 (and the wire schema) expect the flat key "emConsentState".
    if "consent" in status_dict and "emConsentState" not in status_dict:
        pec_state = status_dict.pop("consent", {}).get("state")
        if pec_state is not None:
            status_dict["emConsentState"] = pec_state
    status_dict.setdefault("type", "ParticipantStatus")
    participant_dict = obj_to_inline_dict(participant)
    participant_dict.setdefault("type", "CaseParticipant")
    return {
        "type": "Add",
        "actor": actor_id,
        "object": status_dict,
        "target": participant_dict,
        "context": case_id,
    }


def build_add_case_status_snapshot(
    status: CaseStatus,
    case: VulnerabilityCase,
    actor_id: str,
    case_id: str,
) -> dict[str, Any]:
    """Build the ``add_case_status_to_case`` snapshot (``Add(CaseStatus)``)."""
    status_dict = obj_to_inline_dict(status)
    status_dict.setdefault("type", "CaseStatus")
    case_dict = obj_to_inline_dict(case)
    case_dict.setdefault("type", "VulnerabilityCase")
    return {
        "type": "Add",
        "actor": actor_id,
        "object": status_dict,
        "target": case_dict,
        "context": case_id,
    }
