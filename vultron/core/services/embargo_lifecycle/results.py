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

"""Public value types returned and accepted by :class:`EmbargoLifecycle`.

``TransitionMode`` selects how strictly an operation drives the EM machine;
``EmbargoLifecycleResult`` (with its per-participant ``ParticipantConsentChange``
entries) is what every operation returns.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from vultron.core.states.em import EM


class TransitionMode(StrEnum):
    """Controls how strict the EM state machine is during a transition.

    ``STRICT``   — Used where the executing actor *decides* the
                   transition: a trigger's CASE_MANAGER arm and the
                   CASE_MANAGER's received-side adjudication.  The service
                   enforces that the requested transition is valid for the
                   current EM state and raises
                   :exc:`~vultron.errors.VultronInvalidStateTransitionError`
                   otherwise.  A trigger run by any other participant makes no
                   lifecycle call at all: it asks the CASE_MANAGER
                   (EP-09-008).

    ``OBSERVED`` — Used where the executing actor *follows* a decision the
                   CASE_MANAGER already committed: received-side recording and
                   ledger replay (EP-09-007).  The service syncs local state
                   even if the local machine would not have initiated that
                   transition.
    """

    STRICT = "STRICT"
    OBSERVED = "OBSERVED"


class ParticipantConsentChange(BaseModel):
    """Records one participant's consent-row change during a lifecycle op.

    ``consent_before`` is ``None`` when the participant had no row for the
    embargo (it had not been asked); ``consent_after`` is the row's new state.
    """

    participant_id: str
    embargo_id: str
    consent_before: str | None
    consent_after: str


class EmbargoLifecycleResult(BaseModel):
    """Structured result returned by every :class:`EmbargoLifecycle` operation.

    Enables test assertions at the service boundary without inspecting
    DataLayer internals.

    Attributes:
        em_before: EM state before the operation.
        em_after: EM state after the operation.
        case_changed: True if the case object was mutated and persisted.
        case_embargo_changed: True if ``case.active_embargo`` was modified
            (e.g. an embargo was activated or cleared).
        participant_changes: Per-participant consent-row changes that
            occurred during the operation (e.g. a signatory carried over to a
            shorter revision, EP-05-001).  A lapse is not a change: it is
            derived from the rows (CM-18-001), so nothing is written for it.
    """

    em_before: EM
    em_after: EM
    case_changed: bool
    case_embargo_changed: bool
    participant_changes: list[ParticipantConsentChange] = Field(
        default_factory=list
    )
    is_expired: bool = False
