"""Authoritative MSM shorthand → ``MessageSemantics`` mapping table.

Derived from ``specs/message-semantics-mapping.yaml`` (MSM-01 through MSM-04)
and ``notes/message-type-reference.md``.  Each :class:`RowSpec` records one
``SEMANTIC_REGISTRY`` entry's primary page assignment, formal shorthand(s), and
mapping status.

This module is the machine-readable complement to the MSM spec YAML, which
encodes the same information in normative prose.  Keeping it in Python lets the
renderer and ratchet join against ``SEMANTIC_REGISTRY`` without fragile text
parsing.
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

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vultron.core.models.events.base import MessageSemantics


class MappingStatus(StrEnum):
    """How a protocol shorthand relates to a ``SEMANTIC_REGISTRY`` entry."""

    DIRECT = "direct"
    """One shorthand maps to exactly one semantics value."""
    COLLAPSE = "collapse"
    """Multiple shorthands share one wire form; discriminated by a payload field."""
    EXPANSION = "expansion"
    """One shorthand expands across multiple wire forms."""
    EVOLVED = "evolved"
    """The shorthand's purpose is served by a mechanism on a different axis."""
    NONE = "none"
    """No formal protocol shorthand; wire activity with no direct formal counterpart."""


@dataclass(frozen=True)
class RowSpec:
    """One ``SEMANTIC_REGISTRY`` entry with its page and mapping metadata.

    Attributes:
        semantics: The ``MessageSemantics`` enum value.
        page: Primary page slug under ``docs/reference/messages/`` (no ``.md``).
        shorthands: Formal protocol shorthand(s), e.g. ``("RS",)`` or
            ``("CV", "CF")`` for a collapse.  Empty tuple when
            :attr:`status` is ``NONE`` or ``EVOLVED``.
        status: How the shorthand(s) relate to this wire form.
        discriminator: For ``COLLAPSE`` entries: the payload field whose value
            distinguishes the shorthands (e.g. ``"vf_state"``).  ``None``
            otherwise.
    """

    semantics: MessageSemantics
    page: str
    shorthands: tuple[str, ...] = field(default_factory=tuple)
    status: MappingStatus = MappingStatus.NONE
    discriminator: str | None = None


# ---------------------------------------------------------------------------
# Exempted semantics — dispatcher fallbacks, not protocol messages.
# Ratchet test allows these to have no primary page (MSM-06-002).
# ---------------------------------------------------------------------------

EXEMPTED_SEMANTICS: frozenset[MessageSemantics] = frozenset(
    {
        MessageSemantics.UNKNOWN,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }
)

# ---------------------------------------------------------------------------
# Mapping table.  One RowSpec per non-exempted SEMANTIC_REGISTRY entry.
# Source: specs/message-semantics-mapping.yaml MSM-01 through MSM-04,
# notes/message-type-reference.md.
# ---------------------------------------------------------------------------
#
# Design note (MSM-06-002, notes/message-type-reference.md):
#   A few entries legitimately appear on a second page (collapse/expansion
#   semantics give them a secondary home).  The primary page is what this
#   table records; secondary appearances are a renderer concern, not a
#   ratchet concern.  See notes for the three entries with a second home:
#     ADD_PARTICIPANT_STATUS_TO_PARTICIPANT  (cs primary, rm secondary)
#     CLOSE_REPORT                           (rm primary, faults secondary)
#     REJECT_CASE_LEDGER_ENTRY               (ledger primary, faults secondary)

ROW_SPECS: tuple[RowSpec, ...] = (
    # ------------------------------------------------------------------
    # rm.md — Report Management (RM) shorthands
    # Source: MSM-01, plus the Create(VulnerabilityReport) wire activity
    # that has no formal shorthand but belongs in the RM family.
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.CREATE_REPORT,
        page="rm",
    ),
    RowSpec(
        semantics=MessageSemantics.SUBMIT_REPORT,
        page="rm",
        shorthands=("RS",),
        status=MappingStatus.DIRECT,
    ),
    RowSpec(
        semantics=MessageSemantics.ACK_REPORT,
        page="rm",
        shorthands=("RK",),
        status=MappingStatus.DIRECT,
    ),
    RowSpec(
        semantics=MessageSemantics.VALIDATE_REPORT,
        page="rm",
        shorthands=("RV",),
        status=MappingStatus.DIRECT,
    ),
    RowSpec(
        semantics=MessageSemantics.INVALIDATE_REPORT,
        page="rm",
        shorthands=("RI",),
        status=MappingStatus.DIRECT,
    ),
    RowSpec(
        semantics=MessageSemantics.CLOSE_REPORT,
        page="rm",
        shorthands=("RC",),
        status=MappingStatus.DIRECT,
    ),
    # RA and RD use case-level verbs (Join / Ignore) because the act is a
    # case-participation decision, not a report-validity judgment (MSM-01-004,
    # MSM-01-005).  Primary page is rm.md; they appear in case.py.
    RowSpec(
        semantics=MessageSemantics.ENGAGE_CASE,
        page="rm",
        shorthands=("RA",),
        status=MappingStatus.DIRECT,
    ),
    RowSpec(
        semantics=MessageSemantics.DEFER_CASE,
        page="rm",
        shorthands=("RD",),
        status=MappingStatus.DIRECT,
    ),
    # ------------------------------------------------------------------
    # em.md — Embargo Management (EM) shorthands
    # Source: MSM-02.
    # EP expands into four wire activities; EV/EJ/EC collapse with
    # EP/ER/EA respectively, distinguished by EM context not payload.
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.CREATE_EMBARGO_EVENT,
        page="em",
        shorthands=("EP",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        page="em",
        shorthands=("EP",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE,
        page="em",
        shorthands=("EP",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        page="em",
        # EV (revision proposal) shares the same wire form as EP (initial
        # proposal); discriminated by EM state context, not a payload field.
        shorthands=("EP", "EV"),
        status=MappingStatus.COLLAPSE,
        discriminator="EM state context",
    ),
    RowSpec(
        semantics=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        page="em",
        shorthands=("EA", "EC"),
        status=MappingStatus.COLLAPSE,
        discriminator="EM state context",
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        page="em",
        shorthands=("ER", "EJ"),
        status=MappingStatus.COLLAPSE,
        discriminator="EM state context",
    ),
    RowSpec(
        semantics=MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
        page="em",
        shorthands=("ET",),
        status=MappingStatus.DIRECT,
    ),
    # ------------------------------------------------------------------
    # cs.md — Case State (CS) shorthands
    # Source: MSM-03.
    # CV/CF collapse onto vf_state; CD collapses onto d_state; both share
    # ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.  CP/CX/CA collapse onto pxa_state.
    # ADD_PARTICIPANT_STATUS_TO_PARTICIPANT also carries RM state via rm_state —
    # its secondary home is rm.md (see notes/message-type-reference.md).
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.CREATE_CASE_STATUS,
        page="cs",
    ),
    RowSpec(
        semantics=MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        page="cs",
        shorthands=("CP", "CX", "CA"),
        status=MappingStatus.COLLAPSE,
        discriminator="pxa_state",
    ),
    RowSpec(
        semantics=MessageSemantics.CREATE_PARTICIPANT_STATUS,
        page="cs",
    ),
    # CV and CF use vf_state; CD uses d_state.  All share this one semantics
    # value.  The renderer notes the two discriminators; the ratchet sees one
    # primary page (cs.md).
    RowSpec(
        semantics=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        page="cs",
        shorthands=("CV", "CF", "CD"),
        status=MappingStatus.COLLAPSE,
        # vf_state carries CV/CF; d_state carries CD; rm_state carries the RM
        # ladder.  Show all three so no dimension is hidden.
        discriminator="vf_state / d_state / rm_state",
    ),
    # ------------------------------------------------------------------
    # general.md — General (GI) shorthands
    # Source: MSM-04.
    # GI expands: note lifecycle + actor-suggestion exchange.
    # GK/GE are evolved (no dedicated semantics; see MSM-05).
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.CREATE_NOTE,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.ADD_NOTE_TO_CASE,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.REMOVE_NOTE_FROM_CASE,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.OFFER_ACTOR_TO_CASE,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.OFFER_CASE_PARTICIPANT,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
        page="general",
        shorthands=("GI",),
        status=MappingStatus.EXPANSION,
    ),
    # ------------------------------------------------------------------
    # faults_and_acknowledgements.md — fault / ack mechanisms
    # Source: MSM-05.
    # RE/EE/CE/GE and EK/CK/GK have no dedicated dispatch values; their
    # purposes are served by the mechanisms partitioned on a different axis.
    # CREATE_PROCESSING_FAULT is the primary "not understood" fault mechanism.
    # CLOSE_REPORT and REJECT_CASE_LEDGER_ENTRY also appear here as secondary
    # homes; their primary pages are rm.md and ledger_replication.md.
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.CREATE_PROCESSING_FAULT,
        page="faults_and_acknowledgements",
    ),
    # ------------------------------------------------------------------
    # case_management.md — case lifecycle and roster wire activities
    # No formal shorthand; not modelled by the 28-shorthand protocol set.
    # ------------------------------------------------------------------
    RowSpec(semantics=MessageSemantics.CREATE_CASE, page="case_management"),
    RowSpec(semantics=MessageSemantics.UPDATE_CASE, page="case_management"),
    RowSpec(
        semantics=MessageSemantics.ADD_REPORT_TO_CASE, page="case_management"
    ),
    RowSpec(semantics=MessageSemantics.CLOSE_CASE, page="case_management"),
    RowSpec(
        semantics=MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.INVITE_ACTOR_TO_CASE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.CREATE_CASE_PARTICIPANT,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        page="case_management",
    ),
    RowSpec(
        semantics=MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        page="case_management",
    ),
    # ------------------------------------------------------------------
    # case_proposal.md — pre-case bootstrap (ADR-0023)
    # No formal shorthand; not a case-management message (no case exists yet).
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.CREATE_CASE_PROPOSAL,
        page="case_proposal",
    ),
    RowSpec(
        semantics=MessageSemantics.ACCEPT_CASE_PROPOSAL,
        page="case_proposal",
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_CASE_PROPOSAL,
        page="case_proposal",
    ),
    # ------------------------------------------------------------------
    # ledger_replication.md — SYNC substrate (ADR-0077)
    # REJECT_CASE_LEDGER_ENTRY also appears in faults_and_acknowledgements.md
    # as a secondary home (ledger NAK = acknowledgement story).
    # ------------------------------------------------------------------
    RowSpec(
        semantics=MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY,
        page="ledger_replication",
    ),
    RowSpec(
        semantics=MessageSemantics.REJECT_CASE_LEDGER_ENTRY,
        page="ledger_replication",
    ),
)

# ---------------------------------------------------------------------------
# Derived fast-lookup indices.
# ---------------------------------------------------------------------------

#: Mapping from page slug → tuple of RowSpecs assigned to that page.
_page_rows_builder: dict[str, list[RowSpec]] = {}
for _row in ROW_SPECS:
    _page_rows_builder.setdefault(_row.page, []).append(_row)
PAGE_ROWS: dict[str, tuple[RowSpec, ...]] = {
    k: tuple(v) for k, v in _page_rows_builder.items()
}

#: All known page slugs, in canonical display order.
PAGE_SLUGS: tuple[str, ...] = (
    "rm",
    "em",
    "cs",
    "general",
    "faults_and_acknowledgements",
    "case_management",
    "case_proposal",
    "ledger_replication",
)

#: Mapping from ``MessageSemantics`` → ``RowSpec`` for O(1) lookup.
SEMANTICS_TO_ROW: dict[MessageSemantics, RowSpec] = {
    row.semantics: row for row in ROW_SPECS
}
