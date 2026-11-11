"""Inbound unknown-key disposition at the parse edge (MV-11, #3900, #3921, #3969).

One rule, stated once at ``parse_activity`` and holding at every depth: an
unrecognised key that is a *near miss* for a declared spelling (a case or
underscore variant) refuses the whole activity naming both spellings; any
other unrecognised key is set aside and reported at INFO, and the activity
proceeds on its declared fields.

Measured on 2026-09-30 the disposition depended on class ancestry instead — a
domain type refused (``extra="forbid"`` on core, ARCH-12-003) while the
envelope, a generic AS2 object, a ``Link`` and an untyped inline dict all
dropped the key silently.  The rows were written ``xfail(strict=True)`` ahead
of the build (SR-05-005); #3921 built the partition
(``vultron.wire.as2.unknown_keys``) and took every mark off.
"""

import ast
import importlib
import logging
import pkgutil
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from test.support.act_clock import ACT_AT
from test.support.case_owner import INBOUND_CASE_OWNERSHIP
from test.support.objects import make
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.registry import CORE_TYPE_MAP, CORE_VOCABULARY
from vultron.wire.as2.errors import (
    VultronParseMissingTypeError,
    VultronParseValidationError,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.registry import VOCABULARY, WIRE_TYPE_MAP

PUBLISHED = "2026-03-04T05:06:07+00:00"
ACTIVITY_ID = "https://example.org/activities/1"
SENDER = "https://example.org/actors/alice"
FOREIGN_KEY = "fooBar"
# A case invitation carries its invitee inline, as an actor reference
# (AKM-05-017); only then may its target be a case stub (MV-10-002).
INVITEE = {"type": "Person", "id": "https://example.org/actors/bob"}


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
                **INBOUND_CASE_OWNERSHIP,
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
                **INBOUND_CASE_OWNERSHIP,
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


def _string_constants_under(root: Path, names: Collection[str]) -> list[str]:
    """Every string constant under *root* equal to one of *names*, located."""
    return [
        f"{path.relative_to(root)}:{node.lineno}: {node.value!r}"
        for path in sorted(root.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and node.value in names
    ]


def _info_records_naming(
    caplog: pytest.LogCaptureFixture, key: str
) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.levelno == logging.INFO and key in r.getMessage()
    ]


def _assert_set_aside_and_reported(
    body: dict[str, Any],
    key: str,
    path: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """*key* never refuses, never lands on the object, and is logged once."""
    caplog.set_level(logging.INFO)
    activity = parse_activity(body)

    dumped = activity.model_dump(by_alias=True, exclude_none=True)
    assert key not in dumped
    if path:
        inline = dumped[path]
        assert isinstance(inline, dict) and key not in inline

    records = _info_records_naming(caplog, key)
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


@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-11-003")
@pytest.mark.parametrize(
    "body,path",
    [(b, p) for _, b, p in FOREIGN_KEY_POSITIONS],
    ids=[label for label, _, _ in FOREIGN_KEY_POSITIONS],
)
@pytest.mark.spec("MV-11-006")
def test_foreign_key_is_set_aside_and_reported_once(
    body: dict[str, Any], path: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A foreign key never refuses, never lands on the object, and is logged once."""
    _assert_set_aside_and_reported(body, FOREIGN_KEY, path, caplog)


@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-11-002")
@pytest.mark.parametrize(
    "body,arriving,declared",
    [(b, a, d) for _, b, a, d in NEAR_MISS_POSITIONS],
    ids=[label for label, _, _, _ in NEAR_MISS_POSITIONS],
)
@pytest.mark.spec("MV-11-008")
@pytest.mark.spec("MV-11-006")
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


def _inline_case_status(**extra: Any) -> dict[str, Any]:
    return {
        "type": "CaseStatus",
        "id": "https://example.org/case-status/1",
        "context": "https://example.org/cases/1",
        **extra,
    }


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("SDO-03-003")
@pytest.mark.parametrize(
    "flat,declared,value",
    [("em_state", "emState", "ACTIVE"), ("pxa_state", "pxaState", "PXA")],
)
@pytest.mark.parametrize(
    "build",
    [
        _inline_case_status,
        lambda **extra: _inline_participant_status(
            caseStatus=_inline_case_status(**extra)
        ),
    ],
    ids=["CaseStatus", "ParticipantStatus.caseStatus"],
)
def test_flat_case_status_spelling_is_a_near_miss_of_its_wire_spelling(
    build: Callable[..., dict[str, Any]], flat: str, declared: str, value: str
) -> None:
    """``em_state``/``pxa_state`` are refused as near misses (SDO-03-003, #4376).

    Once ``CaseStatus`` stops declaring the flat snake_case spellings, each
    normalises to its wire spelling (``emState``, ``pxaState``), so the
    near-miss rule refuses it: the field is not retired, only that spelling.
    """
    body = _with_inline_object(build(**{flat: value}))
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert flat in message
    assert declared in message


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("SDO-03-003")
@pytest.mark.parametrize(
    "flat,declared,value",
    [
        ("rm_state", "rmState", "RECEIVED"),
        ("vf_state", "vfState", "Vf"),
        ("d_state", "dState", "D"),
    ],
)
def test_flat_participant_status_spelling_is_a_near_miss_of_its_wire_spelling(
    flat: str, declared: str, value: str
) -> None:
    """``rm_state``/``vf_state``/``d_state`` are refused as near misses (#4377).

    ``ParticipantStatus`` no longer declares the flat snake_case spellings, so
    each normalises to its wire spelling and the near-miss rule refuses it:
    the field is not retired, only that spelling.
    """
    body = _with_inline_object(_inline_participant_status(**{flat: value}))
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert flat in message
    assert declared in message


def _inline_participant_status(**extra: Any) -> dict[str, Any]:
    return {
        "type": "ParticipantStatus",
        "id": "https://example.org/status/1",
        "actor": SENDER,
        "context": "https://example.org/cases/1",
        "cvd_role": "VENDOR",
        **extra,
    }


def _inline_case_participant(**extra: Any) -> dict[str, Any]:
    return {
        "type": "CaseParticipant",
        "id": "https://example.org/participants/1",
        "attributedTo": SENDER,
        "context": "https://example.org/cases/1",
        **extra,
    }


def _inline_ledger_entry(**keys: Any) -> dict[str, Any]:
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    entry = make(
        CaseLedgerEntry,
        case_id="https://example.org/cases/1",
        log_index=0,
        log_object_id="https://example.org/activities/0",
        semantic_type="create_case",
        received_at=ACT_AT,
        published=ACT_AT,
    )
    body = entry.model_dump(by_alias=True, mode="json", exclude_none=True)
    body.update(keys)
    return body


def _inline_case(**extra: Any) -> dict[str, Any]:
    return {
        **INBOUND_CASE_OWNERSHIP,
        "type": "VulnerabilityCase",
        "id": "https://example.org/cases/1",
        "name": "c",
        **extra,
    }


#: (label, body, key) for each name the protocol once read and no longer does.
#: Before 1.0 Vultron supports one protocol version (ADR-0175), so each is an
#: ordinary unknown key: set aside and reported (MV-11-003), never refused.
FORMER_NAME_POSITIONS: list[tuple[str, dict[str, Any], str]] = [
    *(
        (
            f"ParticipantStatus.{key}",
            _with_inline_object(_inline_participant_status(**{key: "VFD"})),
            key,
        )
        for key in ("vfd_state", "vfdState")
    ),
    *(
        (
            f"{build.__name__.removeprefix('_inline_')}.{key}",
            _with_inline_object(build(**{key: value})),
            key,
        )
        for key, value in [
            ("emConsentState", "SIGNATORY"),
            ("em_consent_state", "SIGNATORY"),
            ("embargoAdherence", True),
            ("embargo_adherence", True),
            ("embargoConsentState", "SIGNATORY"),
            ("embargo_consent_state", "SIGNATORY"),
            ("acceptedEmbargoIds", ["https://example.org/embargoes/1"]),
            ("accepted_embargo_ids", ["https://example.org/embargoes/1"]),
        ]
        for build in (_inline_participant_status, _inline_case_participant)
    ),
    *(
        (
            f"VulnerabilityCase.{key}",
            _with_inline_object(_inline_case(**{key: value})),
            key,
        )
        for key, value in [
            ("activeEmbargo", "https://example.org/embargoes/1"),
            ("active_embargo", "https://example.org/embargoes/1"),
            ("proposedEmbargoes", ["https://example.org/embargoes/2"]),
            ("proposed_embargoes", ["https://example.org/embargoes/2"]),
        ]
    ),
    (
        "CaseLedgerEntry.eventType",
        _envelope(
            type="Announce",
            object=_inline_ledger_entry(eventType="create_case"),
        ),
        "eventType",
    ),
    (
        "Note.eventType",
        _with_inline_object(
            {
                "type": "Note",
                "id": "https://example.org/notes/1",
                "content": "hello",
                "eventType": "create_case",
            }
        ),
        "eventType",
    ),
]


@pytest.mark.spec("MV-11-002", "MV-11-003")
@pytest.mark.parametrize(
    "body,key",
    [(b, k) for _, b, k in FORMER_NAME_POSITIONS],
    ids=[label for label, _, _ in FORMER_NAME_POSITIONS],
)
def test_a_former_field_name_is_set_aside_and_reported(
    body: dict[str, Any], key: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A name the protocol no longer reads is an unknown key, not a refusal.

    No list of retired names is kept (ADR-0175): the key is not a near miss
    of any declared spelling, so the parse edge sets it aside and logs it once
    at INFO, and the activity proceeds on its declared fields (MV-11-003).
    """
    _assert_set_aside_and_reported(body, key, "object", caplog)


def test_the_parse_edge_keeps_no_retired_name_list() -> None:
    """The table #5573 removed is gone from ``unknown_keys`` (ADR-0175).

    This checks one removal by its old name only; a list reintroduced under
    another name is caught by
    :func:`test_a_former_field_name_is_set_aside_and_reported`, which fails
    if any former name is refused instead of set aside.
    """
    from vultron.wire.as2 import unknown_keys

    assert not hasattr(unknown_keys, "RETIRED_NAMES")


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("MV-11-009")
def test_no_similarity_helper_in_the_parse_edge() -> None:
    """The near-miss test is normalisation plus a list; nothing fuzzier (MV-11-002).

    Scans the whole wire package, not just ``parser.py``: #3921 AC-7 lets the
    partition helper move to a sibling module under ``vultron/wire/as2/``.
    """
    from pathlib import Path

    import vultron.wire.as2 as wire_package

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


# ---------------------------------------------------------------------------
# Edge cases of the partition beyond the position matrix (#3921)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("EH-07-001")
@pytest.mark.spec("MV-11-008")
def test_every_near_miss_is_named_in_one_refusal() -> None:
    """A refusal names every near miss at every depth, not only the first."""
    body = _envelope(
        Actor="dup",
        object={
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "https://example.org/cases/1",
            "Name": "a case",
            "caseStatuses": [{"type": "CaseStatus", "Context": "x"}],
        },
    )
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    for arriving, declared in (
        ("Actor", "actor"),
        ("Name", "name"),
        ("Context", "context"),
    ):
        assert repr(arriving) in message and repr(declared) in message
    assert "'object.caseStatuses[0]'" in message


@pytest.mark.spec("MV-11-002")
def test_core_near_miss_refusal_is_the_parse_edges_not_pydantics() -> None:
    """A core-class near miss is refused by the partition, not ``forbid`` (AC-8)."""
    body = NEAR_MISS_POSITIONS[-1][1]
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert "MV-11-002" in message
    assert "Extra inputs are not permitted" not in message


@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-11-003")
def test_untyped_dict_in_a_core_slot_is_partitioned_by_the_slot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An untyped dict is judged by the class its parent field validates it into.

    ``VulnerabilityCase.case_statuses`` holds ``CaseStatus``; a foreign key on
    an untyped entry is set aside rather than reaching the core class's
    ``extra="forbid"``, and is reported with its full dotted path.
    """
    caplog.set_level(logging.INFO)
    body = _with_inline_object(
        {
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "https://example.org/cases/1",
            "caseStatuses": [
                {
                    "context": "https://example.org/cases/1",
                    "published": "2026-01-01T00:00:00+00:00",
                    FOREIGN_KEY: 2,
                }
            ],
        }
    )
    activity = parse_activity(body)

    assert isinstance(activity, as_TransitiveActivity)
    case = activity.object_
    assert isinstance(case, VulnerabilityCase)
    status = case.case_statuses[0]
    assert isinstance(status, CaseStatus)
    assert FOREIGN_KEY not in status.model_dump(by_alias=True)
    records = _info_records_naming(caplog, FOREIGN_KEY)
    assert len(records) == 1
    assert "'object.caseStatuses[0]'" in records[0].getMessage()


@pytest.mark.spec("MV-11-003")
@pytest.mark.spec("SL-03-001")
def test_foreign_key_is_reported_at_info_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A set-aside key is a normal protocol event: nothing above INFO (AC-3)."""
    caplog.set_level(logging.DEBUG)
    parse_activity(FOREIGN_KEY_POSITIONS[-1][1])
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.spec("MV-11-003")
@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("MV-11-010")
def test_set_aside_key_survives_only_in_the_received_evidence() -> None:
    """The evidence is the only copy of a set-aside key; the body is untouched."""
    body = _with_inline_object(
        {"type": "Note", "content": "hi", FOREIGN_KEY: 1}
    )
    activity = parse_activity(body)

    assert body["object"][FOREIGN_KEY] == 1
    evidence = activity.received_evidence
    assert evidence is not None
    assert evidence["object"][FOREIGN_KEY] == 1


@pytest.mark.spec("MV-11-001")
def test_opaque_payload_snapshot_is_carried_unexamined() -> None:
    """A ``payloadSnapshot`` is data, not an AS2 object: nothing is set aside."""
    from vultron.wire.as2.unknown_keys import partition_unknown_keys
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Announce,
    )

    snapshot = {"type": "Announce", "Actor": "x", FOREIGN_KEY: 1}
    body = _envelope(
        type="Announce",
        object={"type": "CaseLedgerEntry", "payloadSnapshot": snapshot},
    )
    kept, set_aside = partition_unknown_keys(body, as_Announce)
    assert kept["object"]["payloadSnapshot"] == snapshot
    assert set_aside == []


@pytest.mark.spec("MV-11-002")
@pytest.mark.parametrize(
    "key,expected",
    [
        ("attributedTo", "attributedto"),
        ("attributed-to", "attributedto"),
        ("ATTRIBUTED_TO", "attributedto"),
        ("@context", "context"),
        ("@id", "id"),
        ("@type", "type"),
        ("vf state!", "vfstate"),
    ],
)
def test_normalisation_is_lowercase_and_strip_non_alphanumerics(
    key: str, expected: str
) -> None:
    """Exactly lowercase plus strip non-alphanumerics; nothing fuzzier."""
    from vultron.wire.as2.unknown_keys import normalise

    assert normalise(key) == expected


@pytest.mark.spec("SDO-03-009")
@pytest.mark.spec("MV-11-012")
def test_no_core_module_names_a_retired_key() -> None:
    """No core class carries a by-name guard for a former key (MV-11-012).

    A per-class reject-guard has to spell the former key as a string to test
    for it, as ``ParticipantStatus._reject_retired_vfd_keys`` did; no string
    constant under ``vultron/core/`` may equal one of the former names.
    """
    import vultron.core as core_package

    offenders = _string_constants_under(
        Path(core_package.__file__).parent,
        {key for _, _, key in FORMER_NAME_POSITIONS},
    )
    assert offenders == [], offenders


@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-10-001")
def test_embargoed_invite_stub_is_judged_as_the_stub(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The informed-consent stub keeps its ``caseStatus`` (CM-17-013).

    An embargoed Invite's target stub carries ``activeEmbargo`` and
    ``caseStatus``.  Judged against the full case, which has no ``caseStatus``,
    the key would be set aside and the invitee would lose the embargo state it
    consents on; the stub is selected on its own key set (#2624) even when a
    foreign key rides along, which the partition sets aside.
    """
    from vultron.core.models.dimensions import EmDimension
    from vultron.core.states.em import EM
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCaseStub,
    )

    case_id = "https://example.org/cases/1"
    stub = as_VulnerabilityCaseStub(
        case_id=case_id,
        summary="Security issue — embargo active, details after acceptance",
        active_embargo="https://example.org/embargoes/1",
        case_status=make(
            CaseStatus, context=case_id, em=EmDimension(state=EM.ACTIVE)
        ),
    )
    target = stub.model_dump(by_alias=True, mode="json", exclude_none=True)
    target[FOREIGN_KEY] = 1
    body = _envelope(type="Invite", object=INVITEE, target=target)
    caplog.set_level(logging.INFO)

    activity = parse_activity(body)

    parsed = activity.target
    assert type(parsed) is as_VulnerabilityCaseStub
    assert isinstance(parsed.case_status, CaseStatus)
    assert parsed.case_status.em.state == EM.ACTIVE
    records = _info_records_naming(caplog, FOREIGN_KEY)
    assert len(records) == 1 and "'target'" in records[0].getMessage()
    assert not _info_records_naming(caplog, "caseStatus")


@pytest.mark.spec("MV-11-002")
@pytest.mark.parametrize("misspelled", ["CaseStatus", "case-status"])
def test_near_miss_of_a_stub_key_is_refused(misspelled: str) -> None:
    """A misspelled ``caseStatus`` on a stub refuses; it is not set aside.

    The stub's ``type`` selects the stub (CM-11-013), and the stub's partition
    refuses the near miss naming ``caseStatus`` (MV-11-002) rather than
    setting it aside and losing the embargo state the invitee consents on.
    """
    body = _envelope(
        type="Invite",
        object=INVITEE,
        target={
            "type": "VulnerabilityCaseStub",
            "caseId": "https://example.org/cases/1",
            misspelled: {"type": "CaseStatus", "context": "x"},
        },
    )
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert repr(misspelled) in message and "'caseStatus'" in message


@pytest.mark.spec("MV-10-001")
@pytest.mark.spec("CM-11-038")
@pytest.mark.spec("MV-10-008")
def test_a_sparse_case_carrying_stub_keys_is_still_a_case(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ``VulnerabilityCase`` is a case however few fields it carries.

    Before the stub had its own type, a sparse case carrying ``caseStatus``
    was guessed to be a stub.  The type alone now decides (CM-11-013), so the
    full case's partition judges the key: ``caseStatus`` is no field of the
    case, and it is set aside as foreign.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        VulnerabilityCase,
    )

    body = _envelope(
        type="Invite",
        object="https://example.org/actors/bob",
        target={
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "https://example.org/cases/1",
            "caseStatus": {"type": "CaseStatus", "context": "x"},
        },
    )
    caplog.set_level(logging.INFO)

    activity = parse_activity(body)

    assert type(activity.target) is VulnerabilityCase
    assert _info_records_naming(caplog, "caseStatus")


@pytest.mark.spec("MV-10-001")
@pytest.mark.parametrize(
    "inline",
    [
        {
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "urn:uuid:c1",
        },
        {
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "urn:uuid:c1",
            FOREIGN_KEY: 1,
        },
        {
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "urn:uuid:c1",
            "name": "n",
        },
        {
            **INBOUND_CASE_OWNERSHIP,
            "type": "VulnerabilityCase",
            "id": "urn:uuid:c1",
            "caseStatus": {},
        },
    ],
    ids=["minimal", "minimal-plus-foreign", "full", "stub-only-key"],
)
def test_partition_and_expansion_resolve_the_same_case_class(
    inline: dict[str, Any],
) -> None:
    """The raw dict and its partitioned form resolve to the same class.

    The partition judges the raw dict and the expansion the partitioned one;
    if they disagreed, a key would be judged against a class that does not
    validate it.
    """
    from vultron.wire.as2.unknown_keys import (
        partition_unknown_keys,
        resolve_inline_class,
    )
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Offer,
    )

    kept, _ = partition_unknown_keys(_with_inline_object(inline), as_Offer)
    assert resolve_inline_class(inline) is resolve_inline_class(kept["object"])


@pytest.mark.spec("MV-10-001")
@pytest.mark.parametrize(
    "summary",
    [
        pytest.param(None, id="absent"),
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
    ],
)
@pytest.mark.spec("MV-10-007")
def test_a_stub_without_a_summary_is_refused(summary: str | None) -> None:
    """A receiver refuses a stub whose ``summary`` is absent or blank (MV-10-001).

    The summary is what tells the invitee what it is asked to join; a stub
    without one gives no basis for consent.  Blank/empty values are refused by
    the ``NonEmptyString`` type; an absent value is refused by the inbound
    validator added by #4165.
    """
    target: dict[str, Any] = {
        "type": "VulnerabilityCaseStub",
        "id": "https://example.org/cases/1/stub",
        "caseId": "https://example.org/cases/1",
    }
    if summary is not None:
        target["summary"] = summary
    body = _envelope(type="Invite", object=INVITEE, target=target)
    with pytest.raises(VultronParseValidationError, match="summary"):
        parse_activity(body)


@pytest.mark.spec("MV-02-002")
@pytest.mark.parametrize("depth", [500, 3000])
def test_a_body_nested_too_deeply_is_refused_not_crashed(depth: int) -> None:
    """Nesting past the recursion limit is a schema fault, not a 500.

    ``RecursionError`` is not a ``VultronParseError``, so the inbox adapter's
    handler would not catch it and the sender would get a server error for a
    malformed message.
    """
    inner: dict[str, Any] = {"type": "Note", "content": "leaf"}
    for _ in range(depth):
        inner = {"type": "Note", "inReplyTo": inner}
    with pytest.raises(VultronParseValidationError, match="too deeply"):
        parse_activity(_with_inline_object(inner))


@pytest.mark.spec("MV-10-001")
@pytest.mark.spec("CM-11-038")
@pytest.mark.parametrize(
    ("wire_type", "expected"),
    [
        ("VulnerabilityCaseStub", "as_VulnerabilityCaseStub"),
        ("VulnerabilityCase", "VulnerabilityCase"),
    ],
)
@pytest.mark.parametrize(
    "spelling",
    ["activeEmbargo", "active_embargo", "caseStatus", "case_status"],
)
@pytest.mark.spec("MV-10-008")
def test_the_type_alone_selects_the_stub_or_the_case(
    spelling: str, wire_type: str, expected: str
) -> None:
    """The ``type`` decides the class, whatever keys ride along (CM-11-013).

    No key set turns a ``VulnerabilityCase`` into a stub, and no key set turns
    a ``VulnerabilityCaseStub`` into a case, in either input spelling
    (CS-14-001, CS-14-002).
    """
    from vultron.wire.as2.unknown_keys import resolve_inline_class

    inline = {"type": wire_type, "id": "urn:uuid:c1", spelling: "x"}
    resolved = resolve_inline_class(inline)
    assert resolved is not None and resolved.__name__ == expected


# ---------------------------------------------------------------------------
# JSON-LD keywords `@id` / `@type` are near misses of `id` / `type` (#3969)
# ---------------------------------------------------------------------------
#
# MV-11-002 names this by design: the normative AS2 context aliases the
# keywords and AS2 Core § 2.1 requires the compacted form, so a document
# carrying `@id` or `@type` is legal JSON-LD but not a conforming AS2 document
# (MV-01-001).  The refusal already fires through `normalise()`; these rows
# make it asserted rather than incidental.

JSONLD_KEYWORDS: list[tuple[str, str]] = [("@id", "id"), ("@type", "type")]
# Values that name no class, so neither can steer class resolution.
_KEYWORD_VALUE = {"@id": "https://example.org/objects/2", "@type": "Unrelated"}
_AS2_CONTEXT = "https://www.w3.org/ns/activitystreams"

_NOTE: dict[str, Any] = {"type": "Note", "content": "hi"}
_CASE: dict[str, Any] = {
    **INBOUND_CASE_OWNERSHIP,
    "type": "VulnerabilityCase",
    "id": "https://example.org/cases/1",
    "name": "a case",
}


def _keyword_on_note(**keys: Any) -> dict[str, Any]:
    return _with_inline_object({**_NOTE, **keys})


def _keyword_on_case(**keys: Any) -> dict[str, Any]:
    return _with_inline_object({**_CASE, **keys})


# (label, body builder, location the refusal names).  Every builder keeps
# `type` present: the envelope's class and an inline object's class resolve
# from it, and these rows pin the partition's judgement of a keyword beside a
# resolved class.  The wire-class and core-class rows are AC-2's two branches.
_KEYWORD_POSITIONS: list[tuple[str, Callable[..., dict[str, Any]], str]] = [
    ("envelope", _envelope, "the envelope"),
    ("inline wire-class Note", _keyword_on_note, "'object'"),
    ("inline core-class VulnerabilityCase", _keyword_on_case, "'object'"),
]
_KEYWORD_BUILDER_PARAMS = pytest.mark.parametrize(
    "build",
    [b for _, b, _ in _KEYWORD_POSITIONS],
    ids=[label for label, _, _ in _KEYWORD_POSITIONS],
)
_KEYWORD_POSITION_PARAMS = pytest.mark.parametrize(
    "build,location",
    [(b, loc) for _, b, loc in _KEYWORD_POSITIONS],
    ids=[label for label, _, _ in _KEYWORD_POSITIONS],
)


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("MV-01-001")
@pytest.mark.spec("MV-02-002")
@pytest.mark.parametrize(
    "arriving,declared", JSONLD_KEYWORDS, ids=[k for k, _ in JSONLD_KEYWORDS]
)
@_KEYWORD_POSITION_PARAMS
def test_jsonld_keyword_is_a_near_miss_of_its_as2_spelling(
    build: Callable[..., dict[str, Any]],
    location: str,
    arriving: str,
    declared: str,
) -> None:
    """`@id`/`@type` refuse naming the keyword and `id`/`type` (AC-1, AC-2).

    The refusal is the parse edge's MV-11-002 message on the wire branch and
    the core branch alike, never a Pydantic ``extra="forbid"`` dump.
    """
    body = build(**{arriving: _KEYWORD_VALUE[arriving]})
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert "MV-11-002" in message
    assert (
        f"{arriving!r} at {location} resembles the declared spelling"
        f" {declared!r}"
    ) in message
    assert "Extra inputs are not permitted" not in message


@pytest.mark.spec("MV-11-002")
def test_jsonld_keyword_in_an_untyped_core_slot_is_a_near_miss() -> None:
    """An untyped dict judged by its slot's core class refuses `@type` too."""
    body = _keyword_on_case(
        caseStatuses=[{"@type": "CaseStatus", "context": "x"}]
    )
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    assert (
        "'@type' at 'object.caseStatuses[0]' resembles the declared"
        " spelling 'type'"
    ) in str(exc_info.value)


@pytest.mark.spec("MV-11-001")
@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("EH-07-001")
@_KEYWORD_POSITION_PARAMS
def test_context_beside_jsonld_keywords_is_declared(
    build: Callable[..., dict[str, Any]], location: str
) -> None:
    """`@context` is declared; one refusal names `@id` and `@type` only (AC-3).

    All three keywords sit on the same object.  Every offending key is named
    in the single refusal (EH-07-001), and `@context` — the one JSON-LD
    keyword that is a declared spelling — is not among them.
    """
    body = build(**{"@context": _AS2_CONTEXT, **_KEYWORD_VALUE})
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)
    message = str(exc_info.value)
    assert f"'@id' at {location}" in message
    assert f"'@type' at {location}" in message
    assert "'@context'" not in message
    assert message.count("resembles the declared spelling") == 2


@pytest.mark.spec("MV-11-001")
@_KEYWORD_BUILDER_PARAMS
def test_context_alone_is_accepted(
    build: Callable[..., dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`@context` alone refuses nothing and is not set aside, at any position."""
    caplog.set_level(logging.INFO)
    parse_activity(build(**{"@context": _AS2_CONTEXT}))
    assert not _info_records_naming(caplog, "@context")


@pytest.mark.spec("MV-02-002")
def test_envelope_with_only_at_type_is_refused_as_missing_type() -> None:
    """With `@type` in place of `type`, no envelope class resolves at all.

    The missing-type refusal fires before the partition has a class to judge
    `@type` against, so the sender hears "missing type" rather than the
    near-miss message.  This is the missing-type refusal (HTTP 400), outside
    MV-11-002, which judges keys against a *resolved* class; pinned only so
    such an activity is never accepted.
    """
    body = _envelope(**{"@type": "Offer"})
    del body["type"]
    with pytest.raises(VultronParseMissingTypeError):
        parse_activity(body)


def _raise_on_import_error(name: str) -> None:
    """``walk_packages`` error hook: a failed subpackage import is a failure."""
    raise ImportError(f"could not import {name} while filling registries")


def _registered_classes() -> list[type[BaseModel]]:
    """Every class a wire or core registry holds, after importing all of it.

    A class registers when its module is imported, so reading the registries
    as they stand covers only what earlier tests happened to import.  Walking
    every ``vultron`` module first makes the ratchet order-independent.
    """
    import vultron

    for info in pkgutil.walk_packages(
        vultron.__path__, "vultron.", onerror=_raise_on_import_error
    ):
        importlib.import_module(info.name)
    found = {
        *VOCABULARY.values(),
        *WIRE_TYPE_MAP.values(),
        *CORE_VOCABULARY.values(),
        *CORE_TYPE_MAP.values(),
    }
    return sorted(
        found, key=lambda cls: f"{cls.__module__}.{cls.__qualname__}"
    )


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("MV-11-007")
def test_no_class_declares_a_jsonld_keyword_as_a_spelling() -> None:
    """No wire or core class accepts `@id`/`@type` on input (AC-4).

    MV-11-002: a receiver MUST NOT declare them as an alias.  Checked on the
    spellings the partition itself derives, so an alias added through
    ``validation_alias``, ``AliasChoices`` or an ``alias_generator`` is caught.
    The private ``_class_spellings`` is read on purpose: it is the partition's
    own definition of "declared", and a public restatement could drift from it.
    """
    from vultron.wire.as2.unknown_keys import _class_spellings

    keywords = {k for k, _ in JSONLD_KEYWORDS}
    classes = _registered_classes()
    names = {cls.__qualname__ for cls in classes}
    # One class from each root and each layer that registers: if these are
    # missing, the walk did not fill the registries and the check is vacuous.
    assert {
        "as_Note",
        "VulnerabilityCase",
        "CaseStatus",
        "OutboxDeadLetterEntry",
    } <= names, sorted(names)
    offenders = [
        f"{cls.__module__}.{cls.__qualname__}: {sorted(found)}"
        for cls in classes
        if (found := keywords & _class_spellings(cls).annotations.keys())
    ]
    assert offenders == [], offenders


@pytest.mark.spec("MV-11-002")
@pytest.mark.spec("MV-11-007")
def test_no_exemption_names_a_jsonld_keyword() -> None:
    """`@id`/`@type` sit in no exemption set, and no source spells them (AC-4).

    The set checks cover the partition's own exemptions; the source scan
    (every string constant under ``vultron/`` that *equals* ``"@id"`` or
    ``"@type"``) catches a new alias or exemption before it reaches a registry.
    It does not see a keyword assembled at run time; the registry ratchet
    above covers that case for every declared spelling.  The scan is deliberately
    package-wide: AS2 compacts both keywords away (MV-11-002), so no Vultron
    module has a reason to spell them, and one that does needs a reviewer.
    """
    import vultron
    from vultron.wire.as2 import unknown_keys

    keywords = {k for k, _ in JSONLD_KEYWORDS}
    exemptions: dict[str, frozenset[str]] = {
        "_UNEXAMINED_KEYS": unknown_keys._UNEXAMINED_KEYS,
        "OPAQUE_PAYLOAD_KEYS": unknown_keys.OPAQUE_PAYLOAD_KEYS,
    }
    assert {
        name: sorted(keywords & keys)
        for name, keys in exemptions.items()
        if keywords & keys
    } == {}

    offenders = _string_constants_under(
        Path(vultron.__file__).parent, keywords
    )
    assert offenders == [], (
        "MV-11-002: @id/@type are near misses of id/type by design and MUST "
        f"NOT be declared or exempted; found {offenders}"
    )
