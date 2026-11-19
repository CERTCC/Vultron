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

"""Case resolution for a report: one producer, one consumer mixin.

Separate from ``conditions.py`` because :class:`RequireCaseForReport` and
:class:`FindCaseForReport` are actions, not conditions — they write an output
port that downstream nodes consume, so a tree resolves the case once and every
later node reads ``/case_id`` (ARCH-15-004).  A trigger tree uses
:class:`RequireCaseForReport`, which fails on a miss; a received report tree
uses :class:`FindCaseForReport`.

:class:`CaseIdInputPortMixin` is the matching read side, and lives here rather
than in each consumer's module so the producer/consumer contract for
``/case_id`` has exactly one definition.

:class:`FindCaseForReport` is the lookup a received report tree runs ahead
of its path stage (BT-25-009): it publishes the report's case and never
refuses, and :class:`CaseFoundForReport` refuses the miss where the tree
places it (BT-25-010).  Every report node reads ``/report_id``
(BTND-01-008).

:class:`CaseResolving` marks a node a received tree may run ahead of its
sender guard to resolve the case the guard reads (``case_resolution``).
"""

from typing import Any

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    optional_act_value,
)
from vultron.core.behaviors.act_keys import CASE_ID, REPORT_ID
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import DeclaredRefusalMixin
from vultron.core.models.case import VulnerabilityCase

#: The name a report's miss guard takes, the step it replaced, so a tree
#: dump and a refusal read as they did when the case was resolved there.
CASE_FOUND_NODE_NAME = "RequireCaseForReport"

#: Why a report with no report id has no case to resolve.
NO_REPORT_ID = "no report_id — no case to resolve"


def no_case_for_report(report_id: str) -> str:
    """Why *report_id* has no case: this store holds none for it (#2255)."""
    return (
        f"no VulnerabilityCase for report '{report_id}' in this actor's store"
    )


class CaseResolving:
    """Marker mixin: this node resolves a case and writes only blackboard keys.

    Carries no behaviour.  ``create_receive_activity_tree`` runs a received
    tree's ``case_resolution`` steps before the sender guard, so it admits
    only nodes that carry this marker: a sender with no standing must leave
    nothing behind (HP-01-006).  Mark a node only when its ``update()``
    writes no DataLayer record and enqueues no activity.
    """


class RequireCaseForReport(CaseResolving, DataLayerActionWithPorts):
    """Resolve this actor's own case replica for a report and publish ``/case_id``.

    This is the single canonical place where a behavior tree asserts "the case
    for this report must be present in *my* store before I act on it"
    (ARCH-15-004).  Returns ``SUCCESS`` and writes the case URI to the
    ``/case_id`` blackboard key when the case is found; returns ``FAILURE``
    otherwise, per ARCH-15-001 — a required key that resolves to nothing must
    not be reported as ``SUCCESS``.

    Why absence is a hard failure, not a soft pass
    ----------------------------------------------
    ADR-0073 gives every actor its own store, and PCR-01-003 makes co-location
    irrelevant to the protocol: whether the CaseActor runs on this host or
    another, its case reaches this actor only as a ``Create(VulnerabilityCase)``
    replica (ADR-0041, CBT-01-002).  So "no case here" is a real, expected,
    transient state — the replica has not arrived yet — and it means the
    case-scoped work cannot be done.  Soft-passing it lets downstream nodes
    write records for transitions that never happened, which is how a
    report-phase RM latch gets written while the participant's case-scoped RM
    state stays behind (ISSUE-2548).

    Nodes downstream of this one read ``/case_id`` instead of repeating the
    lookup, so the tree has exactly one case-resolution site.

    The ``/case_id`` write is a blackboard key, not a DataLayer write, so the
    node is safe in a received tree's ``precondition_guards``: a receiver
    without the case refuses before the commit stage (CLP-10-009).
    """

    def __init__(self, name: str | None = None) -> None:
        """Initialize RequireCaseForReport.

        The report is read from ``/report_id`` when the node ticks
        (BTND-01-008); no report there yields ``FAILURE``, since there is
        nothing to resolve.

        Args:
            name: Optional custom node name (defaults to the class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self._report_id: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **act_key_ports(REPORT_ID),
    }
    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", **act_key_remappings(REPORT_ID)}

    def initialise(self) -> None:
        super().initialise()
        self._report_id = optional_act_value(self, REPORT_ID, str)

    def _find_case(self, report_id: str) -> VulnerabilityCase | None:
        """The lookup subclasses narrow; the rest of ``update`` is shared."""
        assert self.datalayer is not None
        return self.datalayer.find_case_by_report_id(report_id)

    def _absence_message(self, report_id: str) -> str:
        return no_case_for_report(report_id)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self._report_id:
            self.feedback_message = NO_REPORT_ID
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case = self._find_case(self._report_id)
        if case is None:
            self.feedback_message = self._absence_message(self._report_id)
            # INFO, not WARNING: pre-replica is a legitimate transient state on
            # the receiving side, and the normal "no duplicate case yet" path in
            # the case-proposal tree lands here too.
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._set_output("case_id", case.id_)
        self.logger.debug(
            "%s: resolved case '%s' for report '%s'",
            self.name,
            case.id_,
            self._report_id,
        )
        return Status.SUCCESS


class FindCaseForReport(RequireCaseForReport):
    """The lookup a received report tree runs first: publish the report's case.

    A received report verdict (``Accept``, ``TentativeReject`` or ``Reject``
    of ``Offer(VulnerabilityReport)``) names its report, never its case, and
    only this store knows which case holds the report.  So the case is a
    per-act value a lookup node finds (BT-25-009), and this is that node: it
    runs ahead of the path stage, which reads the receiver's role in the case
    it published (ADR-0153), and every later node of the tree reads the same
    ``/case_id`` (BT-25-011).

    It never refuses.  A report this store holds no case for publishes
    nothing and succeeds, so the path stage puts the receiver on the no-case
    path and the tree's declaration decides the delivery there, exactly as
    when the case was read before the tree ran (HP-01-039, HP-01-041).  The
    miss is refused by :class:`CaseFoundForReport`, which a tree places where
    its unknown-case refusal belongs (BT-25-010, #2255).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self._find_case(self._report_id) if self._report_id else None
        if case is None:
            # A miss is an answer, not a refusal: the declaration decides it.
            self.logger.debug(
                "%s: no case in this store for report '%s'; the tree's"
                " declaration decides the delivery",
                self.name,
                self._report_id,
            )
            return Status.SUCCESS
        self._set_output("case_id", case.id_)
        self.logger.debug(
            "%s: found case '%s' for report '%s'",
            self.name,
            case.id_,
            self._report_id,
        )
        return Status.SUCCESS


class CaseFoundForReport(
    DeclaredRefusalMixin, CaseResolving, DataLayerConditionWithPorts
):
    """Refuse a report whose case :class:`FindCaseForReport` did not find.

    The miss half of the report lookup (BT-25-010): it reads ``/case_id``
    and ``/report_id`` and fails, with the reason the lookup gives, when no
    case was published for the report.  It reads no store and publishes
    nothing, so the lookup stays the one source of ``/case_id`` (BT-25-011).
    It declares the refusal, naming the report and citing BT-25-010
    (:class:`~vultron.core.behaviors.idempotency.ReportsRefusal`).  It may
    run before the sender guard (``case_resolution``) or among the
    precondition guards, wherever the tree refuses an activity about a case
    this store does not hold (#2255).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        **act_key_ports(CASE_ID, REPORT_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(CASE_ID, REPORT_ID)

    def __init__(self, name: str = CASE_FOUND_NODE_NAME) -> None:
        super().__init__(name=name)
        self._case_id: str | None = None
        self._report_id: str | None = None

    def initialise(self) -> None:
        super().initialise()
        self._case_id = optional_act_value(self, CASE_ID, str)
        self._report_id = optional_act_value(self, REPORT_ID, str)

    def update(self) -> Status:
        if self._case_id:
            return Status.SUCCESS
        self.feedback_message = (
            no_case_for_report(self._report_id)
            if self._report_id
            else NO_REPORT_ID
        )
        # INFO, not WARNING: the replica may not have arrived yet, a
        # legitimate transient state on the receiving side.
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return self._refuse(f"{self.feedback_message} (BT-25-010)")


class CaseIdInputPortMixin:
    """Read the ``/case_id`` blackboard key a report lookup published.

    The publisher is ``RequireCaseForReport`` in a trigger tree and
    ``FindCaseForReport`` in a received report tree.

    The port is declared optional so a tree may omit the publisher, but a node
    that mixes this in and needs the case MUST treat absence as ``FAILURE``
    (ARCH-15-001) — see :meth:`_resolve_case_id`.  Declaring it required would
    make ``setup()`` raise instead of letting the enclosing composite handle a
    missing case as ordinary control flow.

    Every node that needs "the case for this report" mixes this in rather than
    calling ``find_case_by_report_id`` itself, so the lookup happens once per
    tick per tree (ARCH-15-004).
    """

    # Annotation only: binding a value here would make every class that mixes
    # this in look like it had declared its ports (py_trees' abstract check).
    INPUT_PORTS: dict[str, PortInformation]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # A mixin cannot merge a class attribute through ``super()``, so add
        # the port to whatever ``INPUT_PORTS`` the class ends up with. This
        # runs before ``PortsMixin.__init_subclass__`` (the mixin precedes
        # the ports base in the MRO), so the port is validated with the rest.
        # No fallback: a class with no ``INPUT_PORTS`` to extend raises here
        # rather than silently declaring ``case_id`` alone.
        cls.INPUT_PORTS = {
            **cls.INPUT_PORTS,
            "case_id": PortInformation(data_type=str, required=False),
        }
        super().__init_subclass__(**kwargs)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        remappings = dict(super()._domain_port_remappings())  # type: ignore[misc]
        remappings["case_id"] = "/case_id"
        return remappings

    def initialise(self) -> None:
        super().initialise()  # type: ignore[misc]
        self._case_id: str | None = None
        value = self._try_get_input("case_id")  # type: ignore[attr-defined]
        if isinstance(value, str) and value:
            self._case_id = value

    def _resolve_case_id(self) -> str | None:
        """Return the blackboard ``case_id``, or ``None`` after logging why not.

        Callers turn ``None`` into ``Status.FAILURE``.  Absence is expected and
        transient — the case replica has not been delivered to this actor's
        store yet (ADR-0073, PCR-01-007) — but it still means the case-scoped
        work cannot be performed, so it must never be reported as SUCCESS
        (ARCH-15-001, ISSUE-2548).
        """
        if self._case_id:
            return self._case_id
        self.feedback_message = (  # type: ignore[attr-defined]
            "no case_id on the blackboard — the case for this report is not in"
            " this actor's store yet; RequireCaseForReport must run first"
        )
        self.logger.warning(  # type: ignore[attr-defined]
            "%s: %s",
            self.name,  # type: ignore[attr-defined]
            self.feedback_message,  # type: ignore[attr-defined]
        )
        return None
