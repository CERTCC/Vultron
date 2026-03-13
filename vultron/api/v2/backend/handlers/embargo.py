"""Handler functions for embargo management activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchActivity
import vultron.core.use_cases.embargo as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_EMBARGO_EVENT)
def create_embargo_event(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.create_embargo_event(
        dispatchable.payload, dl, wire_object=dispatchable.wire_object
    )


@verify_semantics(MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE)
def add_embargo_event_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.add_embargo_event_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo_event_from_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.remove_embargo_event_from_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE)
def announce_embargo_event_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.announce_embargo_event_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo_on_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.invite_to_embargo_on_case(
        dispatchable.payload, dl, wire_activity=dispatchable.wire_activity
    )


@verify_semantics(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_embargo_on_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.accept_invite_to_embargo_on_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_embargo_on_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.reject_invite_to_embargo_on_case(dispatchable.payload, dl)
