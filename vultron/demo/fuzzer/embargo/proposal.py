"""Embargo negotiation and proposal fuzzer nodes."""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from vultron.core.behaviors.call_out.capabilities.embargo.proposal import (
    ReasonToProposeEmbargoWhenDeployedCapability,
    SelectEmbargoOfferTermsCapability,
    StopProposingEmbargoCapability,
    WantToProposeEmbargoCapability,
    WillingToCounterEmbargoProposalCapability,
)
from vultron.demo.fuzzer.base import (
    AlmostCertainlyFail,
    AlwaysSucceed,
    RandomSucceedFail,
    UsuallyFail,
    UsuallySucceed,
)

# ---------------------------------------------------------------------------
# Embargo negotiation / proposal nodes
# ---------------------------------------------------------------------------


class StopProposingEmbargo(StopProposingEmbargoCapability, UsuallyFail):
    """Decide whether to abandon an ongoing embargo negotiation.

    Simulates :class:`StopProposingEmbargoCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — human or policy decision to give up on negotiating an
        embargo (e.g., too many counter-proposals, time pressure).
        Modeled as uncommon; parties are usually willing to keep
        negotiating.

    Input category: Human decision.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Low** — negotiation-fatigue judgment depends on
    relationship context and subjective assessment of negotiation
    prospects; requires human decision.
    """


class SelectEmbargoOfferTerms(
    SelectEmbargoOfferTermsCapability, AlwaysSucceed
):
    """Select the specific terms to include in an embargo proposal.

    Simulates :class:`SelectEmbargoOfferTermsCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — choose duration, conditions, and other terms for a new
        embargo proposal or counter-proposal.  In production may involve
        negotiation-support tooling or organizational policy lookup.

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — standard terms can be drawn from
    organizational policy templates automatically; atypical situations may
    need human review.
    """


class WantToProposeEmbargo(WantToProposeEmbargoCapability, RandomSucceedFail):
    """Decide whether to initiate an embargo negotiation.

    Simulates :class:`WantToProposeEmbargoCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — does the participant currently wish to propose an
        embargo?  Depends on case context, role, and organizational
        policy.  The fuzzer exercises both paths equally; in production
        the recommended default is to propose an embargo.

    Input category: Human decision.

    Success probability: 0.50 (``RandomSucceedFail``).

    Automation potential: **Medium** — default policy (always propose) can
    be automated; exceptions (already-public vulnerability, no vendor
    identified) could be rule-encoded, but edge cases may need human
    override.
    """


class WillingToCounterEmbargoProposal(
    WillingToCounterEmbargoProposalCapability, UsuallyFail
):
    """Decide whether to counter an incoming embargo proposal.

    Simulates :class:`WillingToCounterEmbargoProposalCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — is the participant willing to respond to an incoming
        proposal with a counter-proposal rather than accepting or
        rejecting outright?  The recommended behavior is to accept the
        current proposal and negotiate revisions separately; countering is
        intentionally modeled as uncommon.

    Input category: Human decision.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Low** — nuanced negotiation judgment about
    whether countering is strategically preferable to accepting and
    revising; best left to human discretion.
    """


class AvoidEmbargoCounterProposal(UsuallySucceed):
    """Prefer accepting an embargo proposal over issuing a counter-proposal.

    Semantic function:
        Condition — convenience complement of
        ``WillingToCounterEmbargoProposal``.  Returns ``SUCCESS`` when
        the participant should *not* counter (i.e., accept or reject
        directly), and ``FAILURE`` when a counter-proposal is warranted.
        Derived as the logical inversion of
        ``WillingToCounterEmbargoProposal`` (p=0.25 → p=0.75).

    Input category: Human decision (derived).

    Success probability: 0.75 (complement of ``WillingToCounterEmbargoProposal``).

    Automation potential: **Low** — mirrors the inverted decision from
    ``WillingToCounterEmbargoProposal``; same human-discretion constraints
    apply.
    """


class ReasonToProposeEmbargoWhenDeployed(
    ReasonToProposeEmbargoWhenDeployedCapability, AlmostCertainlyFail
):
    """Decide whether to start a new embargo after the fix is already deployed.

    Simulates :class:`ReasonToProposeEmbargoWhenDeployedCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — is there an unusual reason to propose an embargo even
        though the fix has already been deployed?  Post-deployment embargo
        proposals are exceptional and very rare.

    Input category: Human decision.

    Success probability: 0.07 (``AlmostCertainlyFail``).

    Automation potential: **Low** — highly exceptional circumstance; no
    general rule can anticipate valid reasons, so human judgment is
    required.
    """
