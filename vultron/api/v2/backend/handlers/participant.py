"""Handler functions for case participant management activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchActivity
import vultron.core.use_cases.case_participant as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE_PARTICIPANT)
def create_case_participant(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.create_case_participant(
        dispatchable.payload, dl, wire_object=dispatchable.wire_object
    )


@verify_semantics(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant_to_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.add_case_participant_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_participant_from_case(
    dispatchable: DispatchActivity, dl: DataLayer
) -> None:
    uc.remove_case_participant_from_case(dispatchable.payload, dl)
