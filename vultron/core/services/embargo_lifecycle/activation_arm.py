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

"""The EP-05-001 activation arm: what an activation reads, and which arm it takes.

Every writer of a case's ``active_embargo`` reads the record it names first
(EMB-18-003), and a revision compares the embargo it activates (B) with the
one it replaces (A) to decide whether existing signatories carry over or
must re-consent (EP-05-001).  Both reads go through
:func:`~vultron.core.services.embargo_ordering.read_embargo_event`, so an
unreadable record fails closed before the case is mutated.
"""

from vultron.core.services.embargo_lifecycle.base import _LifecycleBase
from vultron.core.services.embargo_ordering import (
    earliest_expiring_embargo_id,
    read_embargo_event,
)


class _ActivationArmMixin(_LifecycleBase):
    """Fail-closed embargo reads shared by the activation writers."""

    def _revision_ends_no_later(
        self, *, previous_embargo_id: str, revised_embargo_id: str
    ) -> bool:
        """True when revision B ends no later than the embargo A it replaces.

        The A-vs-B comparison shares :func:`earliest_expiring_embargo_id`'s
        read path (EP-08), so an unreadable record fails closed rather than
        silently deciding the arm; a tie keeps B, the first candidate, so
        equal terms carry everyone over.  Call it *before* the case is
        mutated, so a failure leaves EM and ``active_embargo`` untouched.

        Raises:
            VultronNotFoundError: If either embargo does not resolve.
            VultronValidationError: If either record is not an ``EmbargoEvent``.
        """
        return (
            earliest_expiring_embargo_id(
                self._persistence, [revised_embargo_id, previous_embargo_id]
            )
            == revised_embargo_id
        )

    def _activation_arm(
        self, *, previous_embargo_id: str | None, activated_embargo_id: str
    ) -> bool | None:
        """Read what an activation needs and decide its EP-05-001 arm.

        The one fail-closed read of an activation writer (EMB-18-003): the
        record of the embargo being activated is read on every activation,
        first or replacement, so a case never names an embargo its store
        cannot read; on a replacement the embargo it replaces is read too, by
        :meth:`_revision_ends_no_later`.  Call it *before* the case is
        mutated, so a failure leaves EM, ``active_embargo``, the proposal
        records and every participant's consent untouched.

        Returns:
            ``None`` when nothing is replaced (a first activation, or
            *activated_embargo_id* is already the case's active embargo);
            otherwise :meth:`_revision_ends_no_later`'s answer.

        Raises:
            VultronNotFoundError: If either embargo does not resolve.
            VultronValidationError: If either record is not an ``EmbargoEvent``.
        """
        read_embargo_event(self._persistence, activated_embargo_id)
        if (
            previous_embargo_id is None
            or previous_embargo_id == activated_embargo_id
        ):
            return None
        return self._revision_ends_no_later(
            previous_embargo_id=previous_embargo_id,
            revised_embargo_id=activated_embargo_id,
        )
