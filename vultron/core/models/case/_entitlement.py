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

"""Who is entitled to a :class:`VulnerabilityCase`'s content (CM-10-004).

The one active-participant check (ADR-0114); recipients are selected through
:mod:`vultron.core.participants.recipients`, which asks it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vultron.core.models.case_participant import CaseParticipant


class ParticipantEntitlementMixin:
    """Entitlement check of :class:`VulnerabilityCase` (CM-10-004, ADR-0114)."""

    if TYPE_CHECKING:
        # Register views of :class:`EmbargoRegisterMixin` this check reads.
        @property
        def active_embargo_id(self) -> str | None: ...

        @property
        def embargo_in_force(self) -> bool: ...

    def is_active_participant(self, participant: CaseParticipant) -> bool:
        """True when *participant* is entitled to this case's content.

        The one active-participant check (CM-10-004, ADR-0114 § "Inert and
        active").  A participant is **active** when all hold:

        1. it has joined the case — seated by the case initialization
           sequence or accepted its stub Invite (``participant.joined``);
        2. it has not been removed (``participant.removed``, CM-31-001);
        3. when this case has an active embargo (:attr:`embargo_in_force`),
           its consent row for the active embargo is ``AGREED``
           (:meth:`CaseParticipant.is_signatory`, CM-18-001).

        Every other participant is **inert**.  A removed participant is inert
        whatever its embargo consent: a removed signatory stays bound but
        receives no content (CM-31-008, ADR-0116).  RM ``CLOSED`` is deliberately
        not part of this check: a closed participant is still owed the
        ledger entries that record its own closure, and nothing after them
        (CM-23-004), so each recipient
        selection applies the ``CLOSED`` filter itself
        (:mod:`vultron.core.participants.recipients`).  The sender checks
        apply it too: a closed participant may act on nothing further
        (CM-23-018).  The answer is computed from the
        replicated participant record and this case's own status, never
        stored, so every replica derives the same answer.  Recipients are
        selected through :mod:`vultron.core.participants.recipients`, which
        resolves each roster entry to its record and asks this method.
        """
        if not participant.joined or participant.removed:
            return False
        if not self.embargo_in_force:
            return True
        return participant.is_signatory(self.active_embargo_id)
