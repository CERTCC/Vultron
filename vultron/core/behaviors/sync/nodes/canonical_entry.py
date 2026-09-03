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

from datetime import datetime, timedelta, timezone
from typing import Any

from vultron.core.models._helpers import _as_utc, parse_published
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
    # CaseActor-authored synthetic lapse event (CM-28-009, ADR-0065 §5).
    # Distinct from ("Reject", "Invite") which records an explicit refusal.
    ("Lapse", "Invite"),
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
        # CaseActor-authored synthetic lapse event (CM-28-009, ADR-0065 §5)
        ("Lapse", "Invite"),
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


def _validate_entry_timestamps(
    *,
    event_type: str,
    payload_snapshot: dict[str, Any],
    case_published: datetime | None,
    prev_actor_published: datetime | None,
    future_tolerance: timedelta | None,
    staleness_window: timedelta | None,
    skew_tolerance: timedelta,
) -> None:
    """Enforce the claimed-timestamp invariants at the commit boundary.

    Checks ``payloadSnapshot.published`` — the *asserting actor's* claimed
    event time, carried across the wire→core boundary by
    ``_build_activity_snapshot`` (ISSUE-3149) for received activities and
    stamped with the CaseActor's own clock for CaseActor-authored ones.

    This is deliberately a different field from ``CaseLedgerEntry.published``,
    the CaseActor's commit stamp.  The two invariant families do not belong at
    the same layer:

    * The **commit**-timestamp invariants — CLP-14-002 (non-null), CLP-14-003
      (non-decreasing across *all* entries by ``log_index``) and CLP-14-006
      evaluated against the entry envelope — hold by construction, because a
      single writer stamps every entry from one clock.  The conformance harness
      (``check_clp14_timestamp_invariants``) is authoritative over them.
    * The **claimed**-timestamp invariants checked here cannot hold by
      construction, because they concern a value an external participant chose.

    Critically, CLP-14-003's cross-entry monotonicity is *not* applied to the
    claimed timestamp.  Comparing claimed timestamps across different actors is
    exactly the wall-clock ordering ADR-0079 rejected as option C: two
    participants' clocks are not comparable, so a later-committed assertion
    from actor B legitimately carries an earlier claimed time than one from
    actor A.  The per-stream obligation CLP-15-003 states — non-decreasing
    *within the same participant's* event stream — is what is enforceable, and
    ``prev_actor_published`` is scoped to the snapshot actor for that reason.

    Each check is gated independently on the context it needs.  An earlier
    version gated the whole block on ``case_published is not None`` and was
    never reached, because the only production call site omitted that argument
    (ISSUE-2824).

    Args:
        event_type: Ledger event type, used to prefix violation messages.
        payload_snapshot: The candidate ``payloadSnapshot``.
        case_published: The parent case's own ``published``, or ``None`` when
            the case is not yet readable (the genesis entry is committed
            alongside case creation), which skips CLP-14-006.
        prev_actor_published: Claimed ``published`` of the most recent recorded
            entry asserted by *this same actor* for this case, or ``None`` when
            this is that actor's first assertion, which skips CLP-15-003.
        future_tolerance: CLP-14-007 ceiling; ``None`` disables the check.
        staleness_window: CLP-14-008 window; ``None`` disables the check.
        skew_tolerance: Slack allowed on CLP-14-006 for unsynchronised clocks.

    Raises:
        VultronCanonicalEntryError: On any claimed-timestamp violation.
    """
    case_published = _as_utc(case_published)
    prev_actor_published = _as_utc(prev_actor_published)

    raw_published = payload_snapshot.get("published")
    if raw_published is None:  # CLP-07-011
        raise VultronCanonicalEntryError(
            f"{event_type}: CLP-07-011 — payloadSnapshot.published is "
            "required; a snapshot without it is not the verbatim AS2 activity"
        )
    entry_published = parse_published(raw_published)
    if entry_published is None:  # CLP-07-011 (malformed)
        raise VultronCanonicalEntryError(
            f"{event_type}: CLP-07-011 — payloadSnapshot.published is not a "
            "valid ISO 8601 timestamp"
        )
    if (  # CLP-14-006
        case_published is not None
        and entry_published < case_published - skew_tolerance
    ):
        raise VultronCanonicalEntryError(
            f"{event_type}: CLP-14-006 — entry published {entry_published} "
            f"predates case created {case_published} by more than the "
            f"{skew_tolerance} clock-skew tolerance"
        )
    if (  # CLP-15-003
        prev_actor_published is not None
        and entry_published < prev_actor_published
    ):
        raise VultronCanonicalEntryError(
            f"{event_type}: CLP-15-003 — entry published {entry_published} "
            f"regresses before this actor's previous assertion "
            f"{prev_actor_published}"
        )
    now = datetime.now(tz=timezone.utc)
    if (
        future_tolerance is not None
        and entry_published > now + future_tolerance
    ):
        raise VultronCanonicalEntryError(  # CLP-14-007
            f"{event_type}: CLP-14-007 — entry published {entry_published} "
            f"exceeds future tolerance of {future_tolerance}"
        )
    if (
        staleness_window is not None
        and entry_published < now - staleness_window
    ):
        raise VultronCanonicalEntryError(  # CLP-14-008
            f"{event_type}: CLP-14-008 — entry published {entry_published} "
            f"exceeds staleness window of {staleness_window}"
        )


def _validate_canonical_entry(
    *,
    case_id: str,
    actor_id: str | None,
    case_actor_id: str | None = None,
    disposition: str,
    payload_snapshot: dict[str, Any],
    event_type: str,
    case_published: datetime | None = None,
    prev_actor_published: datetime | None = None,
    future_tolerance: timedelta | None = timedelta(minutes=5),
    staleness_window: timedelta | None = timedelta(days=7),
    skew_tolerance: timedelta = timedelta(minutes=5),
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

    # Claimed-timestamp invariants.  Unconditional for recorded entries: each
    # individual check gates itself on the context it needs.  Gating the whole
    # block on an optional argument is what left it dead (ISSUE-2824).
    _validate_entry_timestamps(
        event_type=event_type,
        payload_snapshot=payload_snapshot,
        case_published=case_published,
        prev_actor_published=prev_actor_published,
        future_tolerance=future_tolerance,
        staleness_window=staleness_window,
        skew_tolerance=skew_tolerance,
    )
