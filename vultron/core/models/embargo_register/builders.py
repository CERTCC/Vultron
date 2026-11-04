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


"""The register step each protocol event causes (ADR-0122).

The callers say *what happened*; these builders say which entries move.
"""

from collections.abc import Sequence

from vultron.core.models._helpers import _as_id
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register.entry import (
    _S,
    _T,
    EmbargoRegisterEntry,
    RegisterChange,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
)


def _ids_with(
    entries: Sequence[EmbargoRegisterEntry], status: EmbargoRegisterStatus
) -> list[str]:
    return [entry.embargo_id for entry in entries if entry.status == status]


def proposal_changes(embargo: str | EmbargoEvent) -> list[RegisterChange]:
    """The step that proposes *embargo*: one new ``PROPOSED`` entry."""
    embargo_id = _as_id(embargo)
    assert embargo_id is not None
    return [
        RegisterChange(
            embargo_id=embargo_id,
            trigger=_T.PROPOSE,
            embargo=embargo if isinstance(embargo, EmbargoEvent) else None,
        )
    ]


def activation_changes(
    entries: Sequence[EmbargoRegisterEntry], embargo_id: str
) -> list[RegisterChange]:
    """The step that activates *embargo_id*, superseding any ``ACTIVE`` entry."""
    return [
        RegisterChange(embargo_id=embargo_id, trigger=_T.ACTIVATE),
        *(
            RegisterChange(embargo_id=active_id, trigger=_T.SUPERSEDE)
            for active_id in _ids_with(entries, _S.ACTIVE)
        ),
    ]


def rejection_changes(embargo_id: str) -> list[RegisterChange]:
    """The step that rejects the proposal *embargo_id*."""
    return [RegisterChange(embargo_id=embargo_id, trigger=_T.REJECT)]


def termination_changes(
    entries: Sequence[EmbargoRegisterEntry], termination: EmbargoTermination
) -> list[RegisterChange]:
    """End the embargo in force with *termination*; cancel proposals (EP-08-004)."""
    return [
        *(
            RegisterChange(
                embargo_id=active_id,
                trigger=_T.TERMINATE,
                termination=termination,
            )
            for active_id in _ids_with(entries, _S.ACTIVE)
        ),
        *(
            RegisterChange(embargo_id=proposed_id, trigger=_T.CANCEL)
            for proposed_id in _ids_with(entries, _S.PROPOSED)
        ),
    ]


def carry_embargo_inline(
    entries: Sequence[EmbargoRegisterEntry], embargo: EmbargoEvent
) -> list[EmbargoRegisterEntry]:
    """*entries* with *embargo*'s entry holding the object, not its id.

    For a copy of a case about to be sent: a recipient cannot dereference an
    embargo it does not hold (AKM-02-004, EMB-18-003).  The status is
    unchanged, so this is not a register step.
    """
    return [
        (
            entry.model_copy(update={"embargo": embargo})
            if entry.embargo_id == embargo.id_
            else entry
        )
        for entry in entries
    ]
