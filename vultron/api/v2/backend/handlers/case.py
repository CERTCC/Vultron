"""Handler functions for vulnerability case activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchEvent
import vultron.core.use_cases.case as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_CASE)
def create_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.create_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ENGAGE_CASE)
def engage_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.engage_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.DEFER_CASE)
def defer_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.defer_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ADD_REPORT_TO_CASE)
def add_report_to_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.add_report_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.CLOSE_CASE)
def close_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.close_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.UPDATE_CASE)
def update_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.update_case(dispatchable.payload, dl)
