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

"""Object labels and registry phrases shared by every ledger reader (DRPT-03).

The labels a measure table shows never put a bare URI or UUID in a cell
(DRPT-03-009), and every phrase comes from ``SEMANTIC_REGISTRY``
(DRPT-03-005, DRPT-03-006).
"""

import dataclasses

import pytest

from vultron.core.models.events.base import MessageSemantics
from vultron.measure.ledger import (
    MISSING_SLOT,
    UNNAMED_ACTOR,
    UNNAMED_OBJECT,
    EntryLabels,
    EntryReferences,
    collect_participant_actors,
    display_label,
    entry_references,
    render_event_phrase,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY, lookup_entry

CASE = "urn:uuid:7699e8c6-b723-4ec7-98ae-00c35f558ecf"
VENDOR = "http://vendor:7999/api/v2/actors/vendor"
UUID_ACTOR = "https://example.org/actors/1e7a421f-b727-4c1d-9a3e-0f6b2c9d8e71"
NAMES = {VENDOR: "Acme Vendor"}


@pytest.mark.parametrize(
    ("ref", "obj_type", "expected"),
    [
        # A display name collected from the payloads wins over everything.
        (VENDOR, "Organization", "Acme Vendor"),
        (VENDOR, None, "Acme Vendor"),
        # The case itself, typed or not.
        (CASE, None, "case"),
        (CASE, "VulnerabilityCase", "case"),
        # A typed non-actor object reads as its type's noun.
        ("urn:uuid:5b0c9d4e-0f6b-4c1d-9a3e-2c9d8e717699", "Note", "note"),
        (None, "VulnerabilityReport", "report"),
        # An unnamed actor falls back to the URI path heuristic ...
        ("http://actor1:7999/api/v2/actors/actor1", "Actor", "Actor1"),
        # ... unless the URI holds no readable word.
        (UUID_ACTOR, "Organization", UNNAMED_ACTOR),
        (
            "urn:uuid:5b0c9d4e-0f6b-4c1d-9a3e-2c9d8e717699",
            None,
            UNNAMED_OBJECT,
        ),
        (None, "Organization", UNNAMED_ACTOR),
        (None, None, None),
    ],
)
@pytest.mark.spec("CEH-01-006")
def test_display_label_never_shows_a_bare_uri(ref, obj_type, expected):
    assert display_label(ref, obj_type, NAMES, case_id=CASE) == expected


def test_a_participant_id_maps_to_the_actor_it_stands_for():
    snapshot = {
        "payloadSnapshot": {
            "type": "Create",
            "object": {
                "type": "VulnerabilityCase",
                "caseParticipants": [
                    {
                        "id": "urn:uuid:p-1",
                        "type": "CaseParticipant",
                        "attributedTo": VENDOR,
                    },
                    {"id": "urn:uuid:p-2", "type": "CaseParticipant"},
                ],
            },
        }
    }
    later = {
        "payloadSnapshot": {
            "object": {
                "id": "urn:uuid:p-1",
                "type": "CaseParticipant",
                "attributedTo": "https://example.org/actors/other",
            }
        }
    }
    assert collect_participant_actors({"a": [snapshot, later]}) == {
        "urn:uuid:p-1": VENDOR
    }


def test_entry_references_unwrap_nested_wrappers_to_the_inner_object():
    payload = {
        "type": "Accept",
        "object": {
            "type": "Invite",
            "object": {"id": VENDOR, "type": "Organization"},
            "target": CASE,
        },
    }
    assert entry_references(payload) == EntryReferences(
        object_ref=VENDOR,
        object_type="Organization",
        target_ref=CASE,
        target_type=None,
    )


def test_entry_references_name_a_participant_by_its_actor():
    payload = {
        "object": {"type": "ParticipantStatus"},
        "target": {
            "id": "urn:uuid:p-1",
            "type": "CaseParticipant",
            "attributedTo": VENDOR,
        },
    }
    refs = entry_references(payload)
    assert (refs.target_ref, refs.target_type) == (VENDOR, "CaseParticipant")
    assert entry_references({}) == EntryReferences()


@pytest.mark.spec("CEH-01-007")
@pytest.mark.spec("DRPT-03-002")
def test_every_registered_phrase_renders_from_its_registry_entry():
    for entry in SEMANTIC_REGISTRY:
        rendered = render_event_phrase(
            entry.semantics.value, "Vendor", "case", "Reporter"
        )
        expected = entry.phrase.format_map(
            {"actor": "Vendor", "object": "case", "target": "Reporter"}
        )
        assert rendered == expected[:1].upper() + expected[1:]


@pytest.mark.spec("DRPT-03-004")
def test_each_slot_reads_what_the_activity_names_in_it():
    """``{target}`` names the invitee, never the case it is invited to."""
    assert render_event_phrase(
        "invite_actor_to_case", "Coordinator", "case", "Vendor"
    ) == ("Coordinator invited Vendor to the case")
    assert render_event_phrase(
        "add_participant_status_to_participant",
        "Case Actor",
        "participant status",
        "Vendor",
    ) == ("Case Actor updated Vendor's participant status")


@pytest.mark.spec("DRPT-03-012")
def test_a_slot_with_no_label_reads_as_a_dash():
    assert render_event_phrase("invite_actor_to_case", "Vendor", "case") == (
        f"Vendor invited {MISSING_SLOT} to the case"
    )


def test_entry_labels_join_the_object_and_its_destination():
    labels = EntryLabels(actor="Vendor", object="note", destination="case")
    assert labels.object_cell == "note → case"
    assert EntryLabels(object="note").object_cell == "note"
    assert EntryLabels(destination="case").object_cell == "case"
    assert EntryLabels().object_cell is None
    assert labels.phrase("add_note_to_case") == render_event_phrase(
        "add_note_to_case", "Vendor", "note", "case"
    )


@pytest.mark.spec("CEH-01-007")
def test_the_phrase_is_read_through_the_registry_lookup(monkeypatch):
    sentinel = dataclasses.replace(
        lookup_entry(MessageSemantics.CREATE_CASE),
        phrase="{actor} sentinel {object}",
    )
    monkeypatch.setattr(
        "vultron.measure.ledger.phrases.lookup_entry", lambda _s: sentinel
    )
    assert render_event_phrase("create_case", "Vendor", "case") == (
        "Vendor sentinel case"
    )


@pytest.mark.spec("CEH-01-007")
@pytest.mark.spec("DRPT-03-006")
def test_an_unknown_semantic_type_reads_as_its_humanized_string():
    assert render_event_phrase("future_thing", "Vendor", "case") == (
        "Future thing"
    )
    assert render_event_phrase("", None, None) == "Performed an action"


@pytest.mark.spec("DRPT-03-012")
def test_a_missing_actor_drops_the_leading_dash():
    rendered = render_event_phrase("create_case", None, "case")
    assert not rendered.startswith(MISSING_SLOT)
    assert "{" not in rendered
