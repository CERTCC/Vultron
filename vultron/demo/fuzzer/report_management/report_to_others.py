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

from py_trees.common import Access, Status

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
from vultron.demo.fuzzer.call_out_point import (
    EvaluatorCallOutPoint,
    RetrieverCallOutPoint,
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


class AllPartiesKnown(EvaluatorCallOutPoint, UniformSucceedFail):
    """Check whether all relevant parties for notification have been identified.

    Semantic function:
        Condition — check whether all relevant parties that should receive
        notification have been identified.  Modeled as a coin flip in
        simulation because identification completeness is inherently
        uncertain.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates party-identification state from caller's DataLayer)
      Output keys: all_parties_known_verdict: str  (SUCCESS only)

    Input category: Human decision / Environmental check.

    Success probability: 0.50 (``UniformSucceedFail``).

    Automation potential: **Low** — inherently requires human expert
    judgment about stakeholder completeness in a specific vulnerability
    context; hard to automate reliably.
    """

    output_keys = {"all_parties_known_verdict": str}


class IdentifyVendors(RetrieverCallOutPoint, SuccessOrRunning):
    """Identify the software vendors responsible for the affected product(s).

    Semantic function:
        Action — identify the software vendors responsible for the
        affected product(s) so they can be notified.  Uses
        ``SuccessOrRunning`` to model that vendor identification may be
        an ongoing (multi-tick) process; never hard-fails.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries CPE/product databases and SBOM data)
      Output keys: identified_vendors: list  (SUCCESS only)

    Input category: Human decision / System integration.

    Success probability: 0.50 (``SuccessOrRunning``; never returns
    FAILURE).

    Automation potential: **Medium** — CPE/product database lookups,
    SBOM analysis, and NVD product data queries are automatable for known
    products; novel, multi-vendor, or open-source supply-chain cases
    benefit from human review.
    """

    output_keys = {"identified_vendors": list}


class IdentifyCoordinators(RetrieverCallOutPoint, SuccessOrRunning):
    """Identify coordinator organizations that should be involved.

    Semantic function:
        Action — identify any coordinator organizations (e.g., CERT/CC,
        national CSIRTs) that should be involved in the disclosure.  Uses
        ``SuccessOrRunning`` to model an ongoing identification process;
        never hard-fails.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries FIRST member directory and CSIRT registries)
      Output keys: identified_coordinators: list  (SUCCESS only)

    Input category: Human decision / System integration.

    Success probability: 0.50 (``SuccessOrRunning``; never returns
    FAILURE).

    Automation potential: **Medium** — FIRST member directory and national
    CSIRT registry lookups are automatable; routing policy (when to involve
    a coordinator) may require human judgment.
    """

    output_keys = {"identified_coordinators": list}


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


class ChooseRecipient(RetrieverCallOutPoint, AlwaysSucceed):
    """Select the next recipient from the identified-parties list.

    Semantic function:
        Action — select the next recipient from the identified-parties
        list for notification.  Could be fully automated; always succeeds
        in simulation.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads pending notification queue from DataLayer)
      Output keys: chosen_recipient: str  (SUCCESS only)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — deterministic queue selection from
    the identified-parties list; fully automatable.
    """

    output_keys = {"chosen_recipient": str}


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


class RecipientEffortExceeded(EvaluatorCallOutPoint, AlmostCertainlyFail):
    """Check whether notification effort for a recipient has exceeded a limit.

    Semantic function:
        Condition — check whether the effort spent trying to notify a
        specific recipient has exceeded an organizational threshold
        (e.g., 3 contact attempts, 1 hour of effort).  Rarely triggers
        in simulation; in production enforces reasonable limits on
        notification attempts.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates per-recipient effort counter from caller's DataLayer)
      Output keys: recipient_effort_exceeded_verdict: str  (SUCCESS only)

    Input category: Environmental check / Human decision.

    Success probability: 0.07 (``AlmostCertainlyFail``).

    Automation potential: **High** — effort counter check against a
    configurable policy threshold; fully automatable once the threshold
    policy is defined.
    """

    output_keys = {"recipient_effort_exceeded_verdict": str}


class PolicyCompatible(EvaluatorCallOutPoint, ProbablySucceed):
    """Check whether the recipient's disclosure policy is compatible with the case.

    Semantic function:
        Condition — check whether the potential recipient's
        disclosure/embargo policy is compatible with the case's current
        embargo expectations before notifying them.  In production may
        involve structured policy comparison tooling.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates recipient and case policy from caller's DataLayer)
      Output keys: policy_compatible_verdict: str  (SUCCESS only)

    Input category: Environmental check / Human decision.

    Success probability: 0.67 (``ProbablySucceed``).

    Automation potential: **Medium** — comparison between the recipient's
    published CVD policy and the case embargo terms is automatable for
    machine-readable policies (e.g., OpenVEX, structured security.txt);
    human review needed for ambiguous or informal policies.
    """

    output_keys = {"policy_compatible_verdict": str}


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


class TotalEffortLimitMet(EvaluatorCallOutPoint, AlmostAlwaysFail):
    """Check whether the total notification effort ceiling has been reached.

    Semantic function:
        Condition — check whether the total effort across all notification
        attempts has exceeded an organizational ceiling (e.g., 20 hours
        total).  Rarely triggers in simulation; provides a global stop
        condition to prevent unbounded notification effort.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates total effort counter from caller's DataLayer)
      Output keys: total_effort_limit_met_verdict: str  (SUCCESS only)

    Input category: Environmental check / Human decision.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — aggregate effort counter check
    against a configurable policy ceiling; fully automatable.
    """

    output_keys = {"total_effort_limit_met_verdict": str}


class MoreVendors(UsuallyFail):
    """Check whether there are more vendors in the identified queue.

    Semantic function:
        Condition — return SUCCESS iff the ``identified_vendors``
        blackboard list is non-empty.  When the key is absent or empty
        (i.e., ``IdentifyVendors`` has not run yet or produced nothing),
        falls back to probabilistic behaviour (``UsuallyFail``, 25%).
        This drives exhaustion-based loop iteration: the inner Sequence
        ``[MoreVendors, InjectVendor]`` ticks until the list is drained.

    Blackboard contract (BT-18-001):
      Input keys:  identified_vendors: list  (READ; key may be absent)
      Output keys: (none)

    Input category: Environmental check.

    Success probability: 0.25 (``UsuallyFail``) when blackboard key is
    absent or empty; 1.0 when ``identified_vendors`` is non-empty.

    Automation potential: **High** — queue-emptiness check; fully
    automatable.
    """

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self._bb = self.attach_blackboard_client(
            name=f"{self.__class__.__name__}_reader"
        )
        self._bb.register_key("identified_vendors", Access.READ)

    def update(self) -> Status:
        try:
            vendors = self._bb.identified_vendors
        except KeyError:
            return super().update()
        if vendors:
            return Status.SUCCESS
        return super().update()


class MoreCoordinators(AlmostAlwaysFail):
    """Check whether there are more coordinators in the identified queue.

    Semantic function:
        Condition — return SUCCESS iff the ``identified_coordinators``
        blackboard list is non-empty.  When the key is absent or empty
        falls back to probabilistic behaviour (``AlmostAlwaysFail``,
        10%).  Mirrors ``MoreVendors`` for the coordinator sub-list.

    Blackboard contract (BT-18-001):
      Input keys:  identified_coordinators: list  (READ; key may be absent)
      Output keys: (none)

    Input category: Environmental check.

    Success probability: 0.10 (``AlmostAlwaysFail``) when blackboard key
    is absent or empty; 1.0 when ``identified_coordinators`` is non-empty.

    Automation potential: **High** — queue-emptiness check; fully
    automatable.
    """

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        self._bb = self.attach_blackboard_client(
            name=f"{self.__class__.__name__}_reader"
        )
        self._bb.register_key("identified_coordinators", Access.READ)

    def update(self) -> Status:
        try:
            coordinators = self._bb.identified_coordinators
        except KeyError:
            return super().update()
        if coordinators:
            return Status.SUCCESS
        return super().update()


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
        Action — pop the first entry from the blackboard list named by
        ``source_key`` and append it to ``potential_participants``.
        When the source key is absent or the list is empty the node
        succeeds as a no-op; the ``More*`` guard upstream prevents this
        node from running when the list is already exhausted.
        Specialized by ``InjectVendor`` and ``InjectCoordinator`` for
        role-specific injection.

    Blackboard contract (BT-18-001):
      Input keys:  <source_key>: list  (READ/WRITE; key may be absent)
      Output keys: potential_participants: list  (WRITE; key may be absent)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — case management system write; fully
    automatable once participant details are known.
    """

    source_key: str = ""

    def setup(self, **kwargs) -> None:
        super().setup(**kwargs)
        if self.source_key:
            self._bb = self.attach_blackboard_client(
                name=f"{self.__class__.__name__}_rw"
            )
            self._bb.register_key(self.source_key, Access.WRITE)
            self._bb.register_key("potential_participants", Access.WRITE)

    def update(self) -> Status:
        if not self.source_key:
            return Status.SUCCESS
        try:
            source = getattr(self._bb, self.source_key)
        except KeyError:
            return Status.SUCCESS
        if not source:
            return Status.SUCCESS
        participant = source.pop(0)
        setattr(self._bb, self.source_key, source)
        try:
            participants = self._bb.potential_participants
        except KeyError:
            participants = []
        participants.append(participant)
        self._bb.potential_participants = participants
        return Status.SUCCESS


class InjectVendor(InjectParticipant):
    """Pop one identified vendor from the queue and inject into the case.

    Semantic function:
        Action — pop the first entry from the ``identified_vendors``
        blackboard list and append it to ``potential_participants``,
        recording that the vendor has been queued for notification.
        When ``identified_vendors`` is absent or empty the node still
        succeeds (no-op); the ``MoreVendors`` guard upstream prevents
        this node from running when the list is already exhausted.

    Blackboard contract (BT-18-001):
      Input keys:  identified_vendors: list  (READ/WRITE; key may be absent)
      Output keys: potential_participants: list  (WRITE; key may be absent)

    Input category: System integration.

    Success probability: 1.00 (``InjectParticipant`` / ``AlwaysSucceed``).

    Automation potential: **High** — case management system write for
    vendor role; fully automatable.
    """

    source_key = "identified_vendors"


class InjectCoordinator(InjectParticipant):
    """Pop one identified coordinator from the queue and inject into the case.

    Semantic function:
        Action — pop the first entry from the ``identified_coordinators``
        blackboard list and append it to ``potential_participants``,
        recording that the coordinator has been queued for notification.
        When ``identified_coordinators`` is absent or empty the node
        still succeeds (no-op); the ``MoreCoordinators`` guard upstream
        prevents this node from running when the list is already
        exhausted.

    Blackboard contract (BT-18-001):
      Input keys:  identified_coordinators: list  (READ/WRITE; key may be absent)
      Output keys: potential_participants: list  (WRITE; key may be absent)

    Input category: System integration.

    Success probability: 1.00 (``InjectParticipant`` / ``AlwaysSucceed``).

    Automation potential: **High** — case management system write for
    coordinator role; fully automatable.
    """

    source_key = "identified_coordinators"


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
