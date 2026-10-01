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

"""EmbargoLifecycle service — consolidated EM + PEC state management.

This service is the single authoritative place for all Embargo Management (EM)
and Participant Embargo Consent (PEC) state transitions.  Callers — trigger use
cases, received use cases, and BT nodes — inject an ``EmbargoLifecycle`` instance
and call named operations; they never instantiate ``EMAdapter`` or
``create_em_machine()`` directly.

Usage::

    from vultron.core.services.embargo_lifecycle import (
        EmbargoLifecycle,
        EmbargoLifecycleResult,
        TransitionMode,
    )

    lifecycle = EmbargoLifecycle(persistence=dl)
    result = lifecycle.propose_embargo(
        case_id=case.id_,
        embargo_id=embargo.id_,
        actor_id=actor.id_,
    )
    # result.em_before, result.em_after, result.case_changed, ...

Package layout (CS-18, #3760) — one module per responsibility, all composed
into :class:`EmbargoLifecycle` in ``service.py``:

- ``results.py``    — ``TransitionMode``, ``EmbargoLifecycleResult``,
  ``ParticipantPECChange``
- ``base.py``       — persistence handle, case lookup, P/X/A guard, EM driver
- ``pec.py``        — participant-consent side effects of EM transitions,
  including the revision-activation cascade (EP-05-001)
- ``proposals.py``  — ``propose_embargo``
- ``answers.py``    — ``accept_embargo_invite``, ``reject_embargo_invite``
- ``activation.py`` — ``terminate_active_embargo``, ``activate_embargo``
- ``consent.py``    — ``record_participant_consent``,
  ``record_embargo_rejection``, ``detect_and_apply_lapse``,
  ``assert_embargo_eligible``

Tracked in: https://github.com/CERTCC/Vultron/issues/538
Scaffold (#746); full operations (#747)
"""

from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
    TransitionMode,
)
from vultron.core.services.embargo_lifecycle.service import EmbargoLifecycle

__all__ = [
    "EmbargoLifecycle",
    "EmbargoLifecycleResult",
    "ParticipantPECChange",
    "TransitionMode",
]
