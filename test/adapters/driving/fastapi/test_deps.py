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

Covers ARCH-13-003 — a DataLayer's ``actor_id`` is the actor's canonical URI, not
a short id or path segment:

- ``get_canonical_actor_dl()`` resolves a path segment to the canonical URI, so
  the store it opens is keyed by that URI.
- That store can read the outbox entries the same actor wrote (BUG-2026040901
  regression).

ARCH-13-004 is no longer covered here: it required the ``actor_id`` passed to
``record_outbox_item`` to match the one the reading DataLayer was constructed
with, and both that method and the mismatch it guarded against are gone
(ADR-0069). ARCH-13-003's own wording still names ``ActorScopedDataLayer`` and
``record_outbox_item``; its *statement* survives the change but its phrasing
needs the Phase 6 amendment.
"""

from collections.abc import Generator

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.deps import get_canonical_actor_dl
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.wire.as2.vocab.base.objects.actors import as_Service

# Canonical *for this node*: an actor id is the URL that reaches it here, so a
# hosted actor is named base_url + "actors/" + slug (ADR-0069). An id under
# another authority names a process elsewhere and cannot be resolved from a path
# segment on this node, which is what these tests exercise.
CANONICAL_URI = canonical_actor_uri("myactor")
SHORT_ID = CANONICAL_URI.rsplit("/", 1)[-1]  # "myactor"
ACTIVITY_ID = "https://example.org/activities/act-001"


@pytest.fixture()
def myactor_dl() -> Generator[SqliteDataLayer, None, None]:
    """The addressed actor's own in-memory store.

    Formerly named for the shared DataLayer and scoped to a generic marker actor
    — a name and a scope that both outlived it.  It has to be *this* actor's
    store: ``get_canonical_actor_dl`` resolves the path segment to the canonical
    URI and asks ``get_datalayer`` for that actor, so seeding somewhere else left
    the setup inert and any read-back assertion looking at an empty queue.

    Created through ``get_datalayer`` rather than a bare constructor so the
    dependency's own factory call finds this in-memory instance instead of
    resolving the configured on-disk URL.
    """
    from vultron.adapters.driven.datalayer_sqlite import (
        get_datalayer,
        reset_datalayer,
    )

    reset_datalayer(CANONICAL_URI)
    dl = get_datalayer(CANONICAL_URI, db_url="sqlite:///:memory:")
    dl.clear_all()
    yield dl
    dl.clear_all()
    reset_datalayer(CANONICAL_URI)


# ---------------------------------------------------------------------------
# AC-1: Unit tests for get_canonical_actor_dl()
# ---------------------------------------------------------------------------


def test_get_canonical_actor_dl_actor_found_via_read(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-1a: Actor found via dl.read() — DL is scoped to canonical URI.

    When actor_id is already the full canonical URI, ``dl.read()`` returns
    the actor directly and ``clone_for_actor`` is called with that URI.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    myactor_dl.save(actor)

    result: DataLayer = get_canonical_actor_dl(actor_id=CANONICAL_URI)

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == CANONICAL_URI


def test_get_canonical_actor_dl_actor_found_via_short_id(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-1b: Actor found via dl.find_actor_by_short_id() fallback.

    When ``actor_id`` is the short UUID (last path segment of the canonical
    URI), ``dl.read()`` returns ``None`` but ``dl.find_actor_by_short_id()``
    resolves the canonical URI.  The returned DL must be keyed by the
    canonical URI, not the short ID (ARCH-13-003).
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    myactor_dl.save(actor)

    result: DataLayer = get_canonical_actor_dl(actor_id=SHORT_ID)

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == CANONICAL_URI, (
        f"Expected canonical URI '{CANONICAL_URI}', "
        f"got '{result._actor_id}'"
    )


def test_get_canonical_actor_dl_actor_not_found_falls_back_to_raw_param(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-1c: Actor not found — DL falls back to raw actor_id path param.

    When neither ``dl.read()`` nor ``dl.find_actor_by_short_id()`` can
    resolve the ID (e.g. an empty store), ``clone_for_actor`` is called with
    the raw path param so the handler is not blocked.
    """
    unknown_id = "https://example.org/actors/unknown"

    result: DataLayer = get_canonical_actor_dl(actor_id=unknown_id)

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == unknown_id


# ---------------------------------------------------------------------------
# AC-3: Regression tests for BUG-2026040901
# ---------------------------------------------------------------------------


def test_one_actor_has_exactly_one_queue_regardless_of_spelling() -> None:
    """BUG-2026040901 is structurally impossible now (ADR-0069).

    This used to document the failure mode: ``record_outbox_item`` wrote under the
    canonical URI while a DL cloned to the *short id* read a different queue
    bucket, so the activity was silently dropped. Two spellings of one actor meant
    two queues.

    A path segment is now resolved to a canonical actor URI by **computation**
    (``base_url + "actors/" + segment``), and a store is keyed by that URI alone.
    So the short id and the canonical URI name the same store, and the queue-key
    mismatch cannot be expressed — which is the point: the bug was fixed by
    removing the possibility, not by remembering to canonicalize.

    Asserted positively, because the old test asserted the *presence* of the
    hazard and would now fail for the right reason.
    """
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    canonical_dl = get_datalayer(CANONICAL_URI, db_url="sqlite:///:memory:")
    canonical_dl.outbox_append(activity_id=ACTIVITY_ID)

    # Reached via the short segment: same actor, therefore the same queue.
    short_id_dl = get_datalayer(
        canonical_actor_uri(SHORT_ID), db_url="sqlite:///:memory:"
    )
    assert ACTIVITY_ID in short_id_dl.outbox_list(), (
        "the short segment and the canonical URI must name one store; two"
        " queues for one actor is BUG-2026040901"
    )


def test_get_canonical_actor_dl_resolves_canonical_uri_for_queue_reads(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-3b: get_canonical_actor_dl() returns a DL that can read the outbox.

    Regression for BUG-2026040901: when the URL path carries a short segment,
    ``get_canonical_actor_dl()`` must resolve it to the canonical URI so that
    ``outbox_list()`` reads the queue that actor's own writes went to.

    The test above asserts the same property of the ``get_datalayer`` factory;
    this one asserts it of the FastAPI dependency, which is the path a request
    actually takes.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    myactor_dl.save(actor)

    myactor_dl.outbox_append(activity_id=ACTIVITY_ID)

    actor_dl: DataLayer = get_canonical_actor_dl(actor_id=SHORT_ID)

    assert ACTIVITY_ID in actor_dl.outbox_list(), (
        "get_canonical_actor_dl must resolve the short UUID to the canonical "
        "URI so that outbox reads succeed (BUG-2026040901 regression)"
    )
