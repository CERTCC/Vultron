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

"""
Unit tests for outbox handler pure helper functions.

Covers: ``_extract_recipients``, ``_format_object``, ``_dehydrate_references``,
``_is_stub_object_dict``, and ``_coerce_reference_value``.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-08-001/002/003: ``to:`` field enforcement (recipient extraction path).
- MV-10-001: VulnerabilityCase stub preservation.
"""

from types import SimpleNamespace

from vultron.adapters.driving.fastapi import outbox_handler as oh

# ---------------------------------------------------------------------------
# _extract_recipients
# ---------------------------------------------------------------------------


def test_extract_recipients_deduplicates():
    """_extract_recipients returns each actor ID at most once."""
    alice = "https://example.org/actors/alice"
    activity = SimpleNamespace(
        to=[alice],
        cc=[alice],  # duplicate
        bto=None,
        bcc=None,
    )
    recipients = oh._extract_recipients(activity)
    assert recipients == [alice]


def test_extract_recipients_reads_to_field():
    """_extract_recipients reads recipients directly from `to`."""
    alice = "https://example.org/actors/alice"
    bob = "https://example.org/actors/bob"
    activity = SimpleNamespace(
        to=[alice, bob],
        cc=None,
        bto=None,
        bcc=None,
    )

    recipients = oh._extract_recipients(activity)

    assert recipients == [alice, bob]


def test_extract_recipients_handles_embedded_object():
    """_extract_recipients extracts id_ from embedded actor objects."""
    alice_id = "https://example.org/actors/alice"
    alice_obj = SimpleNamespace(id_=alice_id)
    activity = SimpleNamespace(
        to=[alice_obj],
        cc=None,
        bto=None,
        bcc=None,
    )
    recipients = oh._extract_recipients(activity)
    assert recipients == [alice_id]


def test_extract_recipients_returns_empty_for_no_fields():
    """_extract_recipients returns [] when all addressing fields are None."""
    activity = SimpleNamespace(to=None, cc=None, bto=None, bcc=None)
    recipients = oh._extract_recipients(activity)
    assert recipients == []


# ---------------------------------------------------------------------------
# _format_object (D5-7-LOGCLEAN-1)
# ---------------------------------------------------------------------------


def test_format_object_returns_type_and_id_for_domain_object():
    """_format_object produces '<TypeName> <id>' for objects with id_."""
    obj = SimpleNamespace(id_="urn:uuid:abc-123")
    result = oh._format_object(obj)
    assert result == "SimpleNamespace urn:uuid:abc-123"


def test_format_object_passes_through_strings():
    """_format_object returns strings unchanged."""
    uri = "urn:uuid:def-456"
    assert oh._format_object(uri) == uri


def test_format_object_handles_none():
    """_format_object returns 'None' for None."""
    assert oh._format_object(None) == "None"


def test_format_object_handles_object_without_id():
    """_format_object returns just the class name when id_ is absent."""
    obj = SimpleNamespace()  # no id_ attribute
    result = oh._format_object(obj)
    assert result == "SimpleNamespace"


# ---------------------------------------------------------------------------
# _dehydrate_references (DR-01)
# ---------------------------------------------------------------------------


def test_dehydrate_references_preserves_vulnerability_case_stub():
    """_dehydrate_references preserves VulnerabilityCase stub dicts (MV-10-001).

    A minimal {id, type} dict with type=VulnerabilityCase must survive
    dehydration intact so that selective disclosure (stub-based invite.target)
    is not erased before the activity reaches the outbox.
    """
    raw = {
        "type": "Invite",
        "actor": "https://example.org/actors/alice",
        "target": {
            "id": "https://example.org/cases/case-001",
            "type": "VulnerabilityCase",
        },
    }
    result = oh._dehydrate_references(raw)
    assert result["target"] == {
        "id": "https://example.org/cases/case-001",
        "type": "VulnerabilityCase",
    }


def test_dehydrate_references_prefers_href_over_id():
    """_dehydrate_references uses 'href' rather than 'id' for AS2 Link dicts."""
    raw = {
        "actor": "https://example.org/actors/alice",
        "target": {
            "id": "urn:uuid:link-object-id",
            "href": "https://example.org/cases/case-002",
        },
    }
    result = oh._dehydrate_references(raw)
    assert result["target"] == "https://example.org/cases/case-002"


def test_dehydrate_references_handles_list_field():
    """_dehydrate_references collapses actor dicts in list fields element-wise."""
    raw = {
        "to": [
            {"id": "https://example.org/actors/bob", "type": "Person"},
            "https://example.org/actors/charlie",  # already a string
        ]
    }
    result = oh._dehydrate_references(raw)
    assert result["to"] == [
        "https://example.org/actors/bob",
        "https://example.org/actors/charlie",
    ]


def test_dehydrate_references_leaves_object_field_intact():
    """_dehydrate_references does NOT touch the 'object' field (exempt)."""
    inline_obj = {
        "id": "urn:uuid:report-001",
        "type": "VulnerabilityReport",
        "name": "TEST",
    }
    raw = {
        "actor": "https://example.org/actors/alice",
        "object": inline_obj,
    }
    result = oh._dehydrate_references(raw)
    assert result["object"] is inline_obj


def test_dehydrate_references_leaves_string_fields_unchanged():
    """_dehydrate_references does not alter fields that are already strings."""
    raw = {
        "actor": "https://example.org/actors/alice",
        "target": "https://example.org/cases/case-already-string",
    }
    result = oh._dehydrate_references(raw)
    assert result["actor"] == "https://example.org/actors/alice"
    assert result["target"] == "https://example.org/cases/case-already-string"


def test_dehydrate_references_leaves_none_fields_unchanged():
    """_dehydrate_references skips fields that are None."""
    raw = {"actor": "https://example.org/actors/alice", "target": None}
    result = oh._dehydrate_references(raw)
    assert result["target"] is None


# ---------------------------------------------------------------------------
# _is_stub_object_dict and _coerce_reference_value
# ---------------------------------------------------------------------------


def test_is_stub_object_dict_true_for_minimal_case_stub():
    """_is_stub_object_dict identifies the selective-disclosure case stub."""
    stub: dict[object, object] = {
        "id": "https://example.org/cases/case-001",
        "type": "VulnerabilityCase",
    }
    assert oh._is_stub_object_dict(stub) is True


def test_coerce_reference_value_preserves_case_stub_dict():
    """_coerce_reference_value keeps intentional case stubs inline."""
    stub = {
        "id": "https://example.org/cases/case-001",
        "type": "VulnerabilityCase",
    }
    assert oh._coerce_reference_value(stub) == stub


def test_coerce_reference_value_collapses_href_then_id():
    """_coerce_reference_value prefers href over id for dict references."""
    assert (
        oh._coerce_reference_value(
            {"id": "urn:uuid:obj-001", "href": "https://example.org/obj/1"}
        )
        == "https://example.org/obj/1"
    )
    assert (
        oh._coerce_reference_value({"id": "https://example.org/obj/2"})
        == "https://example.org/obj/2"
    )
