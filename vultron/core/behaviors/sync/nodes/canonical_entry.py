#!/usr/bin/env python
#
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
"""Canonical-entry validation for the case ledger commit boundary.

Guards every ``disposition="recorded"`` ``CaseLedgerEntry`` before it reaches
the hash chain: the ``payloadSnapshot`` must carry a non-empty actor URI, a
registered ``(activity_type, object_type)`` signature, fully inline nested
objects, a ``context`` equal to the case URI, and — per CLP-07-003 — a
CaseActor actor only for signatures the CaseActor is authorized to author.

Extracted from ``chain.py`` to keep that module within the BTND-07-004
500-line leaf limit; grouped here as its own semantic concern per BTND-07-006.

Spec: CLP-07, CLP-12.
"""

from __future__ import annotations

from typing import Any

from vultron.errors import VultronCanonicalEntryError

# Every ``(activity_type, object_type)`` pair that may appear as a canonical
# ledger ``payloadSnapshot``.  Audited against the CaseActor-authoritative
# initialization path in ADR-0041 (Issue #1777): the four init signatures
# (``Create(VulnerabilityCase)``, ``Add(VulnerabilityReport)``,
# ``Add(ParticipantStatus)``, ``Add(CaseStatus)``) are all still required —
# ``case_proposal_received_tree`` now commits them natively where the deleted
# ``WritePrologueLedgerEntriesNode`` used to back-fill them (CM-22-003).  No
# entry in either collection is prologue-only.
_CANONICAL_PAYLOAD_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("Create", "VulnerabilityCase"),
    ("Offer", "VulnerabilityReport"),
    ("Offer", "VulnerabilityCase"),
    ("Accept", "Offer"),  # validate_report (RV) — object_ is the Offer
    ("TentativeReject", "Offer"),  # invalidate_report (RI)
    ("Reject", "Offer"),  # close_report (RC)
    ("Read", "Offer"),  # ack_report (RK, ADR-0021)
    ("Add", "Note"),
    ("Add", "VulnerabilityReport"),  # add_report_to_case
    ("Add", "CaseStatus"),  # add_case_status_to_case
    ("Add", "ParticipantStatus"),
    ("Add", "EmbargoEvent"),
    ("Remove", "EmbargoEvent"),
    ("Offer", "EmbargoEvent"),
    ("Invite", "EmbargoEvent"),
    ("Accept", "EmbargoEvent"),
    ("Reject", "EmbargoEvent"),
    ("Join", "VulnerabilityCase"),
    ("Ignore", "VulnerabilityCase"),
    ("Leave", "VulnerabilityCase"),
    ("Invite", "VulnerabilityCase"),
    ("Accept", "Invite"),
    ("Reject", "Invite"),
    ("Announce", "VulnerabilityCase"),
    ("Offer", "CaseParticipant"),
    ("Add", "CaseParticipant"),
)
# Signatures the CaseActor itself is authorized to author (CLP-07-003).  Per
# CLP-12-002 this MUST be a superset of every pair the CaseActor emits during
# native case initialization, so that single-actor deployments — where the
# vendor IS the CaseActor — are not rejected for entries the CaseActor is
# legitimately responsible for.
_CASE_AUTHORED_SIGNATURES: frozenset[tuple[str, str]] = frozenset(
    {
        ("Announce", "VulnerabilityCase"),
        ("Add", "EmbargoEvent"),
        ("Remove", "EmbargoEvent"),
        ("Invite", "EmbargoEvent"),
        ("Offer", "CaseParticipant"),
        ("Invite", "VulnerabilityCase"),
        ("Offer", "VulnerabilityCase"),
        ("Leave", "VulnerabilityCase"),
        ("Accept", "Offer"),
        ("Reject", "Offer"),
        ("Add", "CaseParticipant"),
        # native case-initialization entries (ADR-0041, CM-22-003)
        ("Create", "VulnerabilityCase"),
        ("Add", "VulnerabilityReport"),
        ("Add", "ParticipantStatus"),
        ("Add", "CaseStatus"),  # add_case_status_to_case (CLP-12-001, #1767)
    }
)
_INLINE_OBJECT_KEYS: frozenset[str] = frozenset(
    {"object", "object_", "target"}
)


def _snapshot_type(snapshot: dict[str, Any]) -> str | None:
    activity_type = snapshot.get("type") or snapshot.get("type_")
    return (
        activity_type
        if isinstance(activity_type, str) and activity_type
        else None
    )


_ACTOR_TYPES: frozenset[str] = frozenset(
    {"Actor", "Application", "Group", "Organization", "Person", "Service"}
) | {"CoreActor"}


def _snapshot_object_type(snapshot: dict[str, Any]) -> str | None:
    # Invite(Actor, target=Case): object_ is the actor; use target.type so the
    # signature resolves to ('Invite','VulnerabilityCase') not ('Invite','Org').
    obj = snapshot.get("object") or snapshot.get("object_")
    if not isinstance(obj, dict):
        return None
    object_type = obj.get("type") or obj.get("type_")
    if not isinstance(object_type, str) or not object_type:
        return None
    if object_type in _ACTOR_TYPES:
        target = snapshot.get("target")
        if isinstance(target, dict):
            target_type = target.get("type") or target.get("type_")
            if isinstance(target_type, str) and target_type:
                return target_type
    return object_type


def _bare_inline_object_path(
    value: Any, path: str = "payloadSnapshot"
) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in _INLINE_OBJECT_KEYS and isinstance(child, str):
                return child_path
            nested_path = _bare_inline_object_path(child, child_path)
            if nested_path is not None:
                return nested_path
        return None
    if isinstance(value, list):
        for index, item in enumerate(value):
            nested_path = _bare_inline_object_path(item, f"{path}[{index}]")
            if nested_path is not None:
                return nested_path
    return None


def _validate_canonical_entry(
    *,
    case_id: str,
    actor_id: str | None,
    case_actor_id: str | None = None,
    disposition: str,
    payload_snapshot: dict[str, Any],
    event_type: str,
) -> None:
    # Runs before idempotency check so malformed entries never reach the
    # equivalence lookup (CLP-07). Relaxed for non-recorded dispositions.
    if disposition != "recorded":
        return
    if not payload_snapshot:
        raise VultronCanonicalEntryError(
            f"{event_type}: recorded canonical entries require a non-empty "
            "payloadSnapshot"
        )

    snapshot_actor = payload_snapshot.get("actor")
    if not isinstance(snapshot_actor, str) or not snapshot_actor:
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot.actor must be a non-empty URI"
        )

    activity_type = _snapshot_type(payload_snapshot)
    object_type = _snapshot_object_type(payload_snapshot)
    signature = (activity_type or "", object_type or "")

    bare_reference_path = _bare_inline_object_path(payload_snapshot)
    if bare_reference_path is not None:
        raise VultronCanonicalEntryError(
            f"{event_type}: {bare_reference_path} must be an inline object, "
            "not a bare ID string"
        )

    if signature not in _CANONICAL_PAYLOAD_SIGNATURES:
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot type/object pair {signature!r} "
            "is not canonical"
        )

    # CLP-07-003: only CaseActor-authored activities may have the CaseActor as
    # snapshot actor; all participant-originated activities must have a
    # participant (non-CaseActor) actor.
    if (
        case_actor_id
        and snapshot_actor == case_actor_id
        and signature not in _CASE_AUTHORED_SIGNATURES
    ):
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot.actor must not be the CaseActor"
            f" for non-case-authored entries (signature={signature!r})"
        )

    context = payload_snapshot.get("context")
    if context != case_id:
        raise VultronCanonicalEntryError(
            f"{event_type}: payloadSnapshot.context must equal the case URI"
        )
