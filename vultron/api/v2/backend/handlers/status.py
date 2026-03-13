"""Handler functions for case and participant status activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchActivity
import vultron.core.use_cases.status as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE_STATUS)
def create_case_status(dispatchable: DispatchActivity, dl: DataLayer) -> None:
    uc.create_case_status(
        dispatchable.payload, dl, wire_object=dispatchable.wire_object
    )


@verify_semantics(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.add_case_status_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.CREATE_PARTICIPANT_STATUS)
def create_participant_status(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.create_participant_status(
        dispatchable.payload, dl, wire_object=dispatchable.wire_object
    )


@verify_semantics(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_to_participant(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.add_participant_status_to_participant(dispatchable.payload, dl)
