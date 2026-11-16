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

"""The ``Redacted`` marker type carries only ``type`` and ``summary`` (MV-12).

These rows hold the rule at the type (MV-12-003, MV-12-005).  Where a received
marker may stand is the parse edge's question, held by
``test/wire/as2/test_redaction_marker.py``.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from vultron.core.models.redacted import REDACTED_TYPE, Redacted
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.objects.redacted import Redacted as WireRedacted

REASON = "Embargo pending"


@pytest.mark.spec("MV-12-003")
def test_a_marker_reads_its_type_and_summary_from_the_wire_form() -> None:
    marker = Redacted.model_validate({"type": "Redacted", "summary": REASON})

    assert marker.type_ == REDACTED_TYPE == "Redacted"
    assert marker.summary == REASON


@pytest.mark.spec("MV-12-003")
def test_a_marker_needs_no_summary() -> None:
    marker = Redacted.model_validate({"type": "Redacted"})

    assert marker.summary is None
    assert marker.model_dump(by_alias=True, exclude_none=True) == {
        "type": "Redacted"
    }


@pytest.mark.spec("MV-12-003")
def test_a_marker_dumps_only_its_type_and_summary() -> None:
    marker = Redacted(summary=REASON)

    assert marker.model_dump(by_alias=True) == {
        "type": "Redacted",
        "summary": REASON,
    }


@pytest.mark.spec("MV-12-003")
def test_a_marker_refuses_another_type() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Redacted.model_validate({"type": "Note", "summary": REASON})

    assert {error["loc"] for error in exc_info.value.errors()} == {("type",)}


@pytest.mark.spec("MV-12-003")
def test_a_marker_refuses_an_empty_summary() -> None:
    """``summary`` is optional, but if present it is non-empty (CS-08-002)."""
    with pytest.raises(ValidationError) as exc_info:
        Redacted.model_validate({"type": "Redacted", "summary": ""})

    assert {error["loc"] for error in exc_info.value.errors()} == {
        ("summary",)
    }


@pytest.mark.spec("MV-12-005")
@pytest.mark.spec("MV-12-003")
@pytest.mark.parametrize(
    "extra",
    [
        {"content": "CVE-2026-0001 in widget"},
        {"id": "https://example.org/vuls/1"},
        {"name": "CVE-2026-0001"},
    ],
    ids=["content", "id", "name"],
)
def test_a_marker_carrying_the_withheld_value_is_refused(
    extra: dict[str, Any],
) -> None:
    """A marker with any field but ``type`` and ``summary`` is refused."""
    with pytest.raises(ValidationError) as exc_info:
        Redacted.model_validate(
            {"type": "Redacted", "summary": REASON, **extra}
        )

    assert {error["loc"] for error in exc_info.value.errors()} == {
        tuple(extra)
    }
    assert {error["type"] for error in exc_info.value.errors()} == {
        "extra_forbidden"
    }


@pytest.mark.spec("MV-12-003")
def test_a_marker_cannot_gain_a_field_after_construction() -> None:
    """A marker is a frozen value, so no field is set on it later."""
    marker = Redacted(summary=REASON)

    with pytest.raises(ValidationError):
        marker.summary = "Another reason"  # type: ignore[misc]


def test_the_wire_registry_resolves_redacted_to_the_core_marker() -> None:
    """The core class is the marker's only form (ARCH-25-003)."""
    assert WireRedacted is Redacted
    assert find_in_vocabulary("Redacted") is Redacted
