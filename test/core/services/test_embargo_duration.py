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

"""Unit tests for initial embargo duration resolution (EP-04, ADR-0096)."""

from datetime import timedelta

import pytest

from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    resolve_initial_embargo_duration,
    select_actor_default,
)

ACTOR_ID = "https://example.org/actors/vendor"
PROTOCOL_DEFAULT = timedelta(hours=72)


def _policy(policy_id: str, days: int) -> EmbargoPolicy:
    return EmbargoPolicy(
        id_=f"{ACTOR_ID}/{policy_id}",
        actor_id=ACTOR_ID,
        inbox=f"{ACTOR_ID}/inbox",
        preferred_duration=timedelta(days=days),
    )


class TestSelectActorDefault:
    def test_no_policies_is_none(self) -> None:
        assert select_actor_default([]) is None

    @pytest.mark.spec("EP-04-010")
    def test_shortest_wins_regardless_of_order(self) -> None:
        policies = [_policy("a", 45), _policy("b", 14), _policy("c", 60)]
        assert select_actor_default(policies) == timedelta(days=14)
        assert select_actor_default(reversed(policies)) == timedelta(days=14)


class TestResolveInitialEmbargoDuration:
    @pytest.mark.spec("EP-04-005")
    def test_no_candidates_uses_protocol_default(self) -> None:
        resolved = resolve_initial_embargo_duration(
            sender_proposal=None,
            actor_default=None,
            protocol_default=PROTOCOL_DEFAULT,
        )
        assert resolved.duration == PROTOCOL_DEFAULT
        assert resolved.source is EmbargoDurationSource.PROTOCOL_DEFAULT

    @pytest.mark.spec("EP-04-006")
    def test_protocol_default_never_competes(self) -> None:
        resolved = resolve_initial_embargo_duration(
            sender_proposal=None,
            actor_default=timedelta(days=30),
            protocol_default=PROTOCOL_DEFAULT,
        )
        assert resolved.duration == timedelta(days=30)
        assert resolved.source is EmbargoDurationSource.ACTOR_DEFAULT

    @pytest.mark.spec("EP-04-007")
    def test_protocol_default_is_not_a_minimum(self) -> None:
        resolved = resolve_initial_embargo_duration(
            sender_proposal=timedelta(hours=12),
            actor_default=None,
            protocol_default=PROTOCOL_DEFAULT,
        )
        assert resolved.duration == timedelta(hours=12)
        assert resolved.source is EmbargoDurationSource.SENDER_PROPOSAL

    @pytest.mark.parametrize(
        ("sender", "actor", "expected_source"),
        [
            (20, 30, EmbargoDurationSource.SENDER_PROPOSAL),
            (30, 20, EmbargoDurationSource.ACTOR_DEFAULT),
            (30, 30, EmbargoDurationSource.SENDER_PROPOSAL),
        ],
    )
    def test_shorter_candidate_wins(
        self,
        sender: int,
        actor: int,
        expected_source: EmbargoDurationSource,
    ) -> None:
        resolved = resolve_initial_embargo_duration(
            sender_proposal=timedelta(days=sender),
            actor_default=timedelta(days=actor),
            protocol_default=PROTOCOL_DEFAULT,
        )
        assert resolved.duration == timedelta(days=min(sender, actor))
        assert resolved.source is expected_source
