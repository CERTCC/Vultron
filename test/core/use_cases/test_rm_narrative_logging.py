#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Narrative RM logging tests for ``update_participant_rm_state``.

Covers SL-04-001 (all state transitions logged at INFO), SL-04-006 (narrative
template), and SL-04-007 (the idempotent no-op line is DEBUG, not INFO).
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import (
    current_participant_rm_state,
    update_participant_rm_state,
)
from vultron.enums.roles import CVDRole

_ACTOR_ID = "https://example.org/actors/vendor-001"
_CASE_ID = "https://example.org/cases/case-001"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-001"
_HELPERS_LOGGER = "vultron.core.use_cases._helpers"


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture()
def seeded_case(dl: SqliteDataLayer) -> VulnerabilityCase:
    """Case with one VENDOR participant registered on both surfaces."""
    participant = CaseParticipant(
        id_=_PARTICIPANT_ID,
        attributed_to=_ACTOR_ID,
        context=_CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    dl.create(participant)
    case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
    case.add_participant(participant)
    dl.create(case)
    stored = dl.read(_CASE_ID)
    assert isinstance(stored, VulnerabilityCase)
    return stored


def _narrative_records(caplog) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if "RM:" in r.getMessage() and r.levelno == logging.INFO
    ]


class TestUpdateParticipantRmStateLogging:
    """update_participant_rm_state emits the RM narrative line at INFO."""

    def test_first_transition_logged_from_start(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer, caplog
    ) -> None:
        """A participant with no prior status reports RM START as before."""
        with caplog.at_level(logging.INFO, logger=_HELPERS_LOGGER):
            assert update_participant_rm_state(
                _CASE_ID, _ACTOR_ID, RM.RECEIVED, dl
            )

        records = _narrative_records(caplog)
        assert records, "Expected a narrative RM line at INFO"
        message = records[0].getMessage()
        assert (
            message == f"Actor '{_ACTOR_ID}' RM: START → RECEIVED"
            f" for case '{_CASE_ID}'"
        )

    def test_subsequent_transition_reports_actual_before_state(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer, caplog
    ) -> None:
        """The before-state is read from the latest ParticipantStatus."""
        assert update_participant_rm_state(
            _CASE_ID, _ACTOR_ID, RM.RECEIVED, dl
        )
        assert update_participant_rm_state(_CASE_ID, _ACTOR_ID, RM.VALID, dl)

        # Drop the setup transitions: caplog captures every record emitted
        # during the test, not only those inside the at_level() block.
        caplog.clear()
        with caplog.at_level(logging.INFO, logger=_HELPERS_LOGGER):
            assert update_participant_rm_state(
                _CASE_ID, _ACTOR_ID, RM.ACCEPTED, dl
            )

        records = _narrative_records(caplog)
        assert records, "Expected a narrative RM line at INFO"
        assert (
            records[0].getMessage()
            == f"Actor '{_ACTOR_ID}' RM: VALID → ACCEPTED"
            f" for case '{_CASE_ID}'"
        )

    def test_idempotent_repeat_is_debug_not_info(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer, caplog
    ) -> None:
        """A no-op repeat is bookkeeping, not a transition (SL-04-007)."""
        assert update_participant_rm_state(
            _CASE_ID, _ACTOR_ID, RM.RECEIVED, dl
        )

        # Drop the setup transition's own narrative line before asserting.
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger=_HELPERS_LOGGER):
            assert update_participant_rm_state(
                _CASE_ID, _ACTOR_ID, RM.RECEIVED, dl
            )

        assert not _narrative_records(caplog)
        idempotent = [
            r for r in caplog.records if "(idempotent)" in r.getMessage()
        ]
        assert idempotent, "Expected the idempotent line to still be emitted"
        assert all(r.levelno == logging.DEBUG for r in idempotent)

    def test_blocked_transition_emits_no_narrative_line(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer, caplog
    ) -> None:
        """A rejected RM transition must not claim it happened.

        ``START → CLOSED`` is not a legal RM transition, so the helper must
        return ``False`` and emit no narrative line.
        """
        with caplog.at_level(logging.DEBUG, logger=_HELPERS_LOGGER):
            blocked = update_participant_rm_state(
                _CASE_ID, _ACTOR_ID, RM.CLOSED, dl
            )

        assert blocked is False
        assert not _narrative_records(caplog)


class TestCurrentParticipantRmState:
    """current_participant_rm_state reads the latest RM state, or START."""

    def test_returns_start_when_no_status_recorded(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer
    ) -> None:
        assert (
            current_participant_rm_state(seeded_case, _ACTOR_ID, dl)
            == RM.START
        )

    def test_returns_start_for_unknown_actor(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer
    ) -> None:
        result = current_participant_rm_state(
            seeded_case, "https://example.org/actors/stranger", dl
        )
        assert result == RM.START

    def test_returns_latest_recorded_state(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer
    ) -> None:
        assert update_participant_rm_state(
            _CASE_ID, _ACTOR_ID, RM.RECEIVED, dl
        )
        assert update_participant_rm_state(_CASE_ID, _ACTOR_ID, RM.VALID, dl)

        case = dl.read(_CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        assert current_participant_rm_state(case, _ACTOR_ID, dl) == RM.VALID
