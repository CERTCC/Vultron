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

from vultron.core.models.actor import VultronOrganization
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    actor_default_duration,
    resolve_initial_embargo_duration,
    stored_actor_profile,
)
from vultron.errors import VultronNotFoundError

ACTOR_ID = "https://example.org/actors/vendor"
OTHER_ACTOR_ID = "https://example.org/actors/other"
PROTOCOL_DEFAULT = timedelta(hours=72)


def _policy(days: int, actor_id: str = ACTOR_ID) -> EmbargoPolicy:
    return EmbargoPolicy(
        actor_id=actor_id,
        inbox=f"{actor_id}/inbox",
        preferred_duration=timedelta(days=days),
    )


class _ActorStore:
    """The one ``CasePersistence`` method ``stored_actor_profile`` reads."""

    def __init__(self, records: dict[str, PersistableModel]) -> None:
        self.records = records

    def read(self, object_id: str) -> PersistableModel | None:
        return self.records.get(object_id)


class TestActorDefaultDuration:
    """The actor default is the profile's own policy and nothing else."""

    @pytest.mark.spec("EP-04-006")
    @pytest.mark.spec("CP-01-010")
    def test_the_profile_policy_is_the_actor_default(self) -> None:
        profile = VultronOrganization(id_=ACTOR_ID, embargo_policy=_policy(30))
        assert actor_default_duration(profile) == timedelta(days=30)

    @pytest.mark.spec("CP-01-010")
    def test_a_profile_without_a_policy_has_no_actor_default(self) -> None:
        assert (
            actor_default_duration(VultronOrganization(id_=ACTOR_ID)) is None
        )


class TestStoredActorProfile:
    def test_returns_the_actors_own_record(self) -> None:
        profile = VultronOrganization(id_=ACTOR_ID)
        store = _ActorStore({ACTOR_ID: profile})
        assert (
            stored_actor_profile(cast(CasePersistence, store), ACTOR_ID)
            is profile
        )

    def test_a_missing_record_raises(self) -> None:
        store = _ActorStore({})
        with pytest.raises(VultronNotFoundError):
            stored_actor_profile(cast(CasePersistence, store), ACTOR_ID)

    def test_a_non_actor_record_raises(self) -> None:
        store = _ActorStore({ACTOR_ID: _policy(5)})
        with pytest.raises(VultronNotFoundError):
            stored_actor_profile(cast(CasePersistence, store), ACTOR_ID)


class TestProfilePolicyOwnership:
    @pytest.mark.spec("EP-01-001")
    @pytest.mark.spec("ARCH-10-001")
    def test_a_profile_cannot_carry_another_actors_policy(self) -> None:
        with pytest.raises(ValueError, match="differs from the profile id"):
            VultronOrganization(
                id_=ACTOR_ID, embargo_policy=_policy(5, OTHER_ACTOR_ID)
            )


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
