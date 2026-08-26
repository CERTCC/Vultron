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

- ``get_actor_dl()`` resolves a path segment to the canonical URI *by
  computation* — ``{node base URL}/actors/{segment}`` — so the store it opens is
  keyed by that URI.  There is no lookup: the pre-ADR-0073 sequence of
  ``dl.read()``, then ``find_actor_by_short_id()``, then ``clone_for_actor()``
  is gone, along with the shared store it scanned.
- ``node_base_url`` supplies the base for that computation, and is *app*-scoped
  rather than request-derived, so a client cannot change which store is opened by
  changing its ``Host`` header.
- ``get_canonical_actor_dl`` and ``get_trigger_dl`` are alternate override points
  that delegate to it through ``Depends``, which is asserted here rather than
  assumed.
- The resolved store can read the outbox entries the same actor wrote
  (BUG-2026040901 regression).

ARCH-13-004 is no longer covered here: it required the ``actor_id`` passed to
``record_outbox_item`` to match the one the reading DataLayer was constructed
with, and both that method and the mismatch it guarded against are gone
(ADR-0073). ARCH-13-003's own wording still names ``ActorScopedDataLayer`` and
``record_outbox_item``; its *statement* survives the change but its phrasing
needs the Phase 6 amendment.
"""

from collections.abc import Generator
from typing import cast

import pytest
from fastapi import Request
from fastapi.params import Depends as params_Depends

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.deps import (
    get_actor_dl,
    get_canonical_actor_dl,
    get_trigger_dl,
    node_base_url,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.wire.as2.vocab.base.objects.actors import as_Service

# Canonical *for this node*: an actor id is the URL that reaches it here, so a
# hosted actor is named base_url + "actors/" + slug (ADR-0073). An id under
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
# AC-1: Unit tests for get_actor_dl()
# ---------------------------------------------------------------------------


def test_get_actor_dl_passes_a_canonical_uri_through(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-1a: An already-canonical segment is used as-is.

    ``canonical_actor_uri`` returns any id that already carries a scheme
    unchanged, so the store is keyed by exactly the URI the caller named — no
    double-prefixing into ``{base}/actors/https:/...``.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    myactor_dl.save(actor)

    result: DataLayer = get_actor_dl(actor_id=CANONICAL_URI)

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == CANONICAL_URI


def test_get_actor_dl_expands_a_bare_segment_to_the_canonical_uri(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-1b: A bare path segment is expanded, not looked up.

    ``/actors/myactor/...`` carries only the final segment.  Pre-ADR-0073 that was
    resolved by ``dl.find_actor_by_short_id()`` scanning a shared store; it is now
    ``{node base URL}/actors/myactor``, computed without touching any store.  The
    returned DL must still be keyed by the canonical URI, not the segment
    (ARCH-13-003) — a store keyed by ``"myactor"`` would be a second store for the
    same actor.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    myactor_dl.save(actor)

    result: DataLayer = get_actor_dl(actor_id=SHORT_ID)

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == CANONICAL_URI, (
        f"Expected canonical URI '{CANONICAL_URI}', "
        f"got '{result._actor_id}'"
    )


def test_get_actor_dl_does_not_require_the_actor_to_exist(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-1c: Resolution is a computation, so an unknown id still resolves.

    There is nothing to "not find": no store is consulted, so an id for which no
    record exists yields a store keyed by that id rather than a 404 from the
    dependency.  The route body is what decides whether an absent actor is an
    error.

    The id used here carries a scheme and is therefore returned verbatim,
    *including* its authority.  For a foreign authority that means a local store
    minted for an actor this node does not host — deliberate (delivery posts to a
    peer's own URL) but not free; see issue #2549 and the collision warning in
    ``get_actor_engine``.
    """
    unknown_id = "https://example.org/actors/unknown"

    result: DataLayer = get_actor_dl(actor_id=unknown_id)

    assert isinstance(result, SqliteDataLayer)
    assert result._actor_id == unknown_id


# ---------------------------------------------------------------------------
# AC-3: Regression tests for BUG-2026040901
# ---------------------------------------------------------------------------


def test_one_actor_has_exactly_one_queue_regardless_of_spelling() -> None:
    """BUG-2026040901 is structurally impossible now (ADR-0073).

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


def test_get_actor_dl_resolves_canonical_uri_for_queue_reads(
    myactor_dl: SqliteDataLayer,
) -> None:
    """AC-3b: get_actor_dl() returns a DL that can read the outbox.

    Regression for BUG-2026040901: when the URL path carries a short segment,
    ``get_actor_dl()`` must resolve it to the canonical URI so that
    ``outbox_list()`` reads the queue that actor's own writes went to.

    The test above asserts the same property of the ``get_datalayer`` factory;
    this one asserts it of the FastAPI dependency, which is the path a request
    actually takes.
    """
    actor = as_Service(id_=CANONICAL_URI, name="MyActor")
    myactor_dl.save(actor)

    myactor_dl.outbox_append(activity_id=ACTIVITY_ID)

    actor_dl: DataLayer = get_actor_dl(actor_id=SHORT_ID)

    assert ACTIVITY_ID in actor_dl.outbox_list(), (
        "get_actor_dl must resolve the short UUID to the canonical "
        "URI so that outbox reads succeed (BUG-2026040901 regression)"
    )


# ---------------------------------------------------------------------------
# node_base_url: which node's namespace a path segment resolves into.
# ---------------------------------------------------------------------------


class _FakeRequest:
    """A ``Request`` stand-in exposing only ``app.state``.

    Deliberately not a real ``Request``: the point of these tests is that
    ``node_base_url`` reads *app* state and never touches the request's own URL or
    headers, so a stub that has no URL at all proves it by construction — a
    regression to ``request.url`` or ``request.headers["host"]`` raises here
    instead of quietly passing.
    """

    def __init__(self, **state: object) -> None:
        self.app = type("_App", (), {"state": type("_State", (), state)()})()


def _fake_request(**state: object) -> Request:
    """A ``_FakeRequest`` typed as the ``Request`` the dependencies declare.

    The cast is the whole point of the stub, stated to the type checker: these
    tests assert that only ``app.state`` is read, so the object deliberately
    cannot satisfy ``Request`` structurally.
    """
    return cast(Request, _FakeRequest(**state))


class TestNodeBaseUrl:
    def test_returns_the_base_url_the_app_declares(self):
        assert (
            node_base_url(
                _fake_request(node_base_url="https://vendor.test/api")
            )
            == "https://vendor.test/api"
        )

    def test_returns_none_when_there_is_no_request(self):
        """CLI and background paths have no request; config is then the answer."""
        assert node_base_url(None) is None

    def test_returns_none_when_the_app_declares_nothing(self):
        """Production keeps its previous behaviour: fall back to config."""
        assert node_base_url(_fake_request()) is None

    @pytest.mark.parametrize("junk", ["", 0, object()])
    def test_ignores_a_value_that_is_not_a_usable_base_url(self, junk):
        """An empty string would build ``"/actors/vendor"`` — a relative id."""
        assert node_base_url(_fake_request(node_base_url=junk)) is None

    def test_never_consults_the_request_url_or_host_header(self):
        """The stated security property, asserted rather than assumed.

        Deriving the base from the request would let a client pick which store the
        node opens by sending a different ``Host``: two requests for one actor
        would resolve to two canonical URIs and therefore two stores. It would
        also break every ``TestClient`` test, which arrives as
        ``http://testserver``.
        """
        request = _fake_request(node_base_url="https://declared.test/api")
        assert not hasattr(request, "url")
        assert not hasattr(request, "headers")
        assert node_base_url(request) == "https://declared.test/api"


def test_get_actor_dl_resolves_into_the_serving_apps_namespace(
    myactor_dl: SqliteDataLayer,
) -> None:
    """One process hosting two nodes must not collapse them into one store.

    ``node_base_url`` is app-scoped precisely so the demo harness can run several
    nodes in one process. If the segment resolved against process-global config
    instead, ``vendor`` on node A and ``vendor`` on node B would be one canonical
    URI and one store — cross-node knowledge leakage that ADR-0073 exists to
    prevent.
    """
    node_a = cast(
        SqliteDataLayer,
        get_actor_dl(
            actor_id=SHORT_ID,
            request=_fake_request(node_base_url="https://node-a.test/api/v2"),
        ),
    )
    node_b = cast(
        SqliteDataLayer,
        get_actor_dl(
            actor_id=SHORT_ID,
            request=_fake_request(node_base_url="https://node-b.test/api/v2"),
        ),
    )

    assert node_a.actor_id == f"https://node-a.test/api/v2/actors/{SHORT_ID}"
    assert node_b.actor_id == f"https://node-b.test/api/v2/actors/{SHORT_ID}"
    assert node_a.actor_id != node_b.actor_id


# ---------------------------------------------------------------------------
# The alias dependencies must resolve *through* get_actor_dl, not call it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alias", [get_trigger_dl, get_canonical_actor_dl])
def test_alias_deps_delegate_through_depends(alias) -> None:
    """An override of ``get_actor_dl`` must reach the alias dependencies too.

    These aliases used to call ``get_actor_dl(actor_id, request)`` as a plain
    function.  A plain call bypasses FastAPI's override table, so
    ``app.dependency_overrides[get_actor_dl]`` applied to ``/actors/*`` routes
    and not to ``/actors/{id}/trigger/*`` — one app, one actor, two stores.
    Asserting the *signature* rather than the behaviour catches the regression
    at its cause: the delegation has to be a ``Depends`` default.
    """
    import inspect

    params = list(inspect.signature(alias).parameters.values())
    assert len(params) == 1, (
        f"{alias.__name__} must take exactly one parameter, the injected"
        f" DataLayer; got {[p.name for p in params]}"
    )
    default = params[0].default
    assert isinstance(default, params_Depends), (
        f"{alias.__name__} must delegate via Depends(get_actor_dl) so that"
        " dependency_overrides propagate; got default {default!r}"
    )
    assert default.dependency is get_actor_dl
