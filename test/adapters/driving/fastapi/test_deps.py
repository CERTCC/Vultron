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

"""Unit tests for shared FastAPI dependency providers (deps.py).

Covers ARCH-13-003 and ARCH-13-004:

- ``get_canonical_actor_dl()`` resolves short IDs to canonical URIs so that
  actor-scoped DataLayer instances are keyed by the full canonical URI.
- The canonical-URI-keyed DL can read outbox entries written by
  ``record_outbox_item`` (BUG-2026040901 regression).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.deps import get_canonical_actor_dl
from vultron.core.ports.datalayer import ActorScopedDataLayer
from vultron.wire.as2.vocab.base.objects.actors import as_Service

CANONICAL_URI = "https://example.org/actors/myactor"
SHORT_ID = CANONICAL_URI.rsplit("/", 1)[-1]  # "myactor"
ACTIVITY_ID = "https://example.org/activities/act-001"


@pytest.fixture()
def shared_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


# ---------------------------------------------------------------------------
# AC-1: Unit tests for get_canonical_actor_dl()
# ---------------------------------------------------------------------------


def test_get_canonical_actor_dl_actor_found_via_read(
    shared_dl: SqliteDataLayer,
) -> None:
    """AC-1a: Actor found via dl.read() — DL is scoped to canonical URI.

    When actor_id is already the full canonical URI, ``dl.read()`` returns
    the actor directly and ``clone_for_actor`` is called with that URI.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    shared_dl.save(actor)

    result: ActorScopedDataLayer = get_canonical_actor_dl(
        actor_id=CANONICAL_URI, dl=shared_dl
    )

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == CANONICAL_URI


def test_get_canonical_actor_dl_actor_found_via_short_id(
    shared_dl: SqliteDataLayer,
) -> None:
    """AC-1b: Actor found via dl.find_actor_by_short_id() fallback.

    When ``actor_id`` is the short UUID (last path segment of the canonical
    URI), ``dl.read()`` returns ``None`` but ``dl.find_actor_by_short_id()``
    resolves the canonical URI.  The returned DL must be keyed by the
    canonical URI, not the short ID (ARCH-13-003).
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    shared_dl.save(actor)

    result: ActorScopedDataLayer = get_canonical_actor_dl(
        actor_id=SHORT_ID, dl=shared_dl
    )

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == CANONICAL_URI, (
        f"Expected canonical URI '{CANONICAL_URI}', "
        f"got '{result._actor_id}'"
    )


def test_get_canonical_actor_dl_actor_not_found_falls_back_to_raw_param(
    shared_dl: SqliteDataLayer,
) -> None:
    """AC-1c: Actor not found — DL falls back to raw actor_id path param.

    When neither ``dl.read()`` nor ``dl.find_actor_by_short_id()`` can
    resolve the ID (e.g. an empty store), ``clone_for_actor`` is called with
    the raw path param so the handler is not blocked.
    """
    unknown_id = "https://example.org/actors/unknown"

    result: ActorScopedDataLayer = get_canonical_actor_dl(
        actor_id=unknown_id, dl=shared_dl
    )

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == unknown_id


# ---------------------------------------------------------------------------
# AC-3: Regression tests for BUG-2026040901
# ---------------------------------------------------------------------------


def test_short_id_dl_cannot_read_queue_written_by_canonical_uri(
    shared_dl: SqliteDataLayer,
) -> None:
    """AC-3a: Short-ID-scoped DL cannot read outbox written by canonical URI.

    Documents the BUG-2026040901 failure mode: ``record_outbox_item``
    writes an outbox entry keyed by the canonical URI.  A DL clone scoped
    to the short UUID (not the canonical URI) reads a different queue bucket
    and sees no items — the activity is silently dropped.

    This test intentionally demonstrates the problematic behaviour so that
    AC-3b (the regression test) can confirm ``get_canonical_actor_dl``
    prevents it.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    shared_dl.save(actor)

    # Use-case writes to the canonical-URI-keyed outbox (normal runtime path)
    shared_dl.record_outbox_item(
        actor_id=CANONICAL_URI, activity_id=ACTIVITY_ID
    )

    # A DL scoped to the short ID reads a *different* queue bucket → empty
    short_id_dl: ActorScopedDataLayer = shared_dl.clone_for_actor(SHORT_ID)
    assert short_id_dl.outbox_list() == [], (
        "Short-ID-scoped DL must NOT see entries written by the canonical-URI "
        "key (documents the BUG-2026040901 queue-key mismatch scenario)"
    )

    # A DL scoped to the canonical URI reads the correct bucket
    canonical_dl: ActorScopedDataLayer = shared_dl.clone_for_actor(
        CANONICAL_URI
    )
    assert ACTIVITY_ID in canonical_dl.outbox_list(), (
        "Canonical-URI-scoped DL must read the entry written by "
        "record_outbox_item(actor_id=CANONICAL_URI, ...)"
    )


def test_get_canonical_actor_dl_resolves_canonical_uri_for_queue_reads(
    shared_dl: SqliteDataLayer,
) -> None:
    """AC-3b: get_canonical_actor_dl() returns a DL that can read the outbox.

    Regression for BUG-2026040901 (ARCH-13-003, ARCH-13-004): when the URL
    path carries a short UUID, ``get_canonical_actor_dl()`` must resolve it
    to the canonical URI so that subsequent ``outbox_list()`` calls read the
    same queue bucket that ``record_outbox_item`` wrote to.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    shared_dl.save(actor)

    shared_dl.record_outbox_item(
        actor_id=CANONICAL_URI, activity_id=ACTIVITY_ID
    )

    actor_dl: ActorScopedDataLayer = get_canonical_actor_dl(
        actor_id=SHORT_ID, dl=shared_dl
    )

    assert ACTIVITY_ID in actor_dl.outbox_list(), (
        "get_canonical_actor_dl must resolve the short UUID to the canonical "
        "URI so that outbox reads succeed (BUG-2026040901 regression)"
    )
