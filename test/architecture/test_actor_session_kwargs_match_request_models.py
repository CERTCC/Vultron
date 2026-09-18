#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Architecture invariant: an ``ActorSession`` verb method cannot accept a keyword
the trigger endpoint would silently drop (DEMOMA-26-004).

Each ``ActorSession`` trigger method builds a request body and posts it to a
trigger endpoint whose body is validated by a request model with
``extra="ignore"`` (TB-03-002).  A keyword the method accepts but the model does
not declare would be dropped without error — the exact silent-no-op class
``ActorSession`` exists to make unrepresentable.  This test pins each method's
keyword parameters to a subset of its request model's fields (minus ``actor_id``,
which the URL path supplies), so adding a stray or misspelled keyword to a method
fails here rather than at demo runtime.

``case_id`` is deliberately *not* a method keyword — it is bound with
``with_case`` — so a method whose model requires ``case_id`` simply omits it from
its parameters; a subset check (not equality) is therefore the right relation.
"""

import inspect

import pytest

from vultron.adapters.driving.fastapi.trigger_models import (
    AcceptActorRecommendationRequest,
    AcceptCaseInviteRequest,
    AcceptCaseOwnershipTransferRequest,
    AddNoteToCaseRequest,
    CaseTriggerRequest,
    CloseCaseRequest,
    CloseReportRequest,
    CreateCaseRequest,
    InvalidateReportRequest,
    InviteActorToCaseRequest,
    NotifyFixDeployedRequest,
    NotifyFixReadyRequest,
    NotifyPublishedRequest,
    OfferCaseOwnershipTransferRequest,
    RejectCaseInviteRequest,
    SubmitReportRequest,
    SuggestActorToCaseRequest,
    SyncLogEntryRequest,
    ValidateReportRequest,
)
from vultron.demo.actor_session import ActorSession

#: One entry per ``ActorSession`` trigger verb: method name → request model whose
#: body the endpoint validates.  Every public verb method MUST appear here (the
#: coverage test below fails if a method is added without an entry), which forces
#: a new verb to declare which model bounds its keywords.
METHOD_TO_MODEL = {
    "submit_report": SubmitReportRequest,
    "validate_report": ValidateReportRequest,
    "invalidate_report": InvalidateReportRequest,
    "close_report": CloseReportRequest,
    "create_case": CreateCaseRequest,
    "engage_case": CaseTriggerRequest,
    "invite_actor_to_case": InviteActorToCaseRequest,
    "suggest_actor_to_case": SuggestActorToCaseRequest,
    "accept_case_invite": AcceptCaseInviteRequest,
    "reject_case_invite": RejectCaseInviteRequest,
    "accept_actor_recommendation": AcceptActorRecommendationRequest,
    "offer_case_ownership_transfer": OfferCaseOwnershipTransferRequest,
    "accept_case_ownership_transfer": AcceptCaseOwnershipTransferRequest,
    "add_note_to_case": AddNoteToCaseRequest,
    "notify_fix_ready": NotifyFixReadyRequest,
    "notify_fix_deployed": NotifyFixDeployedRequest,
    "notify_published": NotifyPublishedRequest,
    "close_case": CloseCaseRequest,
    "sync_log_entry": SyncLogEntryRequest,
}

#: Session-management helpers that are not trigger verbs and carry no request
#: model.  Kept explicit so the coverage test can subtract them and still catch a
#: genuinely new verb that forgot its ``METHOD_TO_MODEL`` entry.
_NON_VERB_METHODS = {"with_case", "quiet"}


def _keyword_params(method) -> set[str]:
    """Return the keyword parameter names of *method*, excluding ``self``."""
    params = inspect.signature(method).parameters
    return {
        name
        for name, p in params.items()
        if name != "self"
        and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }


def _public_verb_methods() -> set[str]:
    """Public ``ActorSession`` methods that are trigger verbs (not helpers)."""
    return {
        name
        for name, _ in inspect.getmembers(ActorSession, inspect.isfunction)
        if not name.startswith("_") and name not in _NON_VERB_METHODS
    }


@pytest.mark.parametrize("method_name", sorted(METHOD_TO_MODEL))
def test_method_keywords_are_a_subset_of_request_model_fields(method_name):
    """Every verb keyword must be a declared field of its request model."""
    model = METHOD_TO_MODEL[method_name]
    method = getattr(ActorSession, method_name)
    kwargs = _keyword_params(method)
    allowed = set(model.model_fields) - {"actor_id"}
    extra = kwargs - allowed
    assert not extra, (
        f"ActorSession.{method_name} accepts keyword(s) {sorted(extra)} that"
        f" {model.__name__} does not declare — the trigger endpoint would drop"
        f" them silently (TB-03-002). Allowed: {sorted(allowed)}."
    )


def test_every_public_verb_method_is_mapped():
    """A new trigger verb must declare its request model (guard the guard)."""
    unmapped = _public_verb_methods() - set(METHOD_TO_MODEL)
    assert not unmapped, (
        f"ActorSession verb method(s) {sorted(unmapped)} have no entry in"
        " METHOD_TO_MODEL; add one so their keywords are ratcheted against the"
        " request model (DEMOMA-26-004)."
    )
