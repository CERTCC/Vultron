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

"""The :class:`EmbargoLifecycle` service class.

Composed from the per-responsibility mixins in this package; each mixin
module documents the operations it contributes.  Callers only ever see this
class.
"""

from vultron.core.services.embargo_lifecycle.activation import (
    _ActivationOperationsMixin,
)
from vultron.core.services.embargo_lifecycle.answers import (
    _AnswerOperationsMixin,
)
from vultron.core.services.embargo_lifecycle.consent import (
    _ConsentOperationsMixin,
)
from vultron.core.services.embargo_lifecycle.creation import (
    _CreationOperationsMixin,
)
from vultron.core.services.embargo_lifecycle.proposals import (
    _ProposalOperationsMixin,
)


class EmbargoLifecycle(
    _CreationOperationsMixin,
    _ProposalOperationsMixin,
    _AnswerOperationsMixin,
    _ActivationOperationsMixin,
    _ConsentOperationsMixin,
):
    """Consolidated EM + PEC state management service.

    Owns all Embargo Management (EM) and Participant Embargo Consent (PEC)
    state transition logic.  Hides ``create_em_machine()``, ``EMAdapter``,
    ``MachineError`` handling, actor-to-participant lookup via
    ``actor_participant_index``, PEC trigger application, and idempotent
    ``proposed_embargoes`` / ``accepted_embargo_ids`` management.

    Callers inject a :class:`~vultron.core.ports.case_persistence.CasePersistence`
    instance once at construction.  ``SqliteDataLayer`` satisfies the protocol
    structurally.

    Public operations (``STRICT`` and ``OBSERVED`` modes unless noted):
        - :meth:`propose_embargo`
        - :meth:`accept_embargo_invite`
        - :meth:`reject_embargo_invite`
        - :meth:`abandon_embargo_proposals`
        - :meth:`terminate_active_embargo`
        - :meth:`activate_embargo`
        - :meth:`initialize_creation_embargo` (STRICT only; one write, EP-04-002)
        - :meth:`record_participant_consent` (no EM transition; no mode param)
        - :meth:`record_embargo_rejection` (no EM transition; no mode param)
        - :meth:`record_embargo_invite` (no EM transition; no mode param)
        - :meth:`detect_and_apply_lapse` (no EM transition; no mode param)
        - :meth:`assert_embargo_eligible` (guard only; no mode param)
    """
