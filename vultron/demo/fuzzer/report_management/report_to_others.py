#!/usr/bin/env python
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
"""Report-to-others workflow fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Report Management report-to-others workflow (``MaybeReportToOthers``).  Each
node represents an external-dependency touchpoint — a human decision,
environmental check, or system integration hook — that will eventually be
replaced by production logic.

There are 21 nodes covering: party identification, notification tracking,
recipient selection, effort limits, policy compatibility, contact lookup,
RM state management, and participant injection.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/report_to_others.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004,
  BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlwaysSucceed,
    ProbablySucceed,
    SuccessOrRunning,
    UniformSucceedFail,
    UsuallyFail,
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


class AllPartiesKnown(UniformSucceedFail):
    """Check whether all relevant parties for notification have been identified.

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


class IdentifyVendors(SuccessOrRunning):
    """Identify the software vendors responsible for the affected product(s).

    Semantic function:
        Action — identify the software vendors responsible for the
        affected product(s) so they can be notified.  Uses
        ``SuccessOrRunning`` to model that vendor identification may be
        an ongoing (multi-tick) process; never hard-fails.

    Input category: Human decision / System integration.

    Success probability: 0.50 (``SuccessOrRunning``; never returns
    FAILURE).

    Automation potential: **Medium** — CPE/product database lookups,
    SBOM analysis, and NVD product data queries are automatable for known
    products; novel, multi-vendor, or open-source supply-chain cases
    benefit from human review.
    """


class IdentifyCoordinators(SuccessOrRunning):
    """Identify coordinator organizations that should be involved.

    Semantic function:
        Action — identify any coordinator organizations (e.g., CERT/CC,
        national CSIRTs) that should be involved in the disclosure.  Uses
        ``SuccessOrRunning`` to model an ongoing identification process;
        never hard-fails.

    Input category: Human decision / System integration.

    Success probability: 0.50 (``SuccessOrRunning``; never returns
    FAILURE).

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


class ChooseRecipient(AlwaysSucceed):
    """Select the next recipient from the identified-parties list.

    Semantic function:
        Action — select the next recipient from the identified-parties
        list for notification.  Could be fully automated; always succeeds
        in simulation.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — deterministic queue selection from
    the identified-parties list; fully automatable.
    """


class RemoveRecipient(AlwaysSucceed):
    """Remove a recipient from the pending notification queue.

    Semantic function:
        Action — remove a recipient from the pending notification queue
        (after successful notification or after effort limits are
        exceeded).  Always succeeds in simulation.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — queue management operation; fully
    automatable.
    """


class RecipientEffortExceeded(AlmostCertainlyFail):
    """Check whether notification effort for a recipient has exceeded a limit.

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


class PolicyCompatible(ProbablySucceed):
    """Check whether the recipient's disclosure policy is compatible with the case.

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


class FindContact(UsuallySucceed):
    """Look up contact information for the chosen recipient.

    Semantic function:
        Action — look up contact information for the chosen recipient
        (security email, bug bounty platform, disclosure portal).
        Succeeds most of the time; may fail for lesser-known vendors
        with no published security contact.

    Input category: System integration.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — security.txt lookup, PSIRT directory
    queries, FIRST member database, and NVD contact data are all
    automatable for well-known organizations; obscure vendors may require
    manual research.
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


class SetRcptQrmR(AlwaysSucceed):
    """Record notification by transitioning recipient's RM state to RECEIVED.

    Semantic function:
        Action — record that the recipient has been notified by
        transitioning their RM state from START to RECEIVED.  Always
        succeeds in simulation; in production performs a state update.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — RM state write on the case
    participant record; fully automatable.
    """


class TotalEffortLimitMet(AlmostAlwaysFail):
    """Check whether the total notification effort ceiling has been reached.

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


class MoreVendors(UsuallyFail):
    """Check whether there are more vendors in the notification queue.

    Semantic function:
        Condition — check whether there are more vendor parties in the
        identified-but-not-yet-notified queue.  Fails most of the time
        in simulation because the vendor list is usually short.

    Input category: Environmental check.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **High** — query against the vendor
    notification queue; fully automatable.
    """


class MoreCoordinators(AlmostAlwaysFail):
    """Check whether there are more coordinators pending notification.

    Semantic function:
        Condition — check whether there are more coordinator parties
        pending notification.  Fails almost always because the coordinator
        list is typically short (often zero or one).

    Input category: Environmental check.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — query against the coordinator
    notification queue; fully automatable.
    """


class MoreOthers(AlmostAlwaysFail):
    """Check whether there are more "other" parties pending notification.

    Semantic function:
        Condition — check whether there are more "other" parties pending
        notification.  Fails almost always; catch-all category is usually
        empty.

    Input category: Environmental check.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — query against the other-parties
    notification queue; fully automatable.
    """


class InjectParticipant(AlwaysSucceed):
    """Add a new participant to the case (generic form).

    Semantic function:
        Action — add a new participant to the case.  This is the generic
        base node; specialized by ``InjectVendor``,
        ``InjectCoordinator``, and ``InjectOther`` for role-specific
        injection.  Always succeeds in simulation; in production
        performs a case management system write.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — case management system write; fully
    automatable once participant details are known.
    """


class InjectVendor(InjectParticipant):
    """Add an identified vendor as a participant in the disclosure case.

    Semantic function:
        Action — add an identified vendor as a participant in the
        coordinated disclosure case.  Specialization of
        ``InjectParticipant`` for the vendor role.  Always succeeds in
        simulation; in production performs a case management system write
        with vendor role attribution.

    Input category: System integration.

    Success probability: 1.00 (``InjectParticipant`` / ``AlwaysSucceed``).

    Automation potential: **High** — case management system write for
    vendor role; fully automatable.
    """


class InjectCoordinator(InjectParticipant):
    """Add an identified coordinator as a participant in the disclosure case.

    Semantic function:
        Action — add an identified coordinator as a participant in the
        coordinated disclosure case.  Specialization of
        ``InjectParticipant`` for the coordinator role.  Always succeeds
        in simulation; in production performs a case management system
        write with coordinator role attribution.

    Input category: System integration.

    Success probability: 1.00 (``InjectParticipant`` / ``AlwaysSucceed``).

    Automation potential: **High** — case management system write for
    coordinator role; fully automatable.
    """


class InjectOther(InjectParticipant):
    """Add any other identified party as a participant in the disclosure case.

    Semantic function:
        Action — add any other identified party as a participant in the
        coordinated disclosure case.  Specialization of
        ``InjectParticipant`` for the other-party role.  Always succeeds
        in simulation; in production performs a case management system
        write with other-party role attribution.

    Input category: System integration.

    Success probability: 1.00 (``InjectParticipant`` / ``AlwaysSucceed``).

    Automation potential: **High** — case management system write for
    other-party role; fully automatable.
    """
