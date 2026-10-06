"""Use cases for received embargo management activities.

One module per verb family (CS-18-001):

- :mod:`.create_add_remove` — ``Create``, ``Add`` and ``Remove`` of an
  ``EmbargoEvent``;
- :mod:`.announce` — ``Announce(EmbargoEvent)``;
- :mod:`.invite` — ``Invite(EmbargoEvent)`` and the resolution of its
  invitee and proposer;
- :mod:`.accept` — ``Accept(Invite(EmbargoEvent))``, including the
  late-Accept routing (EMB-17);
- :mod:`.reject` — ``Reject(Invite(EmbargoEvent))``.

Every public name of the former flat ``embargo`` module is re-exported here
(CS-18-003).
"""

from vultron.core.use_cases.received.embargo.accept import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.announce import (
    AnnounceEmbargoEventToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.create_add_remove import (
    AddEmbargoEventToCaseReceivedUseCase,
    CreateEmbargoEventReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.embargo.invite import (
    InviteToEmbargoOnCaseReceivedUseCase,
    resolve_invitee_id,
    resolve_proposer_id,
)
from vultron.core.use_cases.received.embargo.reject import (
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)

__all__ = [
    "AcceptInviteToEmbargoOnCaseReceivedUseCase",
    "AddEmbargoEventToCaseReceivedUseCase",
    "AnnounceEmbargoEventToCaseReceivedUseCase",
    "CreateEmbargoEventReceivedUseCase",
    "InviteToEmbargoOnCaseReceivedUseCase",
    "RejectInviteToEmbargoOnCaseReceivedUseCase",
    "RemoveEmbargoEventFromCaseReceivedUseCase",
    "resolve_invitee_id",
    "resolve_proposer_id",
]
