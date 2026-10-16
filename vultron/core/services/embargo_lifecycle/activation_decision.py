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

"""The decide half of the case owner's activation (ADR-0122, ADR-0124).

The CASE_MANAGER decides an activation before it commits anything.
:meth:`_ActivationDecisionMixin.decide_activation` reads the embargoes it
needs (EMB-18-003), applies the ``STRICT`` checks (an open proposal, P/X/A
clear, EMB-02-002), decides the EP-05-001 arm, and returns an
:class:`ActivationDecision`: the entries the activation commits, in order,
and what each changes.  It writes nothing.

- The owner's ``Accept(EmbargoEvent, target=Case)`` is one entry, and it is
  the whole ``ACTIVATE`` register step, the ``SUPERSEDE`` of the embargo in
  force included: :attr:`ActivationDecision.step`.  The same activity states
  the owner's agreement, so its ``AGREED`` row
  (:attr:`ActivationDecision.owner_agreement`) is applied from that entry,
  with no entry of its own (CLP-07-013, MSM-07-008).
- Each ``CARRY_OVER`` row of a revision that ends no later than the embargo
  it replaces is its own CASE_MANAGER ``Update(EmbargoConsent)`` entry,
  after the ``Accept``'s (:attr:`ActivationDecision.carry_overs`, EP-05-001).
"""

from dataclasses import dataclass, field

from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    EmbargoCaseFile,
    RegisterStep,
    RegisterStepKind,
    apply_embargo_change,
)
from vultron.core.models.embargo_consent_move import (
    consent_row_move,
    owner_agreement,
)
from vultron.core.services.embargo_lifecycle.activation_arm import (
    _ActivationArmMixin,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.errors import VultronInvalidStateTransitionError


@dataclass(frozen=True)
class ActivationDecision:
    """What the CASE_MANAGER's activation commits, and what each entry changes.

    *step* is the ``Accept``'s register step and *owner_agreement* the row
    the same activity states (``None`` when the owner's row already agrees);
    *carry_overs* are the ``CARRY_OVER`` rows, one entry each, in commit
    order.  *em_before* and *em_after* are EM around the whole activation.
    """

    step: RegisterStep
    owner_agreement: ConsentRowChange | None
    em_before: EM
    em_after: EM
    carry_overs: tuple[ConsentRowChange, ...] = field(default_factory=tuple)

    @property
    def consent_rows(self) -> list[ConsentRowChange]:
        """Every row the activation changes, in apply order."""
        return [
            *([self.owner_agreement] if self.owner_agreement else []),
            *self.carry_overs,
        ]


def carry_over_changes(
    activated: EmbargoCaseFile,
    *,
    previous_embargo_id: str,
    revised_embargo_id: str,
) -> list[ConsentRowChange]:
    """``CARRY_OVER`` to the revision for every signatory of the one replaced.

    The shorter arm of EP-05-001: a revision ending no later than the embargo
    it replaces asks nothing new of an existing signatory, so each
    participant whose row for *previous_embargo_id* is ``AGREED`` is carried
    over, a ``DECLINED`` revision row included (CM-10-001).  *activated* is
    the case file as the activation's own entry leaves it, so a row the owner
    already agreed is not carried again.  In the case file's order.

    Raises:
        VultronNotFoundError: a participant holds no row for
            *previous_embargo_id* (ADR-0122).
    """
    changes: list[ConsentRowChange] = []
    for actor_id, participant in activated.participants.items():
        # A missing row for the replaced embargo raises (ADR-0122).
        if (
            participant.consent_for(previous_embargo_id)
            != EmbargoConsentState.AGREED
        ):
            continue
        change = consent_row_move(
            activated, actor_id, revised_embargo_id, PEC_Trigger.CARRY_OVER
        )
        if change is not None:
            changes.append(change)
    return changes


def activation_consent_changes(
    activated: EmbargoCaseFile,
    *,
    embargo_id: str,
    previous_embargo_id: str | None,
    ends_no_later: bool | None,
) -> tuple[ConsentRowChange | None, list[ConsentRowChange]]:
    """The consent rows an activation of *embargo_id* writes, in apply order.

    *activated* is the case file as the ``ACTIVATE`` step leaves it.  First
    the owner's ``AGREED`` row its Accept states, then, when the revision
    ends no later than *previous_embargo_id* (*ends_no_later*), one
    ``CARRY_OVER`` row per signatory of the replaced embargo, decided after
    the owner's row (EP-05-001, MSM-07-005).  Writes nothing.
    """
    agreement = owner_agreement(activated, embargo_id)
    if agreement is not None:
        activated = apply_embargo_change(activated, agreement)
    carry_overs: list[ConsentRowChange] = []
    if ends_no_later and previous_embargo_id is not None:
        carry_overs = carry_over_changes(
            activated,
            previous_embargo_id=previous_embargo_id,
            revised_embargo_id=embargo_id,
        )
    return agreement, carry_overs


class _ActivationDecisionMixin(_ActivationArmMixin):
    """The CASE_MANAGER's decision of an owner's activation, writing nothing."""

    def decide_activation(
        self, case_file: EmbargoCaseFile, embargo_id: str
    ) -> ActivationDecision:
        """Decide the owner's activation of *embargo_id* on *case_file*.

        Raises:
            VultronInvalidStateTransitionError: *embargo_id* is not an open
                proposal of the case, or P/X/A is set (EMB-02-002).
            VultronNotFoundError: the activated embargo, or the one it
                replaces, cannot be read (EMB-18-003).
            VultronValidationError: either record is not an ``EmbargoEvent``.
            VultronEntryRefusedError: the register refuses the step
                (ADR-0122, ADR-0130).
        """
        case = case_file.case
        if embargo_id not in case.proposed_embargo_ids:
            raise VultronInvalidStateTransitionError(
                f"Cannot activate embargo '{embargo_id}' on case"
                f" '{case.id_}': it is not an open proposal of the case."
            )
        self._assert_pxa_embargo_eligible(
            case.current_status.pxa.state, case.id_, "activate embargo"
        )
        previous_embargo_id = case.active_embargo_id
        ends_no_later = self._activation_arm(
            previous_embargo_id=previous_embargo_id,
            activated_embargo_id=embargo_id,
        )
        step = RegisterStep(kind=RegisterStepKind.ACTIVATE, embargo=embargo_id)
        activated = apply_embargo_change(case_file, step)
        agreement, carry_overs = activation_consent_changes(
            activated,
            embargo_id=embargo_id,
            previous_embargo_id=previous_embargo_id,
            ends_no_later=ends_no_later,
        )
        return ActivationDecision(
            step=step,
            owner_agreement=agreement,
            em_before=case.em_state,
            em_after=activated.case.em_state,
            carry_overs=tuple(carry_overs),
        )


__all__ = [
    "ActivationDecision",
    "activation_consent_changes",
    "carry_over_changes",
]
