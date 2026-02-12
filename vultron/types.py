"""
Shared type definitions for Vultron.

This module contains common types used across the codebase to avoid circular imports.
"""

from typing import Protocol

from pydantic import BaseModel

from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.enums import MessageSemantics


class DispatchActivity(BaseModel):
    """
    Data model to represent a dispatchable activity with its associated message semantics as a header.
    """

    semantic_type: MessageSemantics
    activity_id: str
    payload: as_Activity
    # We are deliberately not including case_id or report_id here because
    # where they are located in the payload can vary depending on message semantics.
    # Therefore it is better to leave it to downstream semantic-specific handlers to
    # extract those values for logging or other purposes rather than having to build
    # a parallel extraction logic here in the dispatcher that may not be universally applicable.


class BehaviorHandler(Protocol):
    """
    Protocol for behavior handler functions.
    """

    def __call__(self, dispatchable: DispatchActivity) -> None: ...
