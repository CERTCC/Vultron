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

"""Tests for vultron.core.participants._lookup.iter_case_participants."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants._lookup import iter_case_participants
from vultron.enums.roles import CVDRole

_CASE_ID = "https://example.org/cases/iter-test-001"
_ACTOR_A = "https://example.org/actors/actor-a"
_ACTOR_B = "https://example.org/actors/actor-b"
_P_A = f"{_CASE_ID}/participants/actor-a"
_P_B = f"{_CASE_ID}/participants/actor-b"


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture()
def participant_a() -> CaseParticipant:
    return CaseParticipant(
        id_=_P_A,
        attributed_to=_ACTOR_A,
        context=_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture()
def participant_b() -> CaseParticipant:
    return CaseParticipant(
        id_=_P_B,
        attributed_to=_ACTOR_B,
        context=_CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


class TestIterCaseParticipants:
    def test_yields_indexed_participants(
        self,
        dl: SqliteDataLayer,
        participant_a: CaseParticipant,
    ) -> None:
        """Participant in actor_participant_index is yielded (fast path)."""
        dl.create(participant_a)
        case = VulnerabilityCase(id_=_CASE_ID)
        case.actor_participant_index[_ACTOR_A] = _P_A
        case.case_participants.append(_P_A)

        result = list(iter_case_participants(case, dl))
        assert len(result) == 1
        assert result[0].id_ == _P_A

    def test_yields_fallback_string_ref(
        self,
        dl: SqliteDataLayer,
        participant_a: CaseParticipant,
    ) -> None:
        """Participant in case_participants but not indexed is yielded (bootstrap fallback)."""
        dl.create(participant_a)
        case = VulnerabilityCase(id_=_CASE_ID)
        # Not in actor_participant_index — bootstrap path
        case.case_participants.append(_P_A)

        result = list(iter_case_participants(case, dl))
        assert len(result) == 1
        assert result[0].id_ == _P_A

    def test_yields_inline_participant_in_fallback(
        self,
        dl: SqliteDataLayer,
        participant_a: CaseParticipant,
    ) -> None:
        """Inline CaseParticipant in case_participants is yielded once."""
        case = VulnerabilityCase(id_=_CASE_ID)
        case.case_participants.append(participant_a)  # type: ignore[arg-type]

        result = list(iter_case_participants(case, dl))
        assert len(result) == 1
        assert result[0].id_ == _P_A

    def test_deduplicates_inline_participant_already_in_index(
        self,
        dl: SqliteDataLayer,
        participant_a: CaseParticipant,
    ) -> None:
        """Inline participant also present in index is NOT yielded twice."""
        dl.create(participant_a)
        case = VulnerabilityCase(id_=_CASE_ID)
        case.actor_participant_index[_ACTOR_A] = _P_A
        # Also in case_participants as an inline object
        case.case_participants.append(participant_a)  # type: ignore[arg-type]

        result = list(iter_case_participants(case, dl))
        ids = [p.id_ for p in result]
        assert ids.count(_P_A) == 1

    def test_yields_multiple_participants(
        self,
        dl: SqliteDataLayer,
        participant_a: CaseParticipant,
        participant_b: CaseParticipant,
    ) -> None:
        """Two participants in the index are both yielded."""
        dl.create(participant_a)
        dl.create(participant_b)
        case = VulnerabilityCase(id_=_CASE_ID)
        case.actor_participant_index[_ACTOR_A] = _P_A
        case.actor_participant_index[_ACTOR_B] = _P_B
        case.case_participants.extend([_P_A, _P_B])

        result = list(iter_case_participants(case, dl))
        assert {p.id_ for p in result} == {_P_A, _P_B}

    def test_yields_inline_participant_when_dl_read_fails(
        self,
        dl: SqliteDataLayer,
        participant_a: CaseParticipant,
    ) -> None:
        """Inline participant is yielded even when its DL read returns None.

        Regression for the bootstrap-timing race: a case replica received via
        Announce(VulnerabilityCase) has the participant in both
        actor_participant_index AND case_participants, but the separate
        CaseParticipant object has not yet arrived via ledger sync.  The fast
        path (dl.read) returns None; the slow path must still yield the inline
        object so resolve_case_manager_id can find the CASE_MANAGER.
        """
        # participant_a is NOT saved to the DataLayer — simulates unsynced DL
        case = VulnerabilityCase(id_=_CASE_ID)
        case.actor_participant_index[_ACTOR_A] = _P_A
        # Inline object in case_participants (as received from Announce wire)
        case.case_participants.append(participant_a)  # type: ignore[arg-type]

        result = list(iter_case_participants(case, dl))
        assert len(result) == 1
        assert result[0].id_ == _P_A
        assert CVDRole.CASE_MANAGER in result[0].roles

    def test_empty_case_yields_nothing(self, dl: SqliteDataLayer) -> None:
        """A case with no participants yields nothing."""
        case = VulnerabilityCase(id_=_CASE_ID)
        assert list(iter_case_participants(case, dl)) == []
