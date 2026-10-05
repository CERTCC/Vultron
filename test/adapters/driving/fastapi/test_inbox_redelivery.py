#!/usr/bin/env python
"""Redelivery regression: posting the same activity twice causes no second side effect.

Issue #3867. Governing specs: ID-02-001, ID-02-003, ID-03-001, ID-03-003,
ID-04-004, ID-05-003, IE-10-001, IE-05-001, IE-07-001, IO-04-002, IBP-04-002,
DL-07-001, ARCH-13-003.

Route-level tests (AC-1, AC-2, AC-4) post a state-changing activity twice
through the real FastAPI inbox route to a real CoreActor and verify that:
  - both requests are answered 202 (ID-03-001)
  - the store and outbox are identical after the second post (ID-02-001,
    ID-02-003, ID-04-004)
  - the redelivery is logged exactly once at INFO; no WARNING+ caused by
    the duplicate itself (ID-03-003, IE-10-001)

The parametrized sweep (AC-3) runs every dispatchable example activity twice
through the process_payload pipeline on a fresh per-actor in-memory store
(IBP-04-002, IO-04-002) and asserts the second run is a no-op.  No patching of
the dispatcher, use_case_map(), or ingress adapter (IBP-04-002, IO-04-002b).
"""

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

from __future__ import annotations

import logging
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.architecture._vocab_example_corpus import (
    activity_examples,
    wire_body,
)
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
)
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.actor import CoreActor
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACTOR_SLUG = "redelivery-test-actor"
_ACTOR_ID = canonical_actor_uri(_ACTOR_SLUG)
_SENDER_ID = "https://example.org/actors/sender"

# Logger emitting the INFO redelivery notice (FastAPIIngressAdapter.rehydrate).
_ORCHESTRATION_LOGGER = "vultron.adapters.driving.fastapi.inbox_orchestration"

# URL prefix added by create_app() (matches ``router`` prefix in app.py).
_API_PREFIX = "/api/v2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_report_body() -> dict[str, Any]:
    """A ``Create(VulnerabilityReport)`` addressed to the test actor."""
    report = as_VulnerabilityReport(
        name="Redelivery Test Report", content="test body"
    )
    activity = rm_create_report_activity(
        report=report,
        actor=_SENDER_ID,
        to=[_ACTOR_ID],
    )
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def _store_snapshot(dl: SqliteDataLayer) -> dict[str, Any]:
    """Snapshot the full store state: object-id set and outbox."""
    # dl.all() with no table argument returns dict[str, PersistableModel].
    # The overloaded signature cannot express this so mypy sees a union;
    # cast narrows it so .keys() type-checks cleanly.
    all_objects = cast(dict[str, Any], dl.all())
    return {
        "object_ids": frozenset(all_objects.keys()),
        "outbox": frozenset(dl.outbox_list()),
    }


def _run_pipeline_once(
    dl: SqliteDataLayer, body: dict[str, Any]
) -> InboxOutcome:
    """Run process_payload once with production-wired adapters (IBP-04-002).

    Uses ``make_dispatcher()`` explicitly so the sweep is never affected by
    whether the module-level ``_DISPATCHER_SLOT`` was set by a preceding test
    (``app_v2`` lifespan sets it when ``configure_globals=True``; the sweep
    must use real wiring regardless).
    """
    ingress = FastAPIIngressAdapter(dl=dl)
    dispatcher = make_dispatcher()
    dispatch_adp = FastAPIDispatchAdapter(
        dl=dl, actor_id=_ACTOR_ID, dispatcher=dispatcher
    )
    outcome = process_payload(body, ingress, dispatch_adp)
    # IO-04-002: assert on both status and failure_reason field *values*.
    # isinstance guards that process_payload returned the correct type;
    # the InboxOutcomeStatus membership check verifies status is a real enum
    # member rather than None or an arbitrary string.
    assert isinstance(outcome, InboxOutcome), (
        f"process_payload returned {type(outcome).__name__}, expected InboxOutcome"
    )
    assert outcome.status in InboxOutcomeStatus, (
        f"outcome.status={outcome.status!r} is not a valid InboxOutcomeStatus"
    )
    # failure_reason is Optional[str]; assert its type contract holds.
    assert outcome.failure_reason is None or isinstance(
        outcome.failure_reason, str
    ), (
        f"outcome.failure_reason has unexpected type: {type(outcome.failure_reason)}"
    )
    return outcome


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_client():
    """TestClient backed by create_app() with a pre-seeded CoreActor.

    Using ``create_app()`` instead of a bare ``FastAPI()`` means the lifespan
    runs and initialises the per-app dispatcher (``app.state.dispatcher``),
    so route-level inbox processing does not fail with "dispatcher not
    initialised" (ADR-0073, IBP-04-002).

    The actor is seeded into its own store *after* the lifespan starts so
    the auto-injected DataLayer registry exists and the same instance is
    returned to every route call and to this fixture.
    """
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    app = create_app(docs_url=None, openapi_url=None)

    with TestClient(app) as client:
        # Lifespan has run; auto-injected per-actor registry is live.
        factory = app.dependency_overrides[get_actor_dl]
        store: SqliteDataLayer = factory(_ACTOR_SLUG)
        actor = CoreActor(
            id_=_ACTOR_ID,
            name="Redelivery Test Actor",
            inbox=f"{_ACTOR_ID}/inbox",
            outbox=f"{_ACTOR_ID}/outbox",
        )
        store.create(object_to_record(actor))
        yield client, store


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-4: Route-level redelivery (real CoreActor, real HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.spec("ID-03-001")
def test_second_delivery_of_create_report_returns_202(actor_client):
    """Both posts of the same Create(VulnerabilityReport) are answered 202 (ID-03-001)."""
    client, _ = actor_client
    body = _create_report_body()

    resp1 = client.post(
        f"{_API_PREFIX}/actors/{_ACTOR_SLUG}/inbox/", json=body
    )
    assert resp1.status_code == 202

    resp2 = client.post(
        f"{_API_PREFIX}/actors/{_ACTOR_SLUG}/inbox/", json=body
    )
    assert resp2.status_code == 202


@pytest.mark.spec("ID-02-001")
@pytest.mark.spec("ID-02-003")
@pytest.mark.spec("ID-04-004")
def test_second_delivery_leaves_store_and_outbox_unchanged(actor_client):
    """Second delivery leaves exactly one copy and the same store snapshot (ID-02-001, ID-02-003, ID-04-004)."""
    client, store = actor_client
    body = _create_report_body()
    activity_id = body["id"]

    client.post(f"{_API_PREFIX}/actors/{_ACTOR_SLUG}/inbox/", json=body)
    state_after_first = _store_snapshot(store)

    # Precondition: activity stored by first post.
    assert activity_id in state_after_first["object_ids"], (
        "Precondition failed: activity was not stored on first delivery"
    )

    client.post(f"{_API_PREFIX}/actors/{_ACTOR_SLUG}/inbox/", json=body)
    state_after_second = _store_snapshot(store)

    assert state_after_second == state_after_first, (
        "Second delivery changed the store or outbox:\n"
        f"  ids added:    {state_after_second['object_ids'] - state_after_first['object_ids']}\n"
        f"  ids removed:  {state_after_first['object_ids'] - state_after_second['object_ids']}\n"
        f"  outbox after first:  {state_after_first['outbox']}\n"
        f"  outbox after second: {state_after_second['outbox']}"
    )


@pytest.mark.spec("ID-03-003")
@pytest.mark.spec("IE-10-001")
def test_second_delivery_logged_at_info_no_warning(
    actor_client, caplog: pytest.LogCaptureFixture
):
    """Redelivery logs at INFO naming the activity id; no WARNING+ caused by the duplicate (ID-03-003, IE-10-001).

    The ingress adapter already logs the redelivery at INFO with the activity
    id and the sender's actor id (IE-10-001, #3638).  No WARNING or above
    should be emitted as a consequence of the duplicate itself — only the
    natural processing of the second copy (which routes the stored body, not
    the redelivered one) is allowed.
    """
    client, _ = actor_client
    body = _create_report_body()
    activity_id = body["id"]

    # First post: may log at any level (e.g. INFO for normal processing).
    client.post(f"{_API_PREFIX}/actors/{_ACTOR_SLUG}/inbox/", json=body)
    warn_count_after_first = sum(
        1
        for r in caplog.records
        if r.levelno >= logging.WARNING and activity_id in r.getMessage()
    )

    with caplog.at_level(logging.DEBUG, logger=_ORCHESTRATION_LOGGER):
        client.post(f"{_API_PREFIX}/actors/{_ACTOR_SLUG}/inbox/", json=body)

    # The INFO redelivery notice names the activity id, the sender actor id,
    # and "already stored" (IE-10-001, AC-4 of issue #3867).
    # Log format: "activity <activity_id> (actor <sender_id>) was already stored..."
    redelivery_records = [
        r
        for r in caplog.records
        if r.levelno == logging.INFO
        and activity_id in r.getMessage()
        and _SENDER_ID in r.getMessage()
        and "already stored" in r.getMessage()
    ]
    assert redelivery_records, (
        "Expected at least one INFO record naming the activity id, the sender "
        f"actor id ({_SENDER_ID!r}), and 'already stored' to confirm the "
        "redelivered body was not re-stored (IE-10-001)."
    )

    # No new WARNING+ for this activity id introduced by the second post.
    warn_count_after_second = sum(
        1
        for r in caplog.records
        if r.levelno >= logging.WARNING and activity_id in r.getMessage()
    )
    assert warn_count_after_second == warn_count_after_first, (
        f"Second delivery introduced new WARNING+ for activity {activity_id}. "
        f"Extra records: {[r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING and activity_id in r.getMessage()][warn_count_after_first:]}"
    )


# ---------------------------------------------------------------------------
# AC-3: Parametrized sweep — every dispatchable example, pipeline-level
# ---------------------------------------------------------------------------

# Build the corpus once at module load, same as test_vocab_examples_dispatchable.
_EXAMPLES: dict[str, Any] = activity_examples()

# Handlers confirmed non-idempotent pending fix in issue #4215.  Each entry
# carries a strict xfail so the exemption is forced out once the handler
# becomes idempotent.  A name absent from _EXAMPLES triggers
# test_known_non_idempotent_names_are_collected (same guard as in
# test_vocab_examples_dispatchable.py).
_KNOWN_NON_IDEMPOTENT: dict[str, str] = {
    # Both runs refuse (missing case) but a fresh Reject activity is sealed on
    # every invocation rather than only the first.  #4215.
    "add_status_to_case": "non-idempotent refuse path — emits new Reject on redelivery (follow-up #4215)",
    "add_status_to_participant": "non-idempotent refuse path — emits new Reject on redelivery (follow-up #4215)",
    # SendRejectLogEntryNode creates a new Reject(CaseLedgerEntry) on every
    # delivery instead of suppressing duplicates.  #4215.
    "announce_case_ledger_entry": "non-idempotent deferred path — SendRejectLogEntryNode emits new Reject on redelivery (follow-up #4215)",
    # CreateCaseProposalReceivedUseCase emits a trigger-response activity on
    # both the first and second delivery; second delivery is not a no-op.  #4215.
    "create_case_proposal": "non-idempotent processed path — CreateCaseProposalReceivedUseCase emits new activity on redelivery (follow-up #4215)",
}


def _sweep_params() -> list[Any]:
    """Build parametrize params; known non-idempotent entries get strict xfail."""
    params: list[Any] = []
    for name in sorted(_EXAMPLES.keys()):
        if name in _KNOWN_NON_IDEMPOTENT:
            params.append(
                pytest.param(
                    name,
                    marks=pytest.mark.xfail(
                        strict=True,
                        reason=_KNOWN_NON_IDEMPOTENT[name],
                    ),
                )
            )
        else:
            params.append(name)
    return params


def test_known_non_idempotent_names_are_collected() -> None:
    """An exemption for an example that is no longer collected is a stale lie.

    If a name in _KNOWN_NON_IDEMPOTENT disappears from the example corpus
    (renamed, deleted, or given a required argument), the strict xfail would
    record the missing item as a pass rather than failing, so the exemption
    would silently outlive the issue it names.  This guard fails immediately
    instead.
    """
    missing = sorted(set(_KNOWN_NON_IDEMPOTENT) - set(_EXAMPLES))
    assert not missing, (
        f"_KNOWN_NON_IDEMPOTENT names {missing}, which the corpus does not "
        "contain. Either the example was renamed or removed — delete the "
        "entry — or the collector has stopped reaching it."
    )


@pytest.fixture
def sweep_dl():
    """A fresh per-actor in-memory store for each parametrized sweep case."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR_ID)
    yield dl
    dl.close()


@pytest.mark.spec("ID-02-001")
@pytest.mark.spec("ID-02-003")
@pytest.mark.spec("ID-05-003")
@pytest.mark.parametrize("name", _sweep_params())
def test_redelivery_sweep_idempotent(name: str, sweep_dl: SqliteDataLayer):
    """Second pipeline run for every dispatchable example leaves store and outbox unchanged (ID-02-001, ID-02-003, ID-05-003).

    Uses real wiring: no patching of the dispatcher, use_case_map(), or
    ingress adapter (IBP-04-002, IO-04-002b).
    """
    example = _EXAMPLES[name]
    body = wire_body(example)

    outcome1 = _run_pipeline_once(sweep_dl, body)
    state_after_first = _store_snapshot(sweep_dl)

    outcome2 = _run_pipeline_once(sweep_dl, body)
    state_after_second = _store_snapshot(sweep_dl)

    new_ids = (
        state_after_second["object_ids"] - state_after_first["object_ids"]
    )
    new_outbox = state_after_second["outbox"] - state_after_first["outbox"]

    assert not new_ids, (
        f"Second run for '{name}' added new object ids: {new_ids} "
        f"(first outcome={outcome1.status}, second outcome={outcome2.status})"
    )
    assert not new_outbox, (
        f"Second run for '{name}' added new outbox items: {new_outbox} "
        f"(first outcome={outcome1.status}, second outcome={outcome2.status})"
    )
    # AC-3 (issue #3867): second run must not change InboxOutcome.status.
    assert outcome2.status == outcome1.status, (
        f"Second run for '{name}' returned a different status: "
        f"first={outcome1.status}, second={outcome2.status}"
    )
