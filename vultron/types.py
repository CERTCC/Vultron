from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

from vultron.core.models.events import InboundPayload, MessageSemantics

if TYPE_CHECKING:
    from vultron.api.v2.datalayer.abc import DataLayer


class DispatchActivity(BaseModel):
    """
    Data model to represent a dispatchable activity with its associated message semantics as a header.
    """

    semantic_type: MessageSemantics
    activity_id: str
    payload: InboundPayload
    # We are deliberately not including case_id or report_id here because
    # where they are located in payload.raw_activity can vary depending on message semantics.
    # Therefore it is better to leave it to downstream semantic-specific handlers to
    # extract those values for logging or other purposes rather than having to build
    # a parallel extraction logic here in the dispatcher that may not be universally applicable.


class BehaviorHandler(Protocol):
    """
    Protocol for behavior handler functions.
    """

    def __call__(
        self, dispatchable: DispatchActivity, dl: "DataLayer"
    ) -> None: ...
