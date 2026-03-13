"""Handler functions for case note activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchEvent
import vultron.core.use_cases.note as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.CREATE_NOTE)
def create_note(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.create_note(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_to_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.add_note_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REMOVE_NOTE_FROM_CASE)
def remove_note_from_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.remove_note_from_case(dispatchable.payload, dl)
