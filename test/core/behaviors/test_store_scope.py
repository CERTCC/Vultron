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

"""Tests for ``vultron.core.behaviors.store_scope`` (ADR-0073, DL-07-005).

This module is the single answer to "which store belongs to this actor?", created
because three copies of the logic — ``BTBridge._store_for_actor``,
``WritePendingReportCaseLinkNode._store_for`` and a demo seeding helper —
disagreed about two cases: what to do with a test double, and whether a store may
be opened for an actor this node does not host.

Every fall-through is asserted here rather than at the three call sites, because
the reason they were consolidated is that each call site tested only the case its
author had in mind. The two that matter most:

- a store that cannot name its own actor is returned unchanged, so test doubles
  and non-actor-scoped implementations keep working (BT-05-005's one exception);
- ``require_same_authority`` returns ``None`` rather than a clone, because
  ``clone_for_actor`` succeeds for *any* well-formed id — so a remote actor's id
  otherwise yields a fresh empty local store that looks like a successful publish
  and publishes nothing (#2484).
"""

from typing import Any, cast

import pytest

from vultron.core.behaviors.store_scope import (
    port_for_store,
    same_authority,
    store_for_actor,
)
from vultron.core.ports.case_persistence import CasePersistence

_NODE = "http://vendor:7999/api/v2"
_OWN = f"{_NODE}/actors/vendor"
_SIBLING = f"{_NODE}/actors/case-actor-abc"
_FOREIGN = "http://finder:7999/api/v2/actors/finder"


class _Store:
    """An actor-scoped store double that records what it was cloned for."""

    def __init__(self, actor_id: Any = _OWN) -> None:
        self.actor_id = actor_id
        self.cloned_for: list[str] = []

    def clone_for_actor(self, actor_id: str) -> "_Store":
        self.cloned_for.append(actor_id)
        clone = _Store(actor_id)
        return clone


class _UnscopedStore:
    """A store that reports no actor of its own — e.g. a hand-rolled test double."""


def _scope(store: Any, actor_id: str, **kwargs: Any) -> Any:
    return store_for_actor(cast(CasePersistence, store), actor_id, **kwargs)


class TestSameAuthority:
    def test_two_actors_on_one_node_match(self):
        """The final segment is the very thing that differs between actors."""
        assert same_authority(_OWN, _SIBLING) is True

    def test_a_differing_path_prefix_does_not_change_the_node(self):
        """``/api/v2`` versus ``/`` is the same process answering."""
        assert same_authority(_OWN, "http://vendor:7999/actors/other") is True

    def test_a_different_host_is_a_different_node(self):
        assert same_authority(_OWN, _FOREIGN) is False

    def test_the_port_is_part_of_the_authority(self):
        """Two containers on one host are two nodes."""
        assert (
            same_authority(_OWN, "http://vendor:8000/api/v2/actors/vendor")
            is False
        )

    def test_the_scheme_is_part_of_the_authority(self):
        assert (
            same_authority(_OWN, "https://vendor:7999/api/v2/actors/vendor")
            is False
        )

    @pytest.mark.parametrize(
        "a, b", [("", _OWN), (_OWN, ""), ("", ""), (None, _OWN)]
    )
    def test_an_absent_id_is_never_the_same_authority(self, a, b):
        """Refusing is the safe answer: an unknown authority is not "mine"."""
        assert same_authority(a, b) is False

    def test_two_bare_names_are_co_hosted(self):
        """Both share the empty authority, and that is the right answer.

        A bare segment is what ``canonical_actor_uri`` expands against *this*
        node's base URL, so two of them necessarily name actors here. Pinned
        because the reasoning is not obvious from the comparison itself — it
        reads like an accident of ``urlsplit`` returning ``("", "")``.
        """
        assert same_authority("vendor", "finder") is True

    def test_a_bare_name_and_an_absolute_uri_are_not_co_hosted(self):
        """The asymmetry that makes the case above safe: an id that *does* carry
        an authority is compared against it, so a bare name never matches a
        remote node."""
        assert same_authority("vendor", _FOREIGN) is False


class TestStoreForActorFallThroughs:
    """The cases where the store is returned unchanged, and why."""

    def test_an_empty_actor_id_leaves_the_store_alone(self):
        """Nothing to reconcile against; cloning for ``""`` would mint a store
        keyed by the empty string."""
        store = _Store()
        assert _scope(store, "") is store
        assert store.cloned_for == []

    def test_a_store_that_names_no_actor_is_left_alone(self):
        """BT-05-005's one exception: test doubles were correct before ADR-0073."""
        store = _UnscopedStore()
        assert _scope(store, _SIBLING) is store

    @pytest.mark.parametrize("own", [None, "", 0, 42, object()])
    def test_a_non_string_or_empty_own_actor_id_is_left_alone(self, own):
        """A store reporting a non-string ``actor_id`` cannot be compared.

        Coercing it would compare ``"42"`` against a URI and clone every time.
        """
        store = _Store(own)
        assert _scope(store, _SIBLING) is store
        assert store.cloned_for == []

    def test_a_store_already_belonging_to_the_actor_is_returned_as_is(self):
        """An identity clone would be a wasted engine lookup, not a bug — but
        returning the same object keeps ``is`` comparisons at call sites honest.
        """
        store = _Store(_OWN)
        assert _scope(store, _OWN) is store
        assert store.cloned_for == []

    def test_a_store_without_clone_for_actor_is_left_alone(self):
        """The last fall-through: a partial double that names an actor but
        cannot re-scope."""

        class _NoClone:
            actor_id = _OWN

        store = _NoClone()
        assert _scope(store, _SIBLING) is store

    def test_a_non_callable_clone_attribute_is_not_invoked(self):
        """``getattr`` finding a non-callable must not raise ``TypeError``."""

        class _WeirdClone:
            actor_id = _OWN
            clone_for_actor = "not callable"

        store = _WeirdClone()
        assert _scope(store, _SIBLING) is store


class TestStoreForActorScoping:
    def test_a_co_hosted_sibling_is_reached_by_cloning(self):
        """The delegated-emit case: a trigger emitting as the CaseActor.

        Without this the activity is created in one store and queued in the
        other's outbox, so the CaseActor never delivers it and the outbox entry
        names an activity its own store does not hold (PCR-08-007, CM-24-004).
        """
        store = _Store(_OWN)
        scoped = _scope(store, _SIBLING)
        assert scoped is not store
        assert scoped.actor_id == _SIBLING
        assert store.cloned_for == [_SIBLING]

    def test_a_foreign_authority_is_cloned_when_not_asked_to_refuse(self):
        """``BTBridge`` relies on this: the executing actor is one it runs as, so
        it does not set the flag and must never get ``None`` back."""
        store = _Store(_OWN)
        assert _scope(store, _FOREIGN).actor_id == _FOREIGN


class TestRequireSameAuthority:
    def test_a_foreign_actor_yields_none_instead_of_an_empty_store(self):
        """#2484: the failure this flag exists to prevent.

        ``clone_for_actor`` succeeds for any well-formed id, so a remote actor's
        id produced a fresh empty local store — a publish that looked like it
        worked and delivered nothing. ``None`` forces the caller to decide.
        """
        store = _Store(_OWN)
        assert _scope(store, _FOREIGN, require_same_authority=True) is None
        assert store.cloned_for == []

    def test_a_co_hosted_actor_is_still_reached(self):
        """The flag refuses foreign actors, not re-scoping as such."""
        store = _Store(_OWN)
        scoped = _scope(store, _SIBLING, require_same_authority=True)
        assert scoped is not None
        assert scoped.actor_id == _SIBLING

    def test_the_flag_does_not_override_the_earlier_fall_throughs(self):
        """A store that names no actor has no authority to compare, so it is
        returned rather than refused — otherwise every test double would get
        ``None`` from an inbox endpoint."""
        store = _UnscopedStore()
        assert _scope(store, _FOREIGN, require_same_authority=True) is store

    def test_defaults_to_permissive(self):
        """The default has to stay permissive: ``BTBridge`` calls it without the
        flag and treats ``None`` as impossible."""
        assert _scope(_Store(_OWN), _FOREIGN) is not None

    def test_logs_which_actor_was_refused(self, caplog):
        """A silent ``None`` is hard to diagnose from a missing delivery."""
        import logging

        with caplog.at_level(
            logging.DEBUG, logger="vultron.core.behaviors.store_scope"
        ):
            _scope(_Store(_OWN), _FOREIGN, require_same_authority=True)
        assert _FOREIGN in caplog.text


class _Port:
    """A driven-adapter double that holds its own store, as the real ones do."""

    def __init__(self, dl: Any) -> None:
        self._dl = dl

    def for_store(self, dl: Any) -> "_Port":
        if dl is self._dl:
            return self
        return type(self)(dl)


class _StatelessPort:
    """A port with no store of its own — nothing to reconcile."""


@pytest.mark.spec("DL-07-009")
class TestPortForStore:
    """DL-07-009: the other half of the reconciliation ``store_for_actor`` starts.

    Reconciling only the store fixes half of a two-halved write: the adapter
    creates the activity in the store it was constructed with, while the node
    queues its id through the reconciled store. The outbox entry then names an
    activity its own store does not hold, delivery skips it with a warning, and
    the invitee is never told it was invited (ISSUE-2548).
    """

    def test_a_port_holding_a_store_is_rebound_to_the_new_one(self):
        requesting = _Store(_OWN)
        executing = _Store(_SIBLING)
        port = _Port(requesting)

        rebound = port_for_store(port, cast(CasePersistence, executing))

        assert rebound is not port
        assert rebound._dl is executing

    def test_rebinding_to_the_store_it_already_holds_returns_the_same_port(
        self,
    ):
        """The non-delegated path is every other trigger; it must allocate
        nothing."""
        store = _Store(_OWN)
        port = _Port(store)
        assert port_for_store(port, cast(CasePersistence, store)) is port

    def test_a_port_that_does_not_opt_in_is_returned_untouched(self):
        """A stateless port must not be swapped out behind its caller's back."""
        port = _StatelessPort()
        assert port_for_store(port, cast(CasePersistence, _Store())) is port

    def test_none_is_passed_through(self):
        """``BTBridge`` holds optional ports; absent is the common case."""
        assert port_for_store(None, cast(CasePersistence, _Store())) is None

    def test_a_bare_mock_is_not_rebound(self):
        """The reason the lookup is on ``type(port)`` and not the instance.

        ``Mock()`` answers *any* attribute with another callable ``Mock``, so an
        instance-level ``getattr`` would replace every test double with a Mock
        return value — and assertions made against the original would pass
        vacuously or fail for reasons that have nothing to do with the test.
        """
        from unittest.mock import MagicMock, Mock

        for double in (Mock(), MagicMock()):
            assert (
                port_for_store(double, cast(CasePersistence, _Store()))
                is double
            )

    def test_a_spec_mock_of_a_real_port_is_not_rebound(self):
        """Spec'd mocks are the common form in this suite; same guarantee."""
        from unittest.mock import Mock

        from vultron.core.ports.sync_activity import SyncActivityPort

        double = Mock(spec=SyncActivityPort)
        assert (
            port_for_store(double, cast(CasePersistence, _Store())) is double
        )
