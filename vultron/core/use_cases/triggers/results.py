"""Result envelope models for trigger use cases.

`TriggerResult` is the typed return value of a trigger-side action: the minimum
of the `UseCaseResult` hierarchy designed in ADR-0040 (see
`notes/use-case-protocol.md`).  The full hierarchy — a shared `UseCaseResult`
base and a received-side `HandlerResult` sibling — is not built yet (#1769,
#3354); this module deliberately introduces only the trigger half that
`ActorSession` (`vultron/demo/actor_session.py`) needs today.

All fields are optional so a `TriggerResult` can be built by
``TriggerResult.model_validate(raw)`` directly from the ``dict`` a trigger
endpoint returns (``extra="ignore"`` drops keys a given verb does not carry).
Subclasses MAY add domain-specific fields but MUST NOT carry raw ``dict``
payloads (UCORG-05-005).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class TriggerResult(BaseModel):
    """Typed result of a trigger-side use case (UCORG-05-005).

    Carries the outbound activity a trigger emitted (as a wire ``dict``; a
    typed variant lives in the demo-layer :class:`ActivityResult`), the
    emitting actor's URI, and the case/offer ids a verb reports back.  Every
    field is optional: a given trigger populates only the subset meaningful for
    it, and unknown response keys are ignored so the same envelope validates any
    trigger response.
    """

    model_config = ConfigDict(extra="ignore")

    activity: dict[str, Any] | None = None
    case_id: str | None = None
    emitting_actor_id: str | None = None
    offer: dict[str, Any] | None = None
