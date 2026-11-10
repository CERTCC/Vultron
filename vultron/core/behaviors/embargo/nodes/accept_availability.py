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

"""The conditions that route an embargo ``Accept`` by availability (MSM-07-012).

An ``Accept(Invite(EmbargoEvent))`` is answered by whether the embargo it
names is still available, on time or late (EMB-17-001):
:class:`EmbargoAvailabilityIsNode` is the condition of each diverted answer,
read through the one test
(:func:`~vultron.core.services.embargo_availability.embargo_availability`),
and :class:`CaseHoldsAvailableTermsNode` asks whether the case holds terms
to re-invite a refused accepter to (EMB-17-003).  Both are read-only.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_availability import (
    EmbargoAvailability,
    available_terms,
    embargo_availability,
)

__all__ = ["CaseHoldsAvailableTermsNode", "EmbargoAvailabilityIsNode"]


def _why(
    case: VulnerabilityCase, embargo_id: str, found: EmbargoAvailability
) -> str:
    """The reason *found* gives an ``Accept`` of *embargo_id* on *case*."""
    if found is EmbargoAvailability.NEVER_HELD:
        return (
            f"Embargo '{embargo_id}' was never held by the register of case"
            f" '{case.id_}': the Accept is not understood (MSM-07-039)"
        )
    if found is EmbargoAvailability.UNAVAILABLE:
        status = case.embargo_register_status(embargo_id)
        detail = (
            "it has reached its end time"
            if case.can_answer_embargo(embargo_id)
            else f"the register holds it {status.value}"
        )
        return (
            f"Embargo '{embargo_id}' on case '{case.id_}' is no longer"
            f" available ({detail}), so the Accept is moot (MSM-07-012)"
        )
    return f"Embargo '{embargo_id}' on case '{case.id_}' is available"


class EmbargoAvailabilityIsNode(DataLayerConditionWithPorts):
    """Condition: an ``Accept`` of *embargo_id* finds it *availability*.

    SUCCESS when
    :func:`~vultron.core.services.embargo_availability.embargo_availability`
    finds *availability* at the act's instant, with the reason in ``feedback_message``,
    logged at INFO: the refusal notice of an unavailable embargo carries that
    reason (CLP-05-001).  FAILURE otherwise.  Read-only.  A case or an
    answerable embargo the CASE_MANAGER cannot read raises an internal error:
    it holds its own case (Regime 1, ADR-0087), and a guess here would send
    the Accept down the wrong arm.
    """

    def __init__(
        self,
        case_id: str,
        embargo_id: str,
        availability: EmbargoAvailability,
        *,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._embargo_id = embargo_id
        self.availability = availability

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        found = embargo_availability(
            self.datalayer, case, self._embargo_id, self._require_act_instant()
        )
        if found is not self.availability:
            return Status.FAILURE
        self.feedback_message = _why(case, self._embargo_id, found)
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class CaseHoldsAvailableTermsNode(DataLayerConditionWithPorts):
    """Condition: the case holds an available embargo to invite to.

    SUCCESS when
    :func:`~vultron.core.services.embargo_availability.available_terms`
    names one at the act's instant: the Active Embargo, or an open proposal, before its
    end time (EMB-17-003).  FAILURE when it names none, logged at INFO: the
    refused accepter gets the refusal notice alone (EMB-17-004,
    EMB-17-007).  Read-only.
    """

    def __init__(self, case_id: str, *, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if (
            available_terms(self.datalayer, case, self._require_act_instant())
            is not None
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"case '{self._case_id}' holds no available embargo, so the"
            " refused accepter is invited to nothing (EMB-17-007)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
