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

"""Find which report ``Offer`` a case descends from.

One lookup, used on both sides of the CaseProposal round-trip: the receiver of
the report resolves it from its own store to name on the proposal
(CP-01-007), and the CaseActor tries it first before falling back to the Offer
the proposal's ``inReplyTo`` names (CP-01-019, ADR-0041 AC-4).
``offer_id_from_proposal`` reads that ``inReplyTo``.

The Offer's sender is not looked up beside it: an inline Offer names it as
its ``actor``, and the report names it as its ``attributedTo`` (#6419).

``VultronOfferRecord`` is keyed by ``offer_id`` (``build_id``), so answering
"which offer brought this report?" means a scan. That is acceptable here
because both callers run once per case initialization, not per message.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.wire_keys import wire_key

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CasePersistence


def find_offer_for_report(
    datalayer: CasePersistence, report_id: str | None
) -> str | None:
    """Return the id of the ``Offer`` that brought *report_id* to this store.

    Returns ``None`` when this store holds no ``OfferRecord`` for the report —
    which is the normal answer for an actor that never received the
    ``Offer(VulnerabilityReport)`` itself, a co-located CaseActor included
    (ADR-0073, PCR-01-003).
    """
    if not report_id:
        return None
    for raw in datalayer.list_objects("OfferRecord"):
        if not isinstance(raw, VultronOfferRecord):
            continue
        if raw.report_id == report_id:
            return raw.offer_id
    return None


def offer_for_report_or(
    datalayer: CasePersistence,
    report_id: str,
    fallback: str | None,
) -> str | None:
    """Return the id of *report_id*'s ``Offer``, else *fallback*.

    Its own store first, then the Offer the proposal named (CP-01-019). The
    store answers only when this CaseActor received the
    ``Offer(VulnerabilityReport)`` itself — which a co-located one does not,
    because the ``OfferRecord`` belongs to the sibling that did and there is
    no read across that line (ADR-0073, PCR-01-003).

    The fallback is not a nicety. The ledger entry's ``inReplyTo`` is the only
    place the report's Offer survives for the case's participants, who were
    never sent the Offer and read it from there (CP-01-007). Without it the
    omission surfaces nowhere near the commit (#2548).
    """
    return find_offer_for_report(datalayer, report_id) or fallback


def offer_id_from_proposal(proposal_dict: dict | None) -> str | None:
    """Return the id of the ``Offer`` the proposal's ``inReplyTo`` names.

    The Offer is inline when the proposer held it (CP-01-008), else its id
    (CP-01-007); either way the id is what the ledger entry names.  Both key
    spellings are accepted for the same reason
    ``StoreProposalReportNode._report_from_proposal_dict`` accepts both: which
    one a caller has depends on whether its dump used ``by_alias``.
    """
    proposal = proposal_dict or {}
    # The AS2 spelling is derived from the core field name, not typed here
    # (ARCH-25-002, ADR-0099).
    raw = proposal.get(wire_key("in_reply_to"))
    if raw is None:
        raw = proposal.get("in_reply_to")
    if isinstance(raw, Mapping):
        raw = raw.get("id") or raw.get("id_")
    return raw if isinstance(raw, str) and raw else None
