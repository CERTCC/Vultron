"""Vocabulary examples for the CaseProposal message flow.

Demonstrates ``Create(as_CaseProposal)``, ``Accept(as_CaseProposal)``,
and ``Reject(as_CaseProposal)`` activities as specified in ADR-0023 and
``specs/case-proposal.yaml`` CP-01 through CP-03.
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

from datetime import timedelta

from vultron.core.models.actor import VultronOrganization
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.examples._base import (
    _VENDOR,
    _example_stamp,
    gen_report,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

# URI of the hypothetical case-actor service used in these examples.
_CASE_ACTOR_URI = "https://example.org/case-actors/alpha"


def make_case_proposal() -> as_CaseProposal:
    """Build a minimal :class:`as_CaseProposal` example (CP-01-001–CP-01-006).

    Returns an ``as_CaseProposal`` with:

    - ``attributed_to``: vendor actor URI (CP-01-003)
    - ``object_``: inline ``VulnerabilityReport`` (CP-01-004)
    - ``target``: case-actor service URI (CP-01-005)
    - ``summary``: optional description (CP-01-006)
    """
    report = gen_report()
    return as_CaseProposal(
        attributed_to=_VENDOR.id_,
        object_=report,
        target=_CASE_ACTOR_URI,
        summary="Request case initialization for a new vulnerability.",
    )


def vendor_profile() -> VultronOrganization:
    """The vendor's full actor profile, with its published embargo policy.

    ``Create(as_CaseProposal)`` carries this inline as its ``actor``: it is
    where the case-actor service reads the Case Owner's actor default from
    (EP-01-001, CP-01-010).
    """
    return VultronOrganization(
        id_=_VENDOR.id_,
        name=_VENDOR.name,
        embargo_policy=EmbargoPolicy(
            id_=EmbargoPolicy.build_id(_VENDOR.id_),
            actor_id=_VENDOR.id_,
            inbox=f"{_VENDOR.id_}/inbox",
            preferred_duration=timedelta(days=45),
            **_example_stamp(),
        ),
        **_example_stamp(),
    )


def create_case_proposal() -> as_Create:
    """Build ``Create(as_CaseProposal)`` — CP-03-001.

    Sent by the vendor actor to the case-actor service's inbox to request
    case initialization (CP-04-001).  The ``actor`` is the vendor's full
    profile inline, not its URI, so its embargo policy travels with the
    proposal (CP-01-010).
    """
    proposal = make_case_proposal()
    return as_Create(
        actor=vendor_profile(),
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )


def accept_case_proposal() -> as_Accept:
    """Build ``Accept(as_CaseProposal)`` — CP-03-002.

    Sent by the case-actor service to the vendor's inbox to acknowledge
    acceptance of the proposal.  ``Create(VulnerabilityCase)`` follows
    separately (CP-05-003).
    """
    proposal = make_case_proposal()
    return as_Accept(
        actor=_CASE_ACTOR_URI,
        object_=proposal,
        to=[_VENDOR.id_],
    )


def reject_case_proposal() -> as_Reject:
    """Build ``Reject(as_CaseProposal)`` — CP-03-003.

    Sent by the case-actor service to the vendor's inbox to decline the
    proposal (CP-05-004).
    """
    proposal = make_case_proposal()
    return as_Reject(
        actor=_CASE_ACTOR_URI,
        object_=proposal,
        to=[_VENDOR.id_],
    )
