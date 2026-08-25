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
the report resolves it from its own store to put on the proposal (CP-01-007),
and the CaseActor tries it first before falling back to what the proposal
carried (ADR-0041 AC-4).

``VultronOfferRecord`` is keyed by ``offer_id`` (``build_id``), so answering
"which offer brought this report?" means a scan. That is acceptable here
because both callers run once per case initialization, not per message.
"""

from typing import TYPE_CHECKING

from vultron.core.models.offer_record import VultronOfferRecord

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CasePersistence


def find_offer_for_report(
    datalayer: "CasePersistence", report_id: str | None
) -> tuple[str | None, str | None]:
    """Return ``(offer_id, offer_actor_id)`` for *report_id*.

    Returns ``(None, None)`` when this store holds no ``OfferRecord`` for the
    report — which is the normal answer for an actor that never received the
    ``Offer(VulnerabilityReport)`` itself, a co-located CaseActor included
    (ADR-0072, PCR-01-003).
    """
    if not report_id:
        return None, None
    for raw in datalayer.list_objects("OfferRecord"):
        if not isinstance(raw, VultronOfferRecord):
            continue
        if raw.report_id == report_id:
            return raw.offer_id, raw.offer_actor_id
    return None, None
