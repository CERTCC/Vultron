#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

Covers: ``_extract_recipients`` and ``_format_object`` over the parsed sealed
body, and the ADR-0099 detail 8 check that ``VultronActivity`` declares every
AS2 key a wire activity dumps.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``

Spec coverage:
- OX-08-001/002/003: ``to:`` field enforcement (recipient extraction path).
"""

import pytest
from pydantic import BaseModel

from vultron.adapters.driving.fastapi import outbox_handler as oh

# ---------------------------------------------------------------------------
# _extract_recipients
# ---------------------------------------------------------------------------


def test_extract_recipients_deduplicates():
    """_extract_recipients returns each actor ID at most once."""
    alice = "https://example.org/actors/alice"
    body = {"to": [alice], "cc": [alice]}  # duplicate
    assert oh._extract_recipients(body) == [alice]


def test_extract_recipients_reads_to_field():
    """_extract_recipients reads recipients directly from `to`."""
    alice = "https://example.org/actors/alice"
    bob = "https://example.org/actors/bob"
    assert oh._extract_recipients({"to": [alice, bob]}) == [alice, bob]


def test_extract_recipients_handles_embedded_object():
    """An addressee given as an inline object contributes its ``id``."""
    alice = "https://example.org/actors/alice"
    body = {"to": [{"id": alice, "type": "Person"}]}
    assert oh._extract_recipients(body) == [alice]


def test_extract_recipients_accepts_a_single_string():
    """A scalar ``to`` (not a list) is one recipient."""
    alice = "https://example.org/actors/alice"
    assert oh._extract_recipients({"to": alice}) == [alice]


def test_extract_recipients_returns_empty_for_no_fields():
    """No addressing fields → no recipients."""
    assert oh._extract_recipients({"type": "Offer"}) == []


def test_extract_recipients_skips_unusable_items():
    """Empty strings and objects without an ``id`` name nobody."""
    bob = "https://example.org/actors/bob"
    body = {"to": ["", {"type": "Person"}, bob]}
    assert oh._extract_recipients(body) == [bob]


# ---------------------------------------------------------------------------
# _format_object
# ---------------------------------------------------------------------------


def test_format_object_returns_type_and_id_for_inline_object():
    obj = {"type": "VulnerabilityCase", "id": "urn:uuid:case-1"}
    assert oh._format_object(obj) == "VulnerabilityCase urn:uuid:case-1"


def test_format_object_passes_through_strings():
    assert oh._format_object("urn:uuid:x") == "urn:uuid:x"


def test_format_object_handles_none():
    assert oh._format_object(None) == "None"


def test_format_object_handles_object_without_id():
    assert oh._format_object({"type": "Note"}) == "Note"


# ---------------------------------------------------------------------------
# VultronActivity declares every wire activity key (ADR-0099 detail 8)
# ---------------------------------------------------------------------------


def _accepted_keys(model: type[BaseModel]) -> set[str]:
    """Every input key *model* accepts: field names plus their aliases."""
    from pydantic import AliasChoices

    keys: set[str] = set()
    for name, info in model.model_fields.items():
        keys.add(name)
        for alias in (info.alias, info.validation_alias):
            if isinstance(alias, str):
                keys.add(alias)
            elif isinstance(alias, AliasChoices):
                keys.update(c for c in alias.choices if isinstance(c, str))
    return keys


def _wire_activity_classes() -> list[type[BaseModel]]:
    # The factories import every activity module, filling VOCABULARY.
    import vultron.wire.as2.factories  # noqa: F401
    from vultron.wire.as2.vocab.base.objects.activities.base import (
        as_Activity,
    )
    from vultron.wire.as2.vocab.base.registry import VOCABULARY

    return sorted(
        {cls for cls in VOCABULARY.values() if issubclass(cls, as_Activity)},
        key=lambda cls: cls.__name__,
    )


@pytest.mark.parametrize(
    "wire_cls", _wire_activity_classes(), ids=lambda cls: cls.__name__
)
def test_vultron_activity_accepts_every_wire_activity_key(
    wire_cls: type[BaseModel],
) -> None:
    """Every key a wire activity dumps is a ``VultronActivity`` field.

    ``VultronActivity`` inherits ``extra="forbid"`` from ``CoreObject``, so an
    undeclared AS2 key makes a received activity unstorable as a core
    activity.  ``as_Question``'s ``anyOf``/``oneOf``/``closed`` did exactly
    that to the CBT-03-004 replay Question (ADR-0099 detail 8).
    """
    from vultron.core.models.activity import VultronActivity

    dumped = {
        info.serialization_alias or info.alias or name
        for name, info in wire_cls.model_fields.items()
        if not info.exclude
    }
    missing = dumped - _accepted_keys(VultronActivity)
    assert not missing, (
        f"{wire_cls.__name__} dumps keys VultronActivity forbids: "
        f"{sorted(missing)} — declare them (ADR-0099 detail 8)"
    )
