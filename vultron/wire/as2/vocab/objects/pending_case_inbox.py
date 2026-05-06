#!/usr/bin/env python
"""Wire-layer vocabulary registration for :class:`VultronPendingCaseInbox`."""

from vultron.core.models.pending_case_inbox import (  # noqa: F401
    VultronPendingCaseInbox,
)
from vultron.wire.as2.vocab.base.registry import VOCABULARY

VOCABULARY["PendingCaseInbox"] = VultronPendingCaseInbox

__all__ = ["VultronPendingCaseInbox"]
