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

"""What an object slot may hold, and when a whole object must carry its time.

ADR-0198: a slot holds a whole object, a typed reference (exactly ``id`` and
``type``, optionally a ``preview``), or a URI.  A typed reference routes by its
type but is never read as the object (MV-10-011), a ``preview`` is refused for a
type that defines none (MV-10-012), and a received whole object other than an
actor profile or a collection carries ``published`` (CLP-15-011).

Each test feeds raw JSON through ``parse_activity``, the real inbound edge.  The
tests are strict xfails until the implementation Tasks land; each reason names
its Task, so the known-gaps page links it.
"""

from typing import Any

import pytest

from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingPublishedError,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

ACTOR = "https://example.org/actors/alice"
CASE_ID = "https://example.org/cases/c1"
PUBLISHED = "2026-01-02T03:04:05+00:00"

TYPED_REFERENCE_TASK = "#6455"
REQUIRED_PUBLISHED_TASK = "#6456"

#: Types whose ``{id, type}`` form is accepted today as a hollow whole object
#: (#5265), so the parsed object is an instance of the type's class.
REFERENCED_TYPES = ["Note", "Event", "CaseParticipant", "VulnerabilityReport"]


def _body(
    obj: dict[str, Any], activity_type: str = "Remove", **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": activity_type,
        "id": "https://example.org/activities/1",
        "actor": ACTOR,
        "published": PUBLISHED,
        "object": obj,
    }
    body.update(extra)
    return body


@pytest.mark.xfail(
    strict=True,
    reason=f"MV-10-011: a typed reference is read as a hollow whole object."
    f" Tracked by {TYPED_REFERENCE_TASK}.",
)
@pytest.mark.spec("MV-10-011")
@pytest.mark.parametrize("type_", REFERENCED_TYPES)
def test_a_typed_reference_is_not_read_as_the_object(type_: str) -> None:
    """An ``{id, type}`` object names the object; it never becomes one."""
    whole_class = find_in_vocabulary(type_)
    assert whole_class is not None
    reference = {"id": f"https://example.org/objects/{type_}", "type": type_}

    parsed = parse_activity(_body(reference, target=CASE_ID))

    assert isinstance(parsed, as_TransitiveActivity)
    assert not isinstance(parsed.object_, whole_class)


@pytest.mark.xfail(
    strict=True,
    reason=f"MV-10-012: a preview on a typed reference is not refused."
    f" Tracked by {TYPED_REFERENCE_TASK}.",
)
@pytest.mark.spec("MV-10-012")
def test_a_typed_reference_with_an_undefined_preview_is_refused() -> None:
    """No preview is defined for a note, so a note reference carrying one fails."""
    reference = {
        "id": "https://example.org/notes/1",
        "type": "Note",
        # A URI preview: the note class reads ``preview`` as a string, so this
        # is the form that parses today rather than failing for another reason.
        "preview": "https://example.org/notes/1/preview",
    }

    with pytest.raises(VultronParseError):
        parse_activity(_body(reference, target=CASE_ID))


@pytest.mark.xfail(
    strict=True,
    reason=f"CLP-15-011: a received whole object without published is carried."
    f" Tracked by {REQUIRED_PUBLISHED_TASK}.",
)
@pytest.mark.spec("CLP-15-011")
def test_a_whole_object_without_published_is_refused() -> None:
    """A whole note with no ``published`` is malformed, not untimed."""
    note = {
        "id": "https://example.org/notes/1",
        "type": "Note",
        "content": "the vendor confirmed the fix",
        "attributedTo": ACTOR,
    }

    with pytest.raises(VultronParseMissingPublishedError, match="CLP-15-011"):
        parse_activity(_body(note, "Create"))
