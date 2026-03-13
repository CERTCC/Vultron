"""Handler functions for case actor activities — thin delegates to core use cases."""

import logging

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.datalayer import DataLayer
from vultron.types import DispatchEvent
import vultron.core.use_cases.actor as uc

logger = logging.getLogger(__name__)


@verify_semantics(MessageSemantics.SUGGEST_ACTOR_TO_CASE)
def suggest_actor_to_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.suggest_actor_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE)
def accept_suggest_actor_to_case(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.accept_suggest_actor_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE)
def reject_suggest_actor_to_case(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.reject_suggest_actor_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_case_ownership_transfer(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.offer_case_ownership_transfer(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_case_ownership_transfer(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.accept_case_ownership_transfer(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_case_ownership_transfer(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.reject_case_ownership_transfer(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case(dispatchable: DispatchEvent, dl: DataLayer) -> None:
    uc.invite_actor_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.accept_invite_actor_to_case(dispatchable.payload, dl)


@verify_semantics(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case(
    dispatchable: DispatchEvent, dl: DataLayer
) -> None:
    uc.reject_invite_actor_to_case(dispatchable.payload, dl)
