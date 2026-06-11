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

"""Tests for participant helper behavior."""

import logging
from typing import Any, cast

from vultron.core.behaviors.case.nodes import _create_and_attach_participant
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.states.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario


class TestCreateAndAttachParticipant:
    """Unit tests for the shared _create_and_attach_participant helper."""

    def test_creates_participant_in_datalayer(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert bt_scenario.dl.read(participant.id_) is not None

    def test_attaches_participant_to_case(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert participant.id_ in result.case_participants

    def test_updates_actor_participant_index(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        assert result.actor_participant_index.get(actor_id) == participant.id_

    def test_returns_unsaved_case(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """The returned case is unsaved; the caller controls the final save."""
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            case_obj.id_,
            actor_id,
            logging.getLogger("test"),
        )
        assert result is not None
        persisted = cast(Any, bt_scenario.dl.read(case_obj.id_))
        assert participant.id_ not in persisted.case_participants

    def test_idempotent_participant_creation(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VultronCase,
        actor_id: str,
    ) -> None:
        """Calling twice does not create a duplicate participant."""
        participant = VultronParticipant(
            attributed_to=actor_id,
            context=case_obj.id_,
            case_roles=[CVDRole.VENDOR],
        )
        node_logger = logging.getLogger("test")
        _create_and_attach_participant(
            bt_scenario.dl, participant, case_obj.id_, actor_id, node_logger
        )
        bt_scenario.dl.save(cast(Any, bt_scenario.dl.read(case_obj.id_)))

        result2 = _create_and_attach_participant(
            bt_scenario.dl, participant, case_obj.id_, actor_id, node_logger
        )
        assert result2 is not None
        assert result2.case_participants.count(participant.id_) == 1

    def test_returns_none_when_case_not_found(
        self, bt_scenario: BTTestScenario, actor_id: str
    ) -> None:
        participant = VultronParticipant(
            attributed_to=actor_id,
            context="https://example.org/cases/missing",
            case_roles=[CVDRole.VENDOR],
        )
        result = _create_and_attach_participant(
            bt_scenario.dl,
            participant,
            "https://example.org/cases/missing",
            actor_id,
            logging.getLogger("test"),
        )
        assert result is None
