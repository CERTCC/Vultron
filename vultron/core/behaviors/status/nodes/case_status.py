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

"""Case status workflow nodes for AddCaseStatusToCase.

Contains the idempotency guard of the AddCaseStatusToCase BT sequence
(issue #758).  The tree appends nothing: a participant replica takes the
CASE_MANAGER's status from the ledger fan-out (RSH-04-005, RSH-08-003).

:class:`~vultron.core.behaviors.case_status_snapshot.EmitCaseStatusUpdateNode`,
which embargo and status trees both compose, lives in the shared
:mod:`vultron.core.behaviors.case_status_snapshot` module (BTND-04-001).

The whole accept-or-reject guard (RSH-09-005) lives in
:mod:`case_status_acceptance`.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.idempotency import SilentIdempotencyGuardMixin
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)

# Stable sentinel used as feedback_message when a CaseStatus duplicate is
# detected.  The use case imports this constant to distinguish idempotent
# no-ops (log at INFO) from real failures (log at WARNING).
CASE_STATUS_ALREADY_PRESENT = "case_status_already_present"


class CheckCaseStatusIdempotencyNode(
    SilentIdempotencyGuardMixin, DataLayerConditionWithPorts
):
    """AC-1: Verify the CaseStatus has not already been added to the case.

    Returns FAILURE with ``feedback_message == CASE_STATUS_ALREADY_PRESENT``
    when *status_id* is already in ``case.case_statuses`` — a benign no-op
    with no ledger write (CLP-13-001, CLP-13-002).

    Returns FAILURE with a distinct message when the case itself is not found.

    Returns SUCCESS when the status is not yet present and the Sequence should
    continue.

    Per issue #758 AC-1.
    """

    def __init__(
        self,
        case_id: str | None,
        status_id: str,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.status_id = status_id

    def update(self) -> Status:
        if not self.case_id:
            self.feedback_message = (
                "case_id is absent — cannot check idempotency"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        existing_ids = [_as_id(s) for s in case.case_statuses]
        if self.status_id in existing_ids:
            self.feedback_message = CASE_STATUS_ALREADY_PRESENT
            return self._idempotent_failure(
                self.logger,
                "CheckCaseStatusIdempotency: status '%s' already in case '%s'"
                " — skipping (idempotent, CLP-13-001)",
                self.status_id,
                self.case_id,
            )

        return Status.SUCCESS
