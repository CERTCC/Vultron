"""Handler function for unknown/unrecognized activities — thin delegate to core use case."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchEvent
import vultron.core.use_cases.unknown as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.UNKNOWN)
def unknown(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.unknown(dispatchable.payload, dl)
