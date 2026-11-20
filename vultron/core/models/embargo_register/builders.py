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

The callers say *what happened*; these builders say which embargoes move.
"""

from collections.abc import Sequence

from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register.change import (
    _S,
    _T,
    RegisterChange,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
)


def _ids_with(
    embargoes: Sequence[EmbargoEvent], status: EmbargoRegisterStatus
) -> list[str]:
    return [embargo.id_ for embargo in embargoes if embargo.status == status]


def proposal_changes(embargo: EmbargoEvent) -> list[RegisterChange]:
    """The step that proposes *embargo*: the register adds it, ``PROPOSED``."""
    return [
        RegisterChange(
            embargo_id=embargo.id_, trigger=_T.PROPOSE, embargo=embargo
        )
    ]


def activation_changes(
    embargoes: Sequence[EmbargoEvent], embargo_id: str
) -> list[RegisterChange]:
    """The step that activates *embargo_id*, superseding any ``ACTIVE`` embargo."""
    return [
        RegisterChange(embargo_id=embargo_id, trigger=_T.ACTIVATE),
        *(
            RegisterChange(embargo_id=active_id, trigger=_T.SUPERSEDE)
            for active_id in _ids_with(embargoes, _S.ACTIVE)
        ),
    ]


def rejection_changes(embargo_id: str) -> list[RegisterChange]:
    """The step that rejects the proposal *embargo_id*."""
    return [RegisterChange(embargo_id=embargo_id, trigger=_T.REJECT)]


def termination_changes(
    embargoes: Sequence[EmbargoEvent], termination: EmbargoTermination
) -> list[RegisterChange]:
    """End the embargo in force with *termination*; cancel proposals (EP-08-004)."""
    return [
        *(
            RegisterChange(
                embargo_id=active_id,
                trigger=_T.TERMINATE,
                termination=termination,
            )
            for active_id in _ids_with(embargoes, _S.ACTIVE)
        ),
        *(
            RegisterChange(embargo_id=proposed_id, trigger=_T.CANCEL)
            for proposed_id in _ids_with(embargoes, _S.PROPOSED)
        ),
    ]
