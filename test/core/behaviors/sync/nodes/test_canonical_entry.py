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

"""Unit tests for ``_validate_canonical_entry`` (CLP-07, CLP-12).

Mirrors ``vultron/core/behaviors/sync/nodes/canonical_entry.py``, which was
split out of ``chain.py`` (BTND-07-002, CS-18-004).  Tests that exercise the
guard *through* ``CreateLogEntryNode`` stay in ``test_chain.py``; these call
the validator directly.
"""

import pytest

from test.core.behaviors.sync.nodes.conftest import (
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    CASE_ID,
)
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _validate_canonical_entry,
)
from vultron.errors import VultronCanonicalEntryError

CASE_ACTOR_ID = "https://example.org/actors/case-actor"


def _note_snapshot_with_actor(actor_id: str) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/note-prov",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


@pytest.mark.spec("CLP-07-012")
def test_validate_canonical_entry_rejects_empty_snapshot():
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=OWNER_ACTOR_ID,
            disposition="recorded",
            payload_snapshot={},
            event_type="note_added",
        )


# ---------------------------------------------------------------------------
# Actor provenance checks (CLP-07-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-07-003")
def test_validate_canonical_entry_rejects_case_actor_as_snapshot_actor_for_non_case_authored():
    """CLP-07-003: non-CaseActor-authored signatures must not have case_actor as actor."""
    with pytest.raises(
        VultronCanonicalEntryError, match="must not be the CaseActor"
    ):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=CASE_ACTOR_ID,
            case_actor_id=CASE_ACTOR_ID,
            disposition="recorded",
            payload_snapshot=_note_snapshot_with_actor(CASE_ACTOR_ID),
            event_type="note_added",
        )


@pytest.mark.spec("CLP-07-003")
def test_validate_canonical_entry_allows_participant_actor_for_non_case_authored():
    """CLP-07-003: participant actor is valid for non-CaseActor-authored signatures."""
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=OWNER_ACTOR_ID,
        case_actor_id=CASE_ACTOR_ID,
        disposition="recorded",
        payload_snapshot=_note_snapshot_with_actor(PARTICIPANT_ACTOR_ID),
        event_type="note_added",
    )


@pytest.mark.spec("CLP-07-003")
def test_validate_canonical_entry_allows_case_actor_for_case_authored_signature():
    """CLP-07-003: CaseActor is the expected actor for Announce(VulnerabilityCase)."""
    snapshot = {
        "type": "Announce",
        "actor": CASE_ACTOR_ID,
        "object": {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=CASE_ACTOR_ID,
        case_actor_id=CASE_ACTOR_ID,
        disposition="recorded",
        payload_snapshot=snapshot,
        event_type="case_announced",
    )


@pytest.mark.spec("CLP-07-003")
def test_validate_canonical_entry_allows_case_actor_for_invite_vulnerability_case():
    """Regression #1526: Invite(VulnerabilityCase) is case-authored; CaseActor must be allowed."""
    participant_actor_id = "https://example.org/actors/participant-1"
    snapshot = {
        "type": "Invite",
        "actor": CASE_ACTOR_ID,
        "object": {
            "type": "Organization",
            "id": participant_actor_id,
        },
        "target": {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=CASE_ACTOR_ID,
        case_actor_id=CASE_ACTOR_ID,
        disposition="recorded",
        payload_snapshot=snapshot,
        event_type="invite_actor_to_case",
    )


def test_validate_canonical_entry_provenance_skipped_when_no_case_actor_id():
    """Provenance check is skipped when case_actor_id is not provided."""
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=OWNER_ACTOR_ID,
        case_actor_id=None,
        disposition="recorded",
        payload_snapshot=_note_snapshot_with_actor(OWNER_ACTOR_ID),
        event_type="note_added",
    )


@pytest.mark.parametrize(
    "event_type,snapshot_type,object_type",
    [
        ("create_case", "Create", "VulnerabilityCase"),
        ("add_report_to_case", "Add", "VulnerabilityReport"),
        ("add_participant_status_to_participant", "Add", "ParticipantStatus"),
    ],
)
@pytest.mark.spec("CLP-07-003")
def test_validate_canonical_entry_allows_case_actor_for_native_init(
    event_type, snapshot_type, object_type
):
    """CLP-12-002: the CaseActor may author its own native-init entries.

    ADR-0041 makes the CaseActor commit the case-initialization entries
    itself (CM-22-003), so these signatures must be in
    ``_CASE_AUTHORED_SIGNATURES``.  Also an fvv regression: when the vendor
    IS the CaseActor the snapshot actor equals ``case_actor_id``, which is
    what triggers the CLP-07-003 provenance check.
    """
    snapshot = {
        "type": snapshot_type,
        "actor": CASE_ACTOR_ID,
        "object": {"type": object_type, "id": "https://example.org/obj/1"},
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        actor_id=CASE_ACTOR_ID,
        case_actor_id=CASE_ACTOR_ID,
        disposition="recorded",
        payload_snapshot=snapshot,
        event_type=event_type,
    )
