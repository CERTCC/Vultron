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
from typing import cast

import pytest

from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    owner_embargo_policies,
    resolve_initial_embargo_duration,
    select_actor_default,
    select_actor_default_policy,
)

ACTOR_ID = "https://example.org/actors/vendor"
OTHER_ACTOR_ID = "https://example.org/actors/other"
PROTOCOL_DEFAULT = timedelta(hours=72)


def _policy(
    policy_id: str, days: int, actor_id: str = ACTOR_ID
) -> EmbargoPolicy:
    return EmbargoPolicy(
        id_=f"{actor_id}/{policy_id}",
        actor_id=actor_id,
        inbox=f"{actor_id}/inbox",
        preferred_duration=timedelta(days=days),
    )


class _PolicyStore:
    """The one ``CasePersistence`` method ``owner_embargo_policies`` reads."""

    def __init__(self, records: list[PersistableModel]) -> None:
        self.records = records
        self.queried: list[str] = []

    def list_objects(self, type_key: str) -> list[PersistableModel]:
        self.queried.append(type_key)
        return list(self.records)


class TestOwnerEmbargoPolicies:
    """The candidate set is the owner's own policies and nothing else."""

    @pytest.mark.spec("EP-04-006")
    def test_only_the_owners_policies_are_returned(self) -> None:
        """Another actor's shorter policy in the same store is excluded
        (#3753 scoping), and the lookup is keyed on the policy type."""
        mine = _policy("mine", 30)
        store = _PolicyStore(
            [mine, _policy("theirs", 5, actor_id=OTHER_ACTOR_ID)]
        )

        policies = owner_embargo_policies(
            cast(CasePersistence, store), ACTOR_ID
        )

        assert [p.id_ for p in policies] == [mine.id_]
        assert store.queried == [VultronObjectType.EMBARGO_POLICY]

    def test_no_policies_for_owner_is_empty(self) -> None:
        store = _PolicyStore([_policy("theirs", 5, actor_id=OTHER_ACTOR_ID)])

        assert (
            owner_embargo_policies(cast(CasePersistence, store), ACTOR_ID)
            == []
        )


class TestSelectActorDefault:
    def test_no_policies_is_none(self) -> None:
        assert select_actor_default([]) is None
        assert select_actor_default_policy([]) is None

    @pytest.mark.spec("EP-04-010")
    def test_the_policy_shown_is_the_one_whose_duration_is_used(self) -> None:
        """The embargo-policy endpoint shows ``select_actor_default_policy``'s
        choice, so it must be the record ``select_actor_default`` reads."""
        policies = [_policy("a", 45), _policy("b", 14), _policy("c", 60)]
        chosen = select_actor_default_policy(policies)
        assert chosen is not None
        assert chosen.id_ == _policy("b", 14).id_
        assert chosen.preferred_duration == select_actor_default(policies)

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
