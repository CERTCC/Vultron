"""Report-to-others nodes that walk the recipient queues and inject participants."""

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

from py_trees.common import Access

from vultron.core.behaviors.call_out.actuator import ActuationRequest
from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.capabilities.report_management.report_to_others.injection import (
    InjectParticipantCapability,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlwaysSucceed,
    UsuallyFail,
)


class MoreVendors(UsuallyFail):
    """Check whether there are more vendors in the identified queue.

    Semantic function:
        Condition — answer *yes* iff the ``identified_vendors``
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

    def answer(self) -> CallOutAnswer:
        try:
            vendors = self._bb.identified_vendors
        except KeyError:
            return super().answer()
        if vendors:
            return self.yes()
        return super().answer()


class MoreCoordinators(AlmostAlwaysFail):
    """Check whether there are more coordinators in the identified queue.

    Semantic function:
        Condition — answer *yes* iff the ``identified_coordinators``
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

    def answer(self) -> CallOutAnswer:
        try:
            coordinators = self._bb.identified_coordinators
        except KeyError:
            return super().answer()
        if coordinators:
            return self.yes()
        return super().answer()


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


class InjectParticipant(InjectParticipantCapability, AlwaysSucceed):
    """Add a new participant to the case (generic form).

    Simulates :class:`InjectParticipantCapability`,
    whose ports are its blackboard contract (BT-18-021).

    Semantic function:
        Action — pop the first entry from the blackboard list named by
        ``source_key`` and append it to ``potential_participants``.
        When the source key is absent or the list is empty the node
        succeeds as a no-op; the ``More*`` guard upstream prevents this
        node from running when the list is already exhausted.
        Specialized by ``InjectVendor`` and ``InjectCoordinator`` for
        role-specific injection.  The queue mutation is the simulated side
        effect of this Actuator, standing in for a case-management write; it
        is not a declared output, so it bypasses the seam (BT-18-028).

    Simulated blackboard use (beside the capability's contract):
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

    def act(self, request: ActuationRequest) -> CallOutAnswer:
        """Move one queued participant; the simulation keys nothing on *request*."""
        if not self.source_key:
            return self.yes()
        try:
            source = getattr(self._bb, self.source_key)
        except KeyError:
            return self.yes()
        if not source:
            return self.yes()
        participant = source.pop(0)
        setattr(self._bb, self.source_key, source)
        try:
            participants = self._bb.potential_participants
        except KeyError:
            participants = []
        participants.append(participant)
        self._bb.potential_participants = participants
        return self.yes()


class InjectVendor(InjectParticipant):
    """Pop one identified vendor from the queue and inject into the case.

    Semantic function:
        Action — pop the first entry from the ``identified_vendors``
        blackboard list and append it to ``potential_participants``,
        recording that the vendor has been queued for notification.
        When ``identified_vendors`` is absent or empty the node still
        succeeds (no-op); the ``MoreVendors`` guard upstream prevents
        this node from running when the list is already exhausted.

    Simulated blackboard use (beside the capability's contract, which it
    inherits from :class:`InjectParticipantCapability`, BT-18-021):
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

    Simulated blackboard use (beside the capability's contract, which it
    inherits from :class:`InjectParticipantCapability`, BT-18-021):
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

    Its contract is that of :class:`InjectParticipantCapability`, which it
    inherits (BT-18-021).

    Input category: System integration.

    Success probability: 1.00 (``InjectParticipant`` / ``AlwaysSucceed``).

    Automation potential: **High** — case management system write for
    other-party role; fully automatable.
    """
