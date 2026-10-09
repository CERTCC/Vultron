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

"""Attach and detach an object reference on a case's reference lists.

A ``VulnerabilityCase`` holds its notes and its vulnerability reports as lists of
references.  Adding or removing one is the same edit on a different list, so the
edit lives in one base (:class:`CaseReferenceEditNode`) with a pending-check
twin (:class:`CaseReferenceEditPendingNode`) that lets a tree tell a duplicate
delivery from a fresh one *before* it commits a ledger entry (CLP-10-006).
Concrete nodes only name the list and the direction (BTND-07-005, CS-22-001).
"""

from typing import ClassVar, Literal

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import _as_id

ReferenceField = Literal["notes", "vulnerability_reports"]


class CaseReferenceEditNode(DataLayerActionWithPorts, StateWriteCapable):
    """Add or remove one reference on a case list, idempotently.

    Subclasses set ``FIELD`` (the case list) and ``ATTACH`` (``True`` adds the
    reference, ``False`` removes it).  A ``case_id`` of ``None`` is a no-op
    success, for trees that run with no case context.
    """

    FIELD: ClassVar[ReferenceField]
    ATTACH: ClassVar[bool]

    def __init__(
        self,
        ref_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.ref_id = ref_id
        self.case_id = case_id

    def update(self) -> Status:
        if self.case_id is None:
            self.logger.debug("%s: no case_id — skipping case edit", self.name)
            return Status.SUCCESS

        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        refs = getattr(case, self.FIELD)
        present = self.ref_id in [_as_id(r) for r in refs]
        if present == self.ATTACH:
            self.logger.info(
                "%s: '%s' already %s case '%s' %s — skipping (idempotent)",
                self.name,
                self.ref_id,
                "in" if self.ATTACH else "absent from",
                self.case_id,
                self.FIELD,
            )
            return Status.SUCCESS

        if self.ATTACH:
            refs.append(self.ref_id)
        else:
            refs[:] = [r for r in refs if _as_id(r) != self.ref_id]
        self.datalayer.save(case)
        self.logger.info(
            "%s: %s '%s' %s case '%s' %s",
            self.name,
            "attached" if self.ATTACH else "detached",
            self.ref_id,
            "to" if self.ATTACH else "from",
            self.case_id,
            self.FIELD,
        )
        return Status.SUCCESS


class CaseReferenceEditPendingNode(DataLayerConditionWithPorts):
    """Guard: the edit would change the case's list (it is not a duplicate).

    ``SUCCESS`` when attaching a reference the case lacks, or detaching one it
    holds.  ``FAILURE`` with ``is_duplicate`` set is the duplicate delivery: a
    handler reports ``SKIPPED``, with nothing committed.
    Any other ``FAILURE`` (no datalayer, unknown case) is not a duplicate and
    stays a refusal.
    """

    def __init__(
        self,
        ref_id: str,
        case_id: str,
        field: ReferenceField,
        attach: bool,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.ref_id = ref_id
        self.case_id = case_id
        self.field = field
        self.attach = attach
        #: True only after the edit was found to be a duplicate; a missing
        #: datalayer or case also fails the node but is not a duplicate.
        self.is_duplicate = False

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        present = self.ref_id in [_as_id(r) for r in getattr(case, self.field)]
        if present != self.attach:
            return Status.SUCCESS
        self.is_duplicate = True
        self.feedback_message = (
            f"'{self.ref_id}' is already"
            f" {'in' if self.attach else 'absent from'} case"
            f" '{self.case_id}' {self.field}"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class AttachReportToCaseNode(CaseReferenceEditNode):
    """Attach a vulnerability report id to ``case.vulnerability_reports``."""

    FIELD: ClassVar[ReferenceField] = "vulnerability_reports"
    ATTACH: ClassVar[bool] = True

    def __init__(
        self,
        report_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(ref_id=report_id, case_id=case_id, name=name)
        self.report_id = report_id
