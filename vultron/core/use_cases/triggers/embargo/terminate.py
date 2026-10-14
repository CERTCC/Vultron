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

"""Embargo termination trigger use case.

``reason=EARLY`` (the default) ends the embargo in force on the actor's own
decision.  ``reason=END_TIME_REACHED`` is an outside request to end it at its
end time, such as a Sentinel monitoring embargo timers sends: it runs the
same idempotent path as the CASE_MANAGER's lazy check
(:func:`~vultron.core.behaviors.embargo.end_time_tree.end_embargo_at_end_time_bt`),
is refused before the end time, and is answered as already done — no
activity — once the embargo has ended (ADR-0122).  An ``EARLY`` request made
once the end time has passed takes that path too, so the embargo is recorded
as ending at its end time (EMB-13-003).
"""

import json
import logging
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.embargo.end_time_tree import (
    EMBARGO_ALREADY_ENDED_KEY,
    end_embargo_at_end_time_bt,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.models._helpers import now_utc
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.models.events.base import MessageSemantics
from vultron.core.services.embargo_lifecycle import (
    embargo_end_time_passed,
    termination_timing_violations,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.use_cases.triggers._base import SvcEmbargoTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    _coerce_embargo_event,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


class SvcTerminateEmbargoUseCase(SvcEmbargoTriggerBase):
    _assertion_event_type: ClassVar[str] = (
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE.value
    )

    def _prepare(self) -> None:
        request = cast(TerminateEmbargoTriggerRequest, self._request)
        dl = self._dl

        actor = resolve_actor(request.actor_id, dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, dl)
        self._reason: TerminationReason = request.reason
        self._now = now_utc()

        # Resolve embargo_id only when active_embargo is set; when it is None
        # the HasActiveEmbargoNode BT precondition will halt the tree with a
        # typed VultronInvalidStateTransitionError before activity construction.
        embargo_id = self._case.active_embargo_id
        if embargo_id is not None:
            _coerce_embargo_event(dl.read(embargo_id), embargo_id)
        self._embargo_id = embargo_id or ""

        # Once the end time has passed, the embargo ends with
        # END_TIME_REACHED whatever was asked (EMB-13-003): this trigger runs
        # the end-time path itself, so its row opts out of the lazy check.
        if self._reason == TerminationReason.EARLY and embargo_end_time_passed(
            dl, self._case, self._now
        ):
            logger.info(
                "Actor '%s': embargo on case '%s' has reached its end time —"
                " ending it with END_TIME_REACHED, not EARLY",
                self._actor_id,
                self._case.id_,
            )
            self._reason = TerminationReason.END_TIME_REACHED

        # An end-time request before the end time is refused on every actor,
        # so a participant never asks the CASE_MANAGER for one (ADR-0122).
        violations = termination_timing_violations(
            dl,
            self._case,
            EmbargoTermination.from_reason(self._reason),
            self._now,
        )
        if violations:
            raise VultronInvalidStateTransitionError(
                f"Case '{self._case.id_}': " + "; ".join(violations)
            )

    def _assertion_subject(self) -> str | None:
        return self._embargo_id or None

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activity(to: list[str] | None) -> tuple[str, str]:
            remove_id, remove_blob = self._factory.terminate_embargo(
                embargo_id=self._embargo_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                reason=self._reason,
                to=to,
            )
            self._captured["activity"] = json.loads(remove_blob)
            return remove_id, remove_blob

        if self._reason == TerminationReason.END_TIME_REACHED:
            return end_embargo_at_end_time_bt(
                case_id=self._case.id_,
                result_out=self._result_out,
                now=self._now,
                activity_builder=_build_activity,
            )
        return terminate_embargo_bt(
            case_id=self._case.id_,
            result_out=self._result_out,
            termination=EmbargoTermination.early(),
            activity_builder=_build_activity,
        )

    def _handle_result(self) -> None:
        if self._result_out.get(EMBARGO_ALREADY_ENDED_KEY):
            # The other end-time request ended it first: nothing committed.
            logger.info(
                "Actor '%s': embargo on case '%s' had already ended —"
                " end-time request answered as already done",
                self._actor_id,
                self._case.id_,
            )
            return
        super()._handle_result()

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        logger.info(
            "Actor '%s' terminated embargo '%s' on case '%s' (%s; EM %s → %s)",
            self._actor_id,
            self._embargo_id,
            self._case.id_,
            self._reason,
            lr.em_before,
            lr.em_after,
        )
