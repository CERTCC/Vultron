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

"""Regression tests for ``resolve_case_participant_id_for_actor``.

Covers the divergence-detection contract between ``case_participants``
(canonical source) and ``actor_participant_index`` (derived cache):

- Happy path: both surfaces consistent → canonical ID returned.
- Cache miss: participant in ``case_participants`` but absent from index
  → canonical ID returned (cache-miss is not an error).
- Inline participant object in ``case_participants`` → canonical ID returned.
- Actor absent from both surfaces → None returned.
- Stale index: actor in ``actor_participant_index`` but no matching entry
  in ``case_participants`` → VultronValidationError raised.
- Index divergence: ``case_participants`` and ``actor_participant_index``
  disagree on the participant ID → VultronValidationError raised.
- Duplicate actor in ``case_participants``: two distinct participants share
  the same ``attributed_to`` actor → VultronValidationError raised.

Reference: AGENTS.md § "Case Participant Lookup Must Fail Fast on Surface
Divergence", issue #822, issue #825.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.protocols import CaseModel, is_case_model
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import (
    _resolve_case_manager_id,
    resolve_case_participant_id_for_actor,
)
from vultron.errors import VultronValidationError

_ACTOR_ID = "https://example.org/actors/vendor-001"
_CASE_ID = "https://example.org/cases/case-001"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-001"
_ALT_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-alt"


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture()
def participant() -> CaseParticipant:
    return CaseParticipant(
        id_=_PARTICIPANT_ID,
        attributed_to=_ACTOR_ID,
        context=_CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


@pytest.fixture()
def seeded_case(
    dl: SqliteDataLayer, participant: CaseParticipant
) -> CaseModel:
    """Case with participant stored in DL and registered on both surfaces."""
    dl.create(participant)
    case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
    case.add_participant(participant)
    dl.create(case)
    stored = dl.read(_CASE_ID)
    assert is_case_model(stored), "seeded_case: DL did not return a CaseModel"
    return stored


class TestResolveCaseParticipantIdForActor:
    """Contract tests for resolve_case_participant_id_for_actor."""

    def test_happy_path_returns_canonical_id(
        self, seeded_case: CaseModel, dl: SqliteDataLayer
    ) -> None:
        """Both surfaces consistent: canonical participant ID is returned."""
        result = resolve_case_participant_id_for_actor(
            seeded_case, _ACTOR_ID, dl
        )
        assert result == _PARTICIPANT_ID

    def test_cache_miss_returns_canonical_id(
        self, dl: SqliteDataLayer, participant: CaseParticipant
    ) -> None:
        """Participant in case_participants but absent from index → no error.

        A missing index entry (cache miss) is not a divergence — the canonical
        list has the correct entry so the ID should be resolved without error.
        """
        dl.create(participant)
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Populate only case_participants; omit actor_participant_index entry.
        case.case_participants.append(_PARTICIPANT_ID)
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert is_case_model(stored)
        result = resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)
        assert result == _PARTICIPANT_ID

    def test_inline_participant_object_resolved(
        self, dl: SqliteDataLayer, participant: CaseParticipant
    ) -> None:
        """Inline CaseParticipant object in case_participants is resolved."""
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Store participant inline (not as a string ID) — simulates wire-layer
        # round-trips where objects arrive embedded rather than referenced.
        case.case_participants.append(participant)  # type: ignore[arg-type]
        case.actor_participant_index[_ACTOR_ID] = _PARTICIPANT_ID
        dl.create(participant)
        dl.create(case)

        # Re-read from DL: the DL normalises inline objects to typed records.
        # The case must still resolve via the inline-then-rehydrated path.
        stored = dl.read(_CASE_ID)
        assert is_case_model(stored)
        result = resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)
        assert result == _PARTICIPANT_ID

    def test_not_found_returns_none(
        self, seeded_case: CaseModel, dl: SqliteDataLayer
    ) -> None:
        """Actor not in case at all → None returned without error."""
        unknown_id = "https://example.org/actors/unknown"
        result = resolve_case_participant_id_for_actor(
            seeded_case, unknown_id, dl
        )
        assert result is None

    def test_stale_index_raises(self, dl: SqliteDataLayer) -> None:
        """Actor in actor_participant_index but not in case_participants raises.

        This is the canonical stale-cache divergence: the index claims an entry
        exists but the authoritative list has no matching participant.  Any code
        that only populates the index (without case_participants) is in error.
        """
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Stale index: actor mapped to a participant ID, but case_participants
        # is empty so there is no canonical entry to validate against.
        case.actor_participant_index[_ACTOR_ID] = _PARTICIPANT_ID
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert is_case_model(stored)
        with pytest.raises(
            VultronValidationError, match="actor_participant_index"
        ):
            resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)

    def test_index_divergence_raises(
        self, dl: SqliteDataLayer, participant: CaseParticipant
    ) -> None:
        """Index maps actor to a different ID than case_participants → raises.

        This is the strict divergence case: both surfaces have an entry for the
        same actor, but they disagree on which participant ID is authoritative.
        """
        dl.create(participant)
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Canonical list has the correct participant.
        case.case_participants.append(_PARTICIPANT_ID)
        # Index deliberately maps to a *different* ID.
        case.actor_participant_index[_ACTOR_ID] = _ALT_PARTICIPANT_ID
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert is_case_model(stored)
        with pytest.raises(VultronValidationError, match="divergence"):
            resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)

    def test_duplicate_actor_in_canonical_list_raises(
        self, dl: SqliteDataLayer
    ) -> None:
        """Two distinct participants with the same attributed_to actor → raises.

        The canonical list must be unique per actor; duplicates indicate a
        write-path bug that must surface immediately rather than silently
        choosing one entry.
        """
        p1 = CaseParticipant(
            id_=_PARTICIPANT_ID,
            attributed_to=_ACTOR_ID,
            context=_CASE_ID,
            case_roles=[CVDRole.VENDOR],
        )
        p2 = CaseParticipant(
            id_=_ALT_PARTICIPANT_ID,
            attributed_to=_ACTOR_ID,
            context=_CASE_ID,
            case_roles=[CVDRole.VENDOR],
        )
        dl.create(p1)
        dl.create(p2)
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        case.case_participants.append(_PARTICIPANT_ID)
        case.case_participants.append(_ALT_PARTICIPANT_ID)
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert is_case_model(stored)
        with pytest.raises(
            VultronValidationError, match="multiple participants"
        ):
            resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)


# ---------------------------------------------------------------------------
# Tests for _resolve_case_manager_id (consolidated canonical function)
# ---------------------------------------------------------------------------

_CM_ACTOR_ID = "https://example.org/actors/case-manager-001"
_CM_CASE_ID = "https://example.org/cases/cm-case-001"
_CM_PARTICIPANT_ID = f"{_CM_CASE_ID}/participants/case-manager-001"
_VENDOR_ACTOR_ID = "https://example.org/actors/vendor-002"
_VENDOR_PARTICIPANT_ID = f"{_CM_CASE_ID}/participants/vendor-002"


@pytest.fixture()
def cm_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture()
def cm_participant() -> CaseParticipant:
    return CaseParticipant(
        id_=_CM_PARTICIPANT_ID,
        attributed_to=_CM_ACTOR_ID,
        context=_CM_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture()
def vendor_participant() -> CaseParticipant:
    return CaseParticipant(
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ACTOR_ID,
        context=_CM_CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


class TestResolveCaseManagerId:
    """Contract tests for _resolve_case_manager_id (consolidated helper).

    Verifies that the canonical implementation handles:
    - ID-only participants stored in the DataLayer
    - Inline participant objects (bootstrap path)
    - No CASE_MANAGER participant → None
    - Multiple participants where only one is CASE_MANAGER
    """

    def test_dl_participant_returns_actor_id(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
    ) -> None:
        """ID-only participant stored in DL: returns attributed_to actor ID."""
        cm_dl.create(cm_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="CM Test")
        case.case_participants.append(_CM_PARTICIPANT_ID)
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert is_case_model(stored)
        result = _resolve_case_manager_id(stored, cm_dl)
        assert result == _CM_ACTOR_ID

    def test_inline_participant_returns_actor_id(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
    ) -> None:
        """Inline participant object (bootstrap path): returns attributed_to."""
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="CM Inline Test")
        case.case_participants.append(cm_participant)  # type: ignore[arg-type]
        result = _resolve_case_manager_id(cast(CaseModel, case), cm_dl)
        assert result == _CM_ACTOR_ID

    def test_no_case_manager_returns_none(
        self,
        cm_dl: SqliteDataLayer,
        vendor_participant: CaseParticipant,
    ) -> None:
        """No CASE_MANAGER participant: returns None."""
        cm_dl.create(vendor_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="No CM Test")
        case.case_participants.append(_VENDOR_PARTICIPANT_ID)
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert is_case_model(stored)
        result = _resolve_case_manager_id(stored, cm_dl)
        assert result is None

    def test_empty_case_participants_returns_none(
        self,
        cm_dl: SqliteDataLayer,
    ) -> None:
        """Empty case_participants: returns None."""
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Empty Test")
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert is_case_model(stored)
        result = _resolve_case_manager_id(stored, cm_dl)
        assert result is None

    def test_skips_non_manager_returns_manager(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
        vendor_participant: CaseParticipant,
    ) -> None:
        """Multiple participants: returns CASE_MANAGER actor ID, skips others."""
        cm_dl.create(cm_participant)
        cm_dl.create(vendor_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Multi Test")
        case.case_participants.append(_VENDOR_PARTICIPANT_ID)
        case.case_participants.append(_CM_PARTICIPANT_ID)
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert is_case_model(stored)
        result = _resolve_case_manager_id(stored, cm_dl)
        assert result == _CM_ACTOR_ID

    def test_missing_dl_record_skipped(
        self,
        cm_dl: SqliteDataLayer,
    ) -> None:
        """ID-only reference with no DL record: skipped, returns None."""
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Missing DL Test")
        case.case_participants.append(_CM_PARTICIPANT_ID)  # not in DL
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert is_case_model(stored)
        result = _resolve_case_manager_id(stored, cm_dl)
        assert result is None

    def test_primary_index_path_returns_actor_id(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
    ) -> None:
        """Primary fast-path via actor_participant_index returns actor ID."""
        cm_dl.create(cm_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Index Fast-Path Test")
        case.case_participants.append(_CM_PARTICIPANT_ID)
        case.actor_participant_index[_CM_ACTOR_ID] = _CM_PARTICIPANT_ID
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert is_case_model(stored)
        result = _resolve_case_manager_id(stored, cm_dl)
        assert result == _CM_ACTOR_ID
