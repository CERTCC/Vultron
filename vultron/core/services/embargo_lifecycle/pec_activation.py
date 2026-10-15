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

"""PEC consent effects of an embargo becoming the one in force.

Split from :mod:`~vultron.core.services.embargo_lifecycle.pec` (CS-18-001):
the activation arm of the consent bookkeeping.  Consent is per embargo
(ADR-0122), so activation needs almost no bookkeeping: whoever holds an
``AGREED`` row for the activated embargo is its signatory by lookup, and
whoever does not has lapsed by derivation (CM-18-001).  Two writes are left:
the case owner's own agreement, since activating an embargo is agreeing to it,
and containment: a revision that ends no later than the embargo it replaces
asks nothing new of an existing signatory, so their agreement is carried over
to it (``CARRY_OVER``, EP-05-001, CM-10-001).
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    EmbargoCaseFile,
    apply_embargo_change,
    changed_objects,
)
from vultron.core.models.embargo_consent_move import owner_agreement
from vultron.core.services.embargo_lifecycle.activation_decision import (
    carry_over_changes,
)
from vultron.core.services.embargo_lifecycle.pec import (
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantConsentChange,
)

logger = logging.getLogger(__name__)


class _PecActivationMixin(_PecEffectsMixin):
    """Consent bookkeeping run when an embargo becomes the one in force."""

    def _case_file(self, case: VulnerabilityCase) -> EmbargoCaseFile:
        """*case* and the participant records its roster indexes."""
        participants = {
            actor_id: record
            for actor_id, participant_id in case.actor_participant_index.items()
            if isinstance(
                record := self._persistence.read(participant_id),
                CaseParticipant,
            )
        }
        return EmbargoCaseFile(case=case, participants=participants)

    def _consent_at_activation(
        self,
        case: VulnerabilityCase,
        *,
        embargo_id: str,
        previous_embargo_id: str | None,
        ends_no_later: bool | None,
    ) -> list[ParticipantConsentChange]:
        """The consent rows written once *embargo_id* is the embargo in force.

        The consent effect of the case owner's
        ``Accept(EmbargoEvent, target=Case)`` (ADR-0122).  *ends_no_later* is
        ``None`` for a first activation (``PROPOSED → ACTIVE``, nothing
        replaced) and otherwise :meth:`_revision_ends_no_later`'s answer for
        the embargo replaced, taken before the case was mutated;
        *previous_embargo_id* is that embargo.

        The rows are the ones the CASE_MANAGER's decision names
        (:mod:`~vultron.core.services.embargo_lifecycle.activation_decision`),
        written through the one apply function, so this path and the
        copy model move the same rows:

        - The owner's row for the activated embargo is ``AGREED``
          (:func:`~vultron.core.models.embargo_consent_move.owner_agreement`),
          a ``DECLINED`` row included (MSM-07-008).
        - Replacing A with a B that ends no later than A carries A's
          signatories over
          (:func:`~vultron.core.services.embargo_lifecycle.activation_decision.carry_over_changes`);
          a longer B carries nobody, and the signatories who have not agreed
          to it have lapsed by derivation.  A first activation replaces
          nothing.
        """
        before = self._case_file(case)
        after = before
        agreement = owner_agreement(after, embargo_id)
        if agreement is not None:
            after = apply_embargo_change(after, agreement)
        if ends_no_later and previous_embargo_id is not None:
            for change in carry_over_changes(
                after,
                previous_embargo_id=previous_embargo_id,
                revised_embargo_id=embargo_id,
            ):
                after = apply_embargo_change(after, change)
        changes = [
            ParticipantConsentChange(
                participant_id=record.id_,
                embargo_id=embargo_id,
                consent_before=before.participants[actor_id]
                .consent_for(embargo_id)
                .value,
                consent_after=record.consent_for(embargo_id).value,
            )
            for actor_id, record in after.participants.items()
            if record is not before.participants[actor_id]
        ]
        changed = changed_objects(before, after)
        if changed:
            self._persistence.save_many(list(changed))
        logger.info(
            "Recorded consent on case '%s' for activated embargo '%s' (%s);"
            " %d row change(s)",
            _as_id(case),
            embargo_id,
            (
                "first activation"
                if ends_no_later is None
                else (
                    "shorter or equal — signatories carried over"
                    if ends_no_later
                    else "longer — non-agreeing signatories have lapsed"
                )
            ),
            len(changes),
        )
        return changes
