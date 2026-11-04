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


"""The base of the embargo trigger verbs.

:class:`SvcEmbargoTriggerBase` adds a concrete ``_handle_result()`` for the
two role arms of an embargo trigger tree (EP-09-008).
"""

from abc import abstractmethod
from typing import ClassVar

import py_trees

from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.core.use_cases.triggers._base.activity import (
    SvcActivityTriggerBase,
)


class SvcEmbargoTriggerBase(SvcActivityTriggerBase):
    """Abstract base for embargo trigger use cases.

    A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008), so
    the tree runs one of two arms and :meth:`_handle_result` handles both:

    - **Asked the CASE_MANAGER** (the tree wrote
      ``result_out[ASSERTED_ACTIVITY_KEY]``): records the queued activity in
      the pending-assertion store through the helper the note trigger also
      uses (SYNC-11-002, ASK-04-008).  No EM state was written, so there is
      no lifecycle result.
    - **Decided as the CASE_MANAGER**: extracts and validates
      ``lifecycle_result``, raising ``RuntimeError`` if it is absent or the
      wrong type, stores it as ``self._lifecycle_result`` and delegates to the
      per-operation :meth:`_log_lifecycle_result` hook.

    A repeat of an assertion still pending — the same :meth:`_assertion_subject`
    asked again inside the window — is suppressed before the tree runs and
    reported with no activity (:meth:`_suppressed_duplicate`).
    """

    #: Ledger ``semantic_type`` of the activity this trigger emits; the key the
    #: pending assertion and the manager's commit share (SYNC-11-003).
    _assertion_semantic_type: ClassVar[str]

    _case: VulnerabilityCase

    def _clock_decisions(
        self, case_id: str
    ) -> list[py_trees.behaviour.Behaviour]:
        """The case-wide decisions, then the overdue-invitation sweep.

        An embargo act reads the consent rows, so the CASE_MANAGER expires
        every overdue invitation of the case first, and the case owner's
        decision on a proposal is taken knowing of each timeout (CM-28-029,
        EP-09-008).  The sweep runs even when the trigger opts out of the
        case-wide decisions, as terminate-embargo does: the sweep never
        pre-empts what the trigger answers for.  The stage runs only on the
        actor holding ``CVDRole.CASE_MANAGER``; elsewhere it is skipped.
        """
        return [
            *super()._clock_decisions(case_id),
            *embargo_clock_decisions(case_id, now=self._at),
        ]

    def _asserted_semantic_type(self) -> str:
        """The ledger ``semantic_type`` this run asserts.

        :attr:`_assertion_semantic_type` by default; a trigger whose activity
        depends on who runs it overrides this (the case owner's answer is its
        decision for the case, ADR-0122).
        """
        return self._assertion_semantic_type

    @abstractmethod
    def _assertion_subject(self) -> str | None:
        """What a repeat of this trigger would be about, or ``None``.

        The proposal an answer names, the embargo a teardown ends, the terms a
        proposal offers.  ``None`` when there is nothing to compare (the
        tree's own guard then refuses the request).
        """

    def _suppressed_duplicate(self) -> ActivityResult | None:
        subject = self._assertion_subject()
        if subject is None:
            return None
        return self._suppressed_repeat(
            self._case.id_, self._asserted_semantic_type(), subject
        )

    def _handle_result(self) -> None:
        if self._record_asserted_activity(
            self._case.id_,
            self._asserted_semantic_type(),
            subject_id=self._assertion_subject(),
        ):
            return
        lifecycle_result = self._result_out.get("lifecycle_result")
        if not isinstance(lifecycle_result, EmbargoLifecycleResult):
            raise RuntimeError(  # noqa: TRY004  # ruff-baseline #3353
                f"{type(self).__name__} did not capture lifecycle result"
                " in BT output"
            )
        self._lifecycle_result: EmbargoLifecycleResult = lifecycle_result
        self._log_lifecycle_result()

    @abstractmethod
    def _log_lifecycle_result(self) -> None:
        """Log the per-operation lifecycle result after BT execution."""
