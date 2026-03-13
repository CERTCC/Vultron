"""Handler functions for vulnerability report activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchEvent
import vultron.core.use_cases.report as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.create_report(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.submit_report(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.validate_report(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.invalidate_report(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ACK_REPORT)
def ack_report(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.ack_report(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.CLOSE_REPORT)
def close_report(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.close_report(dispatchable.payload, dl)
