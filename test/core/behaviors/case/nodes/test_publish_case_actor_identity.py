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

"""Behavioural tests for ``PublishCaseActorIdentityNode`` (#1872, CP-04-003).

The node that this one replaced, ``ResolveCaseActorUrlsNode``, *derived* a
per-case identity — ``{base}/actors/case-actor-{slug}`` — that no container ever
hosted, so ``POST /actors/case-actor-<slug>/inbox/`` answered a permanent 404 and
the CaseProposal round-trip never began. Its coverage went with it: 298 lines were
deleted from ``test_case_setup.py`` and the replacement was left with a structural
tree-shape assertion in ``test_create_tree.py``.

What that assertion cannot see is the two things this node actually does — publish
two blackboard keys, and refuse rather than guess. Both are the fix for #1872: a
guessed base URL reproduces the phantom identity exactly, just with a different
spelling.
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case import case_actor_identity as identity_mod
from vultron.core.behaviors.case.nodes.case_setup import (
    PublishCaseActorIdentityNode,
)

CASE_ID = "https://example.org/cases/case-pcai-001"
ACTOR_ID = "https://example.org/api/v2/actors/vendor"
SERVICE_URL = "http://case-actor:7999/api/v2"
EXPECTED_IDENTITY = f"{SERVICE_URL}/actors/case-actor"


@pytest.fixture
def configured(monkeypatch):
    """Configure a CaseActor service URL for the duration of a test."""
    monkeypatch.setattr(
        identity_mod,
        "case_actor_identity",
        lambda base_url=None: EXPECTED_IDENTITY,
    )


@pytest.fixture
def unconfigured(monkeypatch):
    """No ``case_actor_service_url`` — the state a bare node starts in."""
    monkeypatch.setattr(
        identity_mod, "case_actor_identity", lambda base_url=None: None
    )


def _blackboard(node: py_trees.behaviour.Behaviour, key: str):
    client = py_trees.blackboard.Client(name="probe")
    client.register_key(key=key, access=py_trees.common.Access.READ)
    return client.get(key)


class TestPublishesTheIdentity:
    @pytest.mark.executes_as(ACTOR_ID)
    def test_succeeds_and_writes_both_keys(
        self, bt_scenario: BTTestScenario, configured
    ) -> None:
        """The whole job: two keys downstream nodes read.

        ``test_create_tree.py`` asserts the node is *in* the tree; nothing asserted
        that it puts anything on the blackboard, so a node that succeeded while
        writing nothing would have looked correct.
        """
        node = PublishCaseActorIdentityNode(case_id=CASE_ID)
        result = bt_scenario.run(node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        assert _blackboard(node, "/case_id") == CASE_ID
        assert _blackboard(node, "/case_actor_id") == EXPECTED_IDENTITY

    @pytest.mark.executes_as(ACTOR_ID)
    def test_the_published_identity_is_not_per_case(
        self, bt_scenario: BTTestScenario, configured
    ) -> None:
        """CP-04-002: one CaseActor per container, not one per case.

        The retired node suffixed a case-derived slug. If a slug ever reappears
        here, the identity becomes one the sender invented and delivery 404s
        permanently — the exact failure of #1872.
        """
        node = PublishCaseActorIdentityNode(case_id=CASE_ID)
        bt_scenario.run(node, actor_id=ACTOR_ID)

        published = _blackboard(node, "/case_actor_id")
        assert published.endswith("/actors/case-actor")
        assert "case-actor-" not in published

    @pytest.mark.executes_as(ACTOR_ID)
    def test_two_cases_publish_the_same_identity(
        self, bt_scenario: BTTestScenario, configured
    ) -> None:
        """Which case it acts on travels in ``activity.context``, not the URI."""
        first = PublishCaseActorIdentityNode(case_id=CASE_ID)
        second = PublishCaseActorIdentityNode(
            case_id="https://example.org/cases/case-pcai-002"
        )
        bt_scenario.run(first, actor_id=ACTOR_ID)
        bt_scenario.run(second, actor_id=ACTOR_ID)

        assert _blackboard(first, "/case_actor_id") == _blackboard(
            second, "/case_actor_id"
        )

    @pytest.mark.executes_as(ACTOR_ID)
    def test_it_creates_nothing(
        self, bt_scenario: BTTestScenario, configured
    ) -> None:
        """Provisioning belongs to whoever hosts the CaseActor (CP-04-004).

        ``ResolveCaseActorUrlsNode`` also created a per-case ``VultronCaseActor``
        Service object. Writing one here would put it in the *sending* actor's
        store, which is the wrong store for an identity that has to answer an
        inbox POST.
        """
        node = PublishCaseActorIdentityNode(case_id=CASE_ID)
        bt_scenario.run(node, actor_id=ACTOR_ID)

        assert bt_scenario.dl.count_all().get("Service", 0) == 0
        assert bt_scenario.dl.read(EXPECTED_IDENTITY) is None


class TestFailurePaths:
    """Both FAILURE returns, neither of which had a test."""

    @pytest.mark.executes_as(ACTOR_ID)
    def test_fails_when_the_service_url_is_unconfigured(
        self, bt_scenario: BTTestScenario, unconfigured
    ) -> None:
        """Refusing beats falling back to this node's own base URL.

        A guessed base is how the proposal ends up addressed to an actor that does
        not exist — #1872 with a different spelling. FAILURE here stops the tree
        while the misconfiguration is still visible as a misconfiguration.
        """
        node = PublishCaseActorIdentityNode(case_id=CASE_ID)
        result = bt_scenario.run(node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        assert "case_actor_service_url" in node.feedback_message
        assert "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL" in node.feedback_message

    @pytest.mark.executes_as(ACTOR_ID)
    def test_publishes_nothing_when_it_fails(
        self, bt_scenario: BTTestScenario, unconfigured
    ) -> None:
        """A half-published blackboard is worse than none.

        ``case_id`` alone would let a downstream node read a stale
        ``case_actor_id`` from an earlier tick and address the proposal to the
        wrong container.
        """
        node = PublishCaseActorIdentityNode(case_id=CASE_ID)
        bt_scenario.run(node, actor_id=ACTOR_ID)

        with pytest.raises(KeyError):
            _blackboard(node, "/case_actor_id")

    @pytest.mark.executes_as(ACTOR_ID)
    @pytest.mark.parametrize("empty", ["", None])
    def test_fails_when_case_id_is_empty(
        self, bt_scenario: BTTestScenario, configured, empty
    ) -> None:
        """``case_id`` is a constructor argument, so an empty one is a caller bug.

        Publishing an empty ``case_id`` would send a CaseProposal with no case.
        """
        node = PublishCaseActorIdentityNode(case_id=empty)
        result = bt_scenario.run(node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        assert "case_id" in node.feedback_message

    @pytest.mark.executes_as(ACTOR_ID)
    def test_the_case_id_check_runs_before_the_config_read(
        self, bt_scenario: BTTestScenario, unconfigured
    ) -> None:
        """Two things wrong: report the caller's bug, not the deployment's.

        A missing ``case_id`` is a programming error and a missing service URL is a
        misconfiguration; reporting the latter would send an operator to the wrong
        place.
        """
        node = PublishCaseActorIdentityNode(case_id="")
        bt_scenario.run(node, actor_id=ACTOR_ID)

        assert "case_id is empty" in node.feedback_message


class TestPortDeclaration:
    def test_both_outputs_are_declared_required(self) -> None:
        """Undeclared writes are invisible to the port-contract checks that keep
        producer and consumer keys in step."""
        ports = PublishCaseActorIdentityNode.output_ports()
        assert set(ports) == {"case_id", "case_actor_id"}
        assert all(p.required for p in ports.values())

    def test_the_keys_are_remapped_to_the_blackboard_root(self) -> None:
        """Consumers read ``/case_actor_id``; a node-scoped key would be a
        different variable that silently never arrives."""
        assert PublishCaseActorIdentityNode._domain_port_remappings() == {
            "case_id": "/case_id",
            "case_actor_id": "/case_actor_id",
        }
