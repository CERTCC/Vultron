"""Report-to-others nodes that identify, choose and vet recipients."""

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

from vultron.core.behaviors.call_out.capabilities.report_management.report_to_others.recipients import (
    AllPartiesKnownCapability,
    ChooseRecipientCapability,
    IdentifyCoordinatorsCapability,
    IdentifyVendorsCapability,
    PolicyCompatibleCapability,
    RecipientEffortExceededCapability,
    RemoveRecipientCapability,
    SetRcptQrmRCapability,
    TotalEffortLimitMetCapability,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlwaysSucceed,
    ProbablySucceed,
    UniformSucceedFail,
    UsuallySucceed,
)


class HaveReportToOthersCapability(UsuallySucceed):
    """Check whether this participant has the capability to notify others.

    Semantic function:
        Condition — check whether this participant has the capability and
        mandate to notify other parties about the vulnerability.  In
        production this is typically a static capability check against
        the participant's CVD role and organizational policy.

    Input category: Environmental check.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — static capability and role
    configuration check; fully automatable as a metadata lookup.
    """


class AllPartiesKnown(AllPartiesKnownCapability, UniformSucceedFail):
    """Check whether all relevant parties for notification have been identified.

    Simulates :class:`AllPartiesKnownCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — check whether all relevant parties that should receive
        notification have been identified.  Modeled as a coin flip in
        simulation because identification completeness is inherently
        uncertain.

    Input category: Human decision / Environmental check.

    Success probability: 0.50 (``UniformSucceedFail``).

    Automation potential: **Low** — inherently requires human expert
    judgment about stakeholder completeness in a specific vulnerability
    context; hard to automate reliably.
    """


class IdentifyVendors(IdentifyVendorsCapability, AlwaysSucceed):
    """Identify the software vendors responsible for the affected product(s).

    Simulates :class:`IdentifyVendorsCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — identify the software vendors responsible for the
        affected product(s) so they can be notified.  A call-out point MUST
        answer synchronously (BT-18-011, ADR-0080), so it is modeled with
        ``AlwaysSucceed``: identification resolves in one tick and never
        hard-fails.

    Input category: Human decision / System integration.

    Success probability: 1.00 (``AlwaysSucceed``; never returns FAILURE).

    Automation potential: **Medium** — CPE/product database lookups,
    SBOM analysis, and NVD product data queries are automatable for known
    products; novel, multi-vendor, or open-source supply-chain cases
    benefit from human review.
    """


class IdentifyCoordinators(IdentifyCoordinatorsCapability, AlwaysSucceed):
    """Identify coordinator organizations that should be involved.

    Simulates :class:`IdentifyCoordinatorsCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — identify any coordinator organizations (e.g., CERT/CC,
        national CSIRTs) that should be involved in the disclosure.  A
        call-out point MUST answer synchronously (BT-18-011, ADR-0080), so it
        is modeled with ``AlwaysSucceed``: identification resolves in one tick
        and never hard-fails.

    Input category: Human decision / System integration.

    Success probability: 1.00 (``AlwaysSucceed``; never returns FAILURE).

    Automation potential: **Medium** — FIRST member directory and national
    CSIRT registry lookups are automatable; routing policy (when to involve
    a coordinator) may require human judgment.
    """


class IdentifyOthers(AlwaysSucceed):
    """Identify any other parties (beyond vendors and coordinators) to notify.

    Semantic function:
        Action — identify any other parties (beyond vendors and
        coordinators) that should be notified.  Always succeeds in
        simulation as a stub placeholder.

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Low** — by definition a catch-all for
    non-vendor, non-coordinator parties; requires human expert assessment
    of the specific disclosure context.
    """


class NotificationsComplete(UniformSucceedFail):
    """Check whether all identified parties have been successfully notified.

    Semantic function:
        Condition — check whether all identified parties have been
        successfully notified.  Modeled as a coin flip; in production
        this is a status check against a notification queue.

    Input category: Environmental check.

    Success probability: 0.50 (``UniformSucceedFail``).

    Automation potential: **High** — notification status tracking against
    the identified-parties queue; fully automatable.
    """


class ChooseRecipient(ChooseRecipientCapability, AlwaysSucceed):
    """Select the next recipient from the identified-parties list.

    Simulates :class:`ChooseRecipientCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — select the next recipient from the identified-parties
        list for notification.  Could be fully automated; always succeeds
        in simulation.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — deterministic queue selection from
    the identified-parties list; fully automatable.
    """


class RemoveRecipient(RemoveRecipientCapability, AlwaysSucceed):
    """Remove a recipient from the pending notification queue.

    Simulates :class:`RemoveRecipientCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — remove a recipient from the pending notification queue
        (after successful notification or after effort limits are
        exceeded).  Always succeeds in simulation.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — queue management operation; fully
    automatable.
    """


class RecipientEffortExceeded(
    RecipientEffortExceededCapability, AlmostCertainlyFail
):
    """Check whether notification effort for a recipient has exceeded a limit.

    Simulates :class:`RecipientEffortExceededCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — check whether the effort spent trying to notify a
        specific recipient has exceeded an organizational threshold
        (e.g., 3 contact attempts, 1 hour of effort).  Rarely triggers
        in simulation; in production enforces reasonable limits on
        notification attempts.

    Input category: Environmental check / Human decision.

    Success probability: 0.07 (``AlmostCertainlyFail``).

    Automation potential: **High** — effort counter check against a
    configurable policy threshold; fully automatable once the threshold
    policy is defined.
    """


class PolicyCompatible(PolicyCompatibleCapability, ProbablySucceed):
    """Check whether the recipient's disclosure policy is compatible with the case.

    Simulates :class:`PolicyCompatibleCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — check whether the potential recipient's
        disclosure/embargo policy is compatible with the case's current
        embargo expectations before notifying them.  In production may
        involve structured policy comparison tooling.

    Input category: Environmental check / Human decision.

    Success probability: 0.67 (``ProbablySucceed``).

    Automation potential: **Medium** — comparison between the recipient's
    published CVD policy and the case embargo terms is automatable for
    machine-readable policies (e.g., OpenVEX, structured security.txt);
    human review needed for ambiguous or informal policies.
    """


class RcptNotInQrmS(AlmostAlwaysSucceed):
    """Verify the recipient has not already been notified (RM state is START).

    Semantic function:
        Condition — verify that the recipient has not already been
        notified (i.e., their RM state is still START / not yet
        RECEIVED).  Succeeds almost always; guards against duplicate
        notifications.

    Input category: Environmental check.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — RM state query against the case
    participant record; fully automatable.
    """


class SetRcptQrmR(SetRcptQrmRCapability, AlwaysSucceed):
    """Record notification by transitioning recipient's RM state to RECEIVED.

    Simulates :class:`SetRcptQrmRCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — record that the recipient has been notified by
        transitioning their RM state from START to RECEIVED.  Always
        succeeds in simulation; in production performs a state update.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — RM state write on the case
    participant record; fully automatable.
    """


class TotalEffortLimitMet(TotalEffortLimitMetCapability, AlmostAlwaysFail):
    """Check whether the total notification effort ceiling has been reached.

    Simulates :class:`TotalEffortLimitMetCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Condition — check whether the total effort across all notification
        attempts has exceeded an organizational ceiling (e.g., 20 hours
        total).  Rarely triggers in simulation; provides a global stop
        condition to prevent unbounded notification effort.

    Input category: Environmental check / Human decision.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — aggregate effort counter check
    against a configurable policy ceiling; fully automatable.
    """
