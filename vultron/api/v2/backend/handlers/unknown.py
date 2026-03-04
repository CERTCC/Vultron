"""
Handler function for unknown/unrecognized activities.
"""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.enums import MessageSemantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.UNKNOWN)
def unknown(dispatchable: DispatchActivity) -> None:
    logger.warning("unknown handler called for dispatchable: %s", dispatchable)
    return None
