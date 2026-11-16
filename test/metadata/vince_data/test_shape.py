"""Telling a VINCE API response apart from other JSON (VSD-02-001)."""

import json

import pytest

from vultron.metadata.vince_data.generator import SYNTHETIC_CASES
from vultron.metadata.vince_data.shape import (
    UnreadableJson,
    find_vince_shape,
    read_documents,
)

#: The serializer kind each per-case read answers with.
_READ_KINDS = {
    "case": "case",
    "posts": "post",
    "report": "report",
    "vuls": "vul",
    "vendors": "vendor",
    "vendors/vuls": "vendor vul status",
    "note": "note",
}


def _reads() -> list[tuple[str, str, object]]:
    return [
        (stem, read, value)
        for stem, reads in SYNTHETIC_CASES.items()
        for read, value in reads.items()
        if value is not None
    ]


@pytest.mark.spec("VSD-02-001")
@pytest.mark.parametrize(("stem", "read", "value"), _reads())
def test_every_generated_read_is_vince_shaped(
    stem: str, read: str, value: object
) -> None:
    match = find_vince_shape(value)
    assert match is not None, f"{stem} {read} is not recognised"
    assert match.kind == _READ_KINDS[read]


def test_the_generator_covers_every_per_case_read() -> None:
    for reads in SYNTHETIC_CASES.values():
        assert set(reads) == set(_READ_KINDS)


def test_a_report_with_its_contact_withheld_is_still_vince_shaped() -> None:
    report = SYNTHETIC_CASES["999902-inactive-published"]["report"]
    assert "contact_email" not in report
    match = find_vince_shape(report)
    assert match is not None and match.kind == "report"


def test_a_response_nested_deep_in_other_json_is_found() -> None:
    case = SYNTHETIC_CASES["999901-active-embargoed"]["case"]
    match = find_vince_shape({"recorded": [{"body": case}]})
    assert match is not None
    assert match.where == "$.recorded[0].body"


@pytest.mark.parametrize(
    "document",
    [
        {"type": "Note", "content": "x", "attributedTo": "a", "id": "b"},
        {"title": "t", "created": "c", "status": "Active", "summary": "s"},
        [1, "two", None],
        "a string",
    ],
)
def test_other_json_is_not_vince_shaped(document: object) -> None:
    assert find_vince_shape(document) is None


def test_json_with_comments_and_trailing_commas_is_read() -> None:
    text = (
        '{\n  // a comment\n  "a": "keeps // and /* inside */ strings",\n'
        '  /* block */ "b": [1, 2,],\n  "c": "quote \\" stays",\n}\n'
    )
    assert read_documents("tsconfig.json", text) == [
        {
            "a": "keeps // and /* inside */ strings",
            "b": [1, 2],
            "c": 'quote " stays',
        }
    ]


def test_a_line_file_holds_one_document_per_line() -> None:
    text = json.dumps({"a": 1}) + "\n\n" + json.dumps([2]) + "\n"
    assert read_documents("log.jsonl", text) == [{"a": 1}, [2]]


@pytest.mark.parametrize(
    ("name", "text"),
    [("x.json", "{not json"), ("x.jsonl", '{"a": 1}\n{oops\n')],
)
def test_text_that_does_not_parse_is_unreadable(name: str, text: str) -> None:
    with pytest.raises(UnreadableJson):
        read_documents(name, text)
