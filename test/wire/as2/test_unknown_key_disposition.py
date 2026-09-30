"""Inbound unknown-key disposition at the parse edge (MV-11, #3900; built under #3921).

One rule, stated once at ``parse_activity`` and holding at every depth: an
unrecognised key that is a *near miss* for a declared spelling (case or
underscore variant, or a retired name) refuses the whole activity naming both
spellings; any other unrecognised key is set aside and reported at INFO, and
the activity proceeds on its declared fields.

Measured on 2026-09-30 the disposition depended on class ancestry instead — a
domain type refused (``extra="forbid"`` on core, ARCH-12-003) while the
envelope, a generic AS2 object, a ``Link`` and an untyped inline dict all
dropped the key silently.  Rows for behaviour not yet built are
``xfail(strict=True)`` so the suite fails the moment the implementation lands
and the marks must come off (SR-05-005).
"""

import logging
from typing import Any

import pytest

from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity

PUBLISHED = "2026-03-04T05:06:07+00:00"
ACTIVITY_ID = "https://example.org/activities/1"
SENDER = "https://example.org/actors/alice"
FOREIGN_KEY = "fooBar"

NOT_BUILT = (
    "MV-11: unknown-key disposition at the parse edge is not built yet. "
    "Tracked by #3921."
)


def _envelope(**extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "Offer",
        "id": ACTIVITY_ID,
        "actor": SENDER,
        "published": PUBLISHED,
        "object": "https://example.org/objects/1",
    }
    body.update(extra)
    return body


def _with_inline_object(inline: dict[str, Any]) -> dict[str, Any]:
    return _envelope(object=inline)


# One row per position MV-11-001 names.  ``path`` is the dotted field path the
# report must carry; ``""`` is the envelope itself.
FOREIGN_KEY_POSITIONS: list[tuple[str, dict[str, Any], str]] = [
    ("envelope", _envelope(**{FOREIGN_KEY: 1}), ""),
    (
        "inline generic AS2 object",
        _with_inline_object({"type": "Note", "content": "hi", FOREIGN_KEY: 1}),
        "object",
    ),
    (
        "inline Link",
        _with_inline_object(
            {"type": "Link", "href": "https://example.org/x", FOREIGN_KEY: 1}
        ),
        "object",
    ),
    (
        "inline untyped dict",
        _with_inline_object({"href": "https://example.org/x", FOREIGN_KEY: 1}),
        "object",
    ),
    (
        "inline domain object",
        _with_inline_object(
            {
                "type": "VulnerabilityCase",
                "id": "https://example.org/cases/1",
                "name": "a case",
                FOREIGN_KEY: 1,
            }
        ),
        "object",
    ),
]

# (label, body, arriving key, declared spelling it resembles).  Note there is
# no underscore row: both roots validate by field name as well as by alias
# (CS-14-001, CS-14-002), so ``attributed_to`` *is* a declared spelling of
# ``attributedTo`` — see ``test_snake_case_field_name_is_declared`` below.
NEAR_MISS_POSITIONS: list[tuple[str, dict[str, Any], str, str]] = [
    ("envelope case variant", _envelope(Actor="dup"), "Actor", "actor"),
    (
        "envelope separator variant",
        _envelope(**{"attributed-to": "z"}),
        "attributed-to",
        "attributedTo",
    ),
    (
        "inline generic AS2 object case variant",
        _with_inline_object({"type": "Note", "Content": "hi"}),
        "Content",
        "content",
    ),
    (
        "inline domain object separator variant",
        _with_inline_object(
            {
                "type": "VulnerabilityCase",
                "id": "https://example.org/cases/1",
                "name": "a case",
                "case-statuses": [],
            }
        ),
        "case-statuses",
        "caseStatuses",
    ),
]


def _info_records_naming(
    caplog: pytest.LogCaptureFixture, key: str
) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.levelno == logging.INFO and key in r.getMessage()
    ]


@pytest.mark.xfail(strict=True, reason=NOT_BUILT)
@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-11-003")
@pytest.mark.parametrize(
    "body,path",
    [(b, p) for _, b, p in FOREIGN_KEY_POSITIONS],
    ids=[label for label, _, _ in FOREIGN_KEY_POSITIONS],
)
def test_foreign_key_is_set_aside_and_reported_once(
    body: dict[str, Any], path: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A foreign key never refuses, never lands on the object, and is logged once."""
    caplog.set_level(logging.INFO)
    activity = parse_activity(body)

    dumped = activity.model_dump(by_alias=True, exclude_none=True)
    assert FOREIGN_KEY not in dumped
    if path:
        inline = dumped[path]
        assert isinstance(inline, dict) and FOREIGN_KEY not in inline

    records = _info_records_naming(caplog, FOREIGN_KEY)
    assert len(records) == 1, [r.getMessage() for r in caplog.records]
    message = records[0].getMessage()
    assert ACTIVITY_ID in message
    assert SENDER in message
    # The path is named in the parser's quoted form (``at 'object'``), never
    # matched as a bare word; the root has no path and is named as the envelope.
    if path:
        assert f"'{path}'" in message
    else:
        assert "envelope" in message


@pytest.mark.xfail(strict=True, reason=NOT_BUILT)
@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-11-002")
@pytest.mark.parametrize(
    "body,arriving,declared",
    [(b, a, d) for _, b, a, d in NEAR_MISS_POSITIONS],
    ids=[label for label, _, _, _ in NEAR_MISS_POSITIONS],
)
def test_near_miss_is_refused_naming_both_spellings(
    body: dict[str, Any], arriving: str, declared: str
) -> None:
    """A case or underscore variant of a declared field refuses the activity."""
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert arriving in message
    assert declared in message


@pytest.mark.spec("MV-11-001")
def test_snake_case_field_name_is_declared(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A field name is a declared spelling, not a near miss (MV-11-001).

    Both roots validate by name (CS-14-001, CS-14-002): ``attributed_to`` fills
    ``attributedTo`` and nothing is refused, set aside, or reported.  Pins the
    definition so an implementation never treats the underscore form as
    unknown.
    """
    caplog.set_level(logging.INFO)
    activity = parse_activity(_envelope(attributed_to="https://example.org/z"))
    assert activity.attributed_to == "https://example.org/z"
    assert not _info_records_naming(caplog, "attributed_to")


@pytest.mark.spec("MV-11-002")
@pytest.mark.parametrize("retired", ["vfd_state", "vfdState"])
def test_retired_name_on_inline_object_is_refused(retired: str) -> None:
    """A retired name is in the list by name, not by normalisation (ADR-0075).

    Holds today through ``ParticipantStatus._reject_retired_vfd_keys`` and must
    keep holding when that core guard is deleted (#3921 AC-4; SDO-03-005,
    MV-11-004) and the wire-side list takes over — so this row is not
    ``xfail``.  Only the naming of the retired key is pinned, not the guard's
    wording: MV-11-002 requires the arriving key and the spelling it resembles,
    and for a retired name those are the same string.
    """
    body = _with_inline_object(
        {
            "type": "ParticipantStatus",
            "id": "https://example.org/status/1",
            "actor": SENDER,
            "context": "https://example.org/cases/1",
            "cvd_role": "VENDOR",
            retired: "VFD",
        }
    )
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    assert retired in str(exc_info.value)


@pytest.mark.spec("MV-11-002")
def test_no_similarity_helper_in_the_parse_edge() -> None:
    """The near-miss test is normalisation plus a list; nothing fuzzier (MV-11-002).

    Scans the whole wire package, not just ``parser.py``: #3921 AC-7 lets the
    partition helper move to a sibling module under ``vultron/wire/as2/``.
    """
    import vultron.wire.as2 as wire_package
    from pathlib import Path

    forbidden = (
        "difflib",
        "get_close_matches",
        "levenshtein",
        "Levenshtein",
        "SequenceMatcher",
        "rapidfuzz",
        "jellyfish",
        "fuzz",
    )
    package_root = Path(wire_package.__file__).parent
    offenders = [
        f"{path.relative_to(package_root)}: {name}"
        for path in sorted(package_root.rglob("*.py"))
        for name in forbidden
        if name in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders
