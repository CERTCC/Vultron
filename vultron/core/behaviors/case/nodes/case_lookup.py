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

Separate from ``conditions.py`` because :class:`RequireCaseForReport` is an
action, not a condition — it writes an output port that downstream nodes
consume, so a tree resolves the case once and every later node reads
``/case_id`` (ARCH-15-004).

:class:`CaseIdInputPortMixin` is the matching read side, and lives here rather
than in each consumer's module so the producer/consumer contract for
``/case_id`` has exactly one definition.
"""

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.case import VulnerabilityCase


class RequireCaseForReport(DataLayerActionWithPorts):
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
    """

    def __init__(self, report_id: str | None, name: str | None = None) -> None:
        """Initialize RequireCaseForReport.

        Args:
            report_id: URI of the ``VulnerabilityReport`` whose case is needed.
                ``None`` yields ``FAILURE`` — there is nothing to resolve.
            name: Optional custom node name (defaults to the class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"case_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if not self._report_id:
            self.feedback_message = "no report_id — no case to resolve"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case = self.datalayer.find_case_by_report_id(self._report_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = (
                f"no VulnerabilityCase for report '{self._report_id}' in this"
                " actor's store"
            )
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


class CaseIdInputPortMixin:
    """Read the ``/case_id`` blackboard key published by ``RequireCaseForReport``.

    The port is declared optional so a tree may omit the publisher, but a node
    that mixes this in and needs the case MUST treat absence as ``FAILURE``
    (ARCH-15-001) — see :meth:`_resolve_case_id`.  Declaring it required would
    make ``setup()`` raise instead of letting the enclosing composite handle a
    missing case as ordinary control flow.

    Every node that needs "the case for this report" mixes this in rather than
    calling ``find_case_by_report_id`` itself, so the lookup happens once per
    tick per tree (ARCH-15-004).
    """

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports: dict[str, PortInformation] = dict(
            super().input_ports()  # type: ignore[misc]
        )
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

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
        store yet (ADR-0073, PCR-01-003) — but it still means the case-scoped
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
