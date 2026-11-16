"""The sanitizer of a VINCE case (#6348, VSD-02-005 to VSD-02-008).

Each test treats its source case as sensitive. The sources are the
generator's synthetic cases (:data:`SYNTHETIC_CASES`), written to a path
outside the repository checkout; nothing here is read from a VINCE instance.
"""

import copy
import json
import logging
import re
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from vultron.metadata.vince_data import check as check_module
from vultron.metadata.vince_data.check import check, file_faults, generate
from vultron.metadata.vince_data.generator import (
    SYNTHETIC_CASES,
    generated_fixtures,
)
from vultron.metadata.vince_data.marker import (
    CLEARED_CASES_PATH,
    FIXTURE_DIR,
    SANITIZER,
    marker_for,
)
from vultron.metadata.vince_data.sanitizer import (
    ENUMERATED_VALUES,
    READS,
    SanitizeError,
    UnclassifiedField,
    sanitize,
    sanitize_file,
    sanitized_path,
    transform,
    verify_sanitized,
)

_SOURCES = ("999901-active-embargoed", "999902-inactive-published")

#: An edit of a parsed JSON source in place; JSON is untyped, hence ``Any``.
Edit = Callable[[Any], object]
#: An edit of a written file's text.
TextEdit = Callable[[str], str]
_VUID = "998001"

#: The values the VINCE API itself defines (``vinny/models.py``:
#: ``Case.STATUS_CHOICES``, ``CaseMemberStatus.STATUS_CHOICES``,
#: ``Post.get_org_name``; ``vinny/serializers.py``:
#: ``PostSerializer.get_author``), written out here so the sanitizer's own
#: list is checked, not trusted.
_VINCE_ENUMERATED = frozenset(
    {
        "Active",
        "Inactive",
        "Affected",
        "Not Affected",
        "Unknown",
        "Coordinator",
        "Reporter",
        "VINCE User",
        "(Removed from case)",
        "Removed",
        "User removed",
        "unknown@example.com",
    }
)

_LOREM_WORD = re.compile(
    r"(?:lorem|ipsum|dolor|sit|amet|consectetur|adipiscing|elit|sed|do|"
    r"eiusmod|tempor|incididunt|ut|labore|et|dolore|magna|aliqua|enim|ad|"
    r"minim|veniam|quis|nostrud|exercitation|ullamco|laboris|nisi|aliquip|"
    r"ex|ea|commodo|consequat|duis|aute|irure|in|reprehenderit|voluptate|"
    r"velit|esse|cillum|fugiat|nulla|pariatur|excepteur|sint|occaecat|"
    r"cupidatat|non|proident|sunt|culpa|qui|officia|deserunt|mollit|anim|"
    r"id|est|laborum)"
)

_TEXT_FIELDS = {
    "summary",
    "title",
    "content",
    "product_name",
    "product_version",
    "vul_description",
    "vul_exploit",
    "vul_impact",
    "vul_discovery",
    "public_references",
    "exploit_references",
    "disclosure_plans",
    "description",
    "statement",
    "references",
    "cert_addendum",
}


# Factories (TB-05-002) --------------------------------------------------


def _reads(stem: str = _SOURCES[0]) -> dict[str, object]:
    return copy.deepcopy(dict(SYNTHETIC_CASES[stem]))


def _source(stem: str = _SOURCES[0]) -> dict[str, object]:
    return {"reads": _reads(stem)}


def _note(**fields: object) -> dict[str, object]:
    """The published note of the generator's case 999902, with *fields*,
    under case 999901's id."""
    note = dict(_reads(_SOURCES[1])["note"])  # type: ignore[call-overload]
    return {**note, "vuid": "999901", **fields}


def _outside(tmp_path: Path, document: object) -> Path:
    """Write *document* where a source case belongs: outside the checkout."""
    source = tmp_path / "outside" / "case.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(document), encoding="utf-8")
    return source


def _checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    generate(root)
    (root / CLEARED_CASES_PATH).write_text("cleared: []\n", encoding="utf-8")
    return root


def _sanitized(stem: str = _SOURCES[0]) -> dict[str, object]:
    document = json.loads(sanitize(_source(stem), _VUID))
    assert document["synthetic"] == {"producer": SANITIZER}
    reads: dict[str, object] = document["reads"]
    return reads


def _leaves(value: object, where: str = "") -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f"{where}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _leaves(child, f"{where}[{i}]")
    else:
        yield where, value


def _times(reads: object) -> list[datetime]:
    names = (
        "created",
        "modified",
        "due_date",
        "date_submitted",
        "date_added",
        "statement_date",
        "datefirstpublished",
        "dateupdated",
    )
    return [
        datetime.fromisoformat(value)
        for where, value in _leaves(reads)
        if isinstance(value, str) and where.rsplit(".", 1)[-1] in names
    ]


def _sensitive(reads: object) -> set[str | int]:
    """Every value of the source a leak would show: every string but an
    enumerated or blank one, and every id, string and numeric."""
    found: set[str | int] = set()
    for where, value in _leaves(reads):
        if (
            isinstance(value, str)
            and value.strip()
            and value not in _VINCE_ENUMERATED
        ):
            found.add(value)
        if where.endswith((".vuid", ".pk")):
            found |= {str(value), int(value)}  # type: ignore[call-overload]
    return found | (_keys(reads) - _keys(dict(SYNTHETIC_CASES)))


def _keys(value: object) -> set[str | int]:
    """Every object key in *value*: a key may carry content too."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


# AC-1: the same shape -----------------------------------------------------


@pytest.mark.parametrize("stem", _SOURCES)
def test_the_sanitized_case_keeps_the_source_shape(stem: str) -> None:
    source, out = _reads(stem), _sanitized(stem)
    assert out.keys() == source.keys()
    assert out["case"]["status"] == source["case"]["status"]  # type: ignore[index]
    for read in ("posts", "vuls", "vendors", "vendors/vuls"):
        assert len(out[read]) == len(source[read])  # type: ignore[arg-type]
    assert [p["pinned"] for p in out["posts"]] == [  # type: ignore[attr-defined]
        p["pinned"]
        for p in source["posts"]  # type: ignore[attr-defined]
    ]
    for read in ("vendors", "vendors/vuls"):
        assert [v["status"] for v in out[read]] == [  # type: ignore[attr-defined]
            v["status"]
            for v in source[read]  # type: ignore[attr-defined]
        ]
    assert (out["note"] is None) == (source["note"] is None)
    assert out["report"].keys() == source["report"].keys()  # type: ignore[attr-defined]


@pytest.mark.parametrize("stem", _SOURCES)
def test_the_participants_and_their_roles_are_kept(stem: str) -> None:
    source, out = _reads(stem), _sanitized(stem)

    def roles(reads: dict[str, object]) -> list[tuple[str, ...]]:
        vendors = [v["vendor"] for v in reads["vendors"]]  # type: ignore[attr-defined]
        report = reads["report"]
        reporter = report.get("contact_org")  # type: ignore[attr-defined]
        posts = [p["author"]["org"] for p in reads["posts"]]  # type: ignore[attr-defined]
        named = {name: i for i, name in enumerate(dict.fromkeys(vendors))}
        return [
            tuple("vendor" if o in named else "other" for o in posts),
            tuple("vendor" if reporter in named else str(bool(reporter))),
            tuple(str(named[v["vendor"]]) for v in reads["vendors/vuls"]),  # type: ignore[attr-defined]
        ]

    assert roles(out) == roles(source)


@pytest.mark.parametrize("stem", _SOURCES)
def test_timestamps_keep_their_order_and_spacing(stem: str) -> None:
    before, after = _times(_reads(stem)), _times(_sanitized(stem))
    assert len(after) == len(before) > 1
    offsets = {b - a for a, b in zip(before, after, strict=True)}
    assert len(offsets) == 1
    assert offsets.pop().days > 0


# AC-2: every value replaced, ids consistent, unclassified fields refused --


@pytest.mark.spec("VSD-02-006")
@pytest.mark.parametrize("stem", _SOURCES)
def test_free_text_is_lorem_and_names_are_fakes(stem: str) -> None:
    checked: set[str] = set()
    for where, value in _leaves(_sanitized(stem)):
        field = re.sub(r"\[\d+\]$", "", where.rsplit(".", 1)[-1])
        if not isinstance(value, str) or not value:
            continue
        if field in _TEXT_FIELDS:
            words = value.rstrip(".").lower().split()
            assert all(_LOREM_WORD.fullmatch(w) for w in words), where
        elif field in {"org", "vendor", "vendor_name", "contact_org"}:
            assert re.fullmatch(r"Example Org \w+", value), where
        elif field in {"name", "contact_name"} and "vuls" not in where:
            assert re.fullmatch(r"Example Person \w+", value), where
        elif field in {"email", "contact_email"}:
            assert re.fullmatch(r"person-\d+@example\.com", value), where
        elif field == "contact_phone":
            assert re.fullmatch(r"\+1-555-0199 x\d+", value), where
        elif field == "cve":
            assert re.fullmatch(r"CVE-2098-\d{4}", value), where
        checked.add(field)
    assert {"contact_name", "contact_phone", "cve", "content"} & checked


@pytest.mark.spec("VSD-02-008")
def test_ids_are_synthetic_and_consistent_across_the_case() -> None:
    source, out = _reads(), _sanitized()
    assert out["case"]["vuid"] == _VUID  # type: ignore[index]
    assert out["case"]["pk"] != source["case"]["pk"]  # type: ignore[index]

    def links(reads: dict[str, object]) -> list[int]:
        names = [v["name"] for v in reads["vuls"]]  # type: ignore[attr-defined]
        return [
            names.index(s["vulnerability"])
            for s in reads["vendors/vuls"]  # type: ignore[attr-defined]
        ]

    assert links(out) == links(source)
    for vul in out["vuls"]:  # type: ignore[attr-defined]
        assert vul["name"].startswith(f"VU#{_VUID}.")
        assert vul["cve"] is None or vul["cve"].startswith("CVE-2098-")


@pytest.mark.spec("VSD-02-007")
@pytest.mark.parametrize(
    ("place", "named"),
    [
        (lambda r: r["case"], "reads.case.leaked_field"),
        (
            lambda r: r["posts"][1]["author"],
            "reads.posts[1].author.leaked_field",
        ),
        (lambda r: r["report"], "reads.report.leaked_field"),
        (lambda r: r["vendors/vuls"][0], "reads.vendors/vuls[0].leaked_field"),
        (lambda r: r, "reads.leaked_field"),
    ],
)
def test_an_unclassified_field_is_refused_by_name(
    place: Callable[[Any], Any], named: str
) -> None:
    source = _source()
    place(source["reads"])["leaked_field"] = "Sensitive Detail 4242"
    with pytest.raises(UnclassifiedField) as raised:
        sanitize(source, _VUID)
    assert raised.value.field == named
    assert named in str(raised.value)
    assert "Sensitive Detail 4242" not in str(raised.value)


@pytest.mark.spec("VSD-02-007")
def test_an_unclassified_top_level_key_is_refused() -> None:
    with pytest.raises(UnclassifiedField, match="recorded_at"):
        sanitize({**_source(), "recorded_at": "x"}, _VUID)


def test_every_serializer_field_is_classified() -> None:
    for stem in _SOURCES:
        transform(_reads(stem), _VUID)
    assert set(READS) == set(next(iter(SYNTHETIC_CASES.values())))


def test_the_kept_values_are_the_ones_vince_defines() -> None:
    assert ENUMERATED_VALUES == _VINCE_ENUMERATED


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda r: r["case"].update(status="Pending"), "not a status"),
        (lambda r: r["vendors"][0].update(status="Fixed"), "not a status"),
        (lambda r: r["case"].update(created="Secret Day"), "ISO 8601"),
        (lambda r: r["case"].update(created="2026-13-45T00:00Z"), "ISO 8601"),
        (lambda r: r["case"].update(pk="Secret Pk"), "integer id"),
        (lambda r: r["posts"][0].update(pinned="Secret Flag"), "boolean"),
        (lambda r: r["case"].update(title=["Secret Title"]), "a string"),
        (lambda r: r.update(posts={"Secret": 1}), "a list"),
        (lambda r: r.pop("note"), "read is missing"),
        (lambda r: r["case"].update(vuid=998001), "a string"),
        (lambda r: r.update(note=_note(revision=True)), "an integer"),
        (lambda r: r.update(case=["Secret Case"]), "an object"),
        (lambda r: r.update(report=["Secret Report"]), "an object"),
        (lambda r: r["vendors"].append("Secret Vendor"), "an object"),
        (lambda r: r.update(note=_note(revision="Secret 7")), "an integer"),
        (
            lambda r: r.update(note=_note(revision=4155551234)),
            "a count outside",
        ),
        (lambda r: r.update(note=_note(references="Secret Ref")), "list of"),
        (lambda r: r.update(note=_note(references=[7])), "a string"),
        (
            lambda r: r["case"].update(
                created="0001-01-01T00:00:00Z", modified="9999-12-30T00:00:00Z"
            ),
            "span too many years",
        ),
        (lambda r: r.update(case=None), "case read is missing"),
    ],
)
def test_a_value_of_the_wrong_kind_is_refused_without_its_value(
    edit: Edit, message: str
) -> None:
    source = _source()
    edit(source["reads"])
    with pytest.raises(SanitizeError, match=message) as raised:
        sanitize(source, _VUID)
    assert "Secret" not in str(raised.value)
    assert "Pending" not in str(raised.value)
    assert "4155551234" not in str(raised.value)


def test_a_case_with_a_status_vince_does_not_define_is_refused() -> None:
    with pytest.raises(SanitizeError, match=r"reads\.case\.status"):
        sanitize(_source("999903-unknown-values"), _VUID)


@pytest.mark.parametrize(
    "vuid",
    [
        "999901",
        "12",
        "abc",
        "999000",
        "0998001",
        "\u0669\u0669\u0668\u0660\u0660\u0661",
    ],
)
def test_a_case_id_outside_the_sanitizer_range_is_refused(vuid: str) -> None:
    with pytest.raises(SanitizeError, match="sanitized case id"):
        sanitize(_source(), vuid)


@pytest.mark.spec("VSD-02-006")
def test_an_output_repeating_a_source_value_is_refused() -> None:
    source = _source()
    posts = source["reads"]["posts"]  # type: ignore[index]
    posts[1]["author"]["org"] = "Example Org Alpha"
    with pytest.raises(SanitizeError, match="repeats a value of the source"):
        sanitize(source, _VUID)


def test_the_api_labels_of_a_post_author_are_kept() -> None:
    source = _source()
    posts = source["reads"]["posts"]  # type: ignore[index]
    posts[0]["author"] = {
        "org": "Coordinator",
        "active": False,
        "name": "User removed",
        "email": "unknown@example.com",
    }
    posts[1]["author"]["org"] = "Synthetic Vendor Alpha (Inactive User)"
    out = json.loads(sanitize(source, _VUID))["reads"]
    assert out["posts"][0]["author"] == posts[0]["author"]
    vendor = out["vendors"][0]["vendor"]
    assert out["posts"][1]["author"]["org"] == f"{vendor} (Inactive User)"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (["Secret"], "a per-case bundle object"),
        ({"synthetic": {"producer": "generator"}}, "has no reads"),
        ({"reads": ["Secret"]}, "expected an object"),
    ],
)
def test_a_source_that_is_not_a_bundle_is_refused(
    source: object, message: str
) -> None:
    with pytest.raises(SanitizeError, match=message) as raised:
        sanitize(source, _VUID)
    assert "Secret" not in str(raised.value)


def test_blank_names_contacts_and_text_become_empty() -> None:
    source = _source()
    report = source["reads"]["report"]  # type: ignore[index]
    report |= {"contact_name": "  ", "contact_phone": "\t", "vul_impact": " "}
    out = json.loads(sanitize(source, _VUID))["reads"]["report"]
    assert (out["contact_name"], out["contact_phone"], out["vul_impact"]) == (
        "",
        "",
        "",
    )


def test_timestamps_are_written_in_utc_to_the_second() -> None:
    source = _source()
    case = source["reads"]["case"]  # type: ignore[index]
    case["modified"] = "2026-02-10T04:30:00.123456-05:00"
    case["due_date"] = "2026-04-06"
    out = json.loads(sanitize(source, _VUID))["reads"]["case"]
    assert out["modified"] == "2090-02-09T09:30:00Z"
    assert out["due_date"] == "2090-04-05"
    assert (
        verify_sanitized(sanitized_path(_VUID), sanitize(source, _VUID))
        is None
    )


@pytest.mark.spec("VSD-02-007")
def test_a_key_shaped_like_content_is_named_by_position() -> None:
    source = _source()
    source["reads"]["case"]["alice@realvendor.example"] = 1  # type: ignore[index]
    with pytest.raises(UnclassifiedField) as raised:
        sanitize(source, _VUID)
    assert raised.value.field == "reads.case.<key 9>"
    assert "alice" not in str(raised.value)


# AC-3: the leak test ------------------------------------------------------


class _Everything(logging.Handler):
    """Every record at every level, formatted with its traceback."""

    def __init__(self) -> None:
        super().__init__(logging.NOTSET)
        self.setFormatter(logging.Formatter("%(name)s %(message)s"))
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def every_log(
    caplog: pytest.LogCaptureFixture,
) -> Iterator[tuple[pytest.LogCaptureFixture, _Everything]]:
    caplog.set_level(logging.DEBUG)
    handler = _Everything()
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield caplog, handler
    finally:
        root.removeHandler(handler)


def _appears(value: str | int, text: str) -> bool:
    token = re.escape(str(value))
    return re.search(rf"(?<![\w.]){token}(?![\w])", text) is not None


@pytest.mark.spec("VSD-02-006")
@pytest.mark.spec("VSD-02-008")
@pytest.mark.spec("VSD-01-003")
@pytest.mark.parametrize("stem", _SOURCES)
def test_no_source_value_reaches_the_output_or_any_log(
    stem: str,
    tmp_path: Path,
    every_log: tuple[pytest.LogCaptureFixture, _Everything],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog, handler = every_log
    root = _checkout(tmp_path)
    source = _outside(tmp_path, _source(stem))
    monkeypatch.setattr(check_module, "repo_root", lambda: root)
    assert check_module.main(["sanitize", str(source), "--vuid", _VUID]) == 0
    text = (root / sanitized_path(_VUID)).read_text(encoding="utf-8")
    logs = "\n".join([caplog.text, *handler.lines, *capsys.readouterr()])
    sensitive = _sensitive(_reads(stem))
    assert sensitive
    for _, value in _leaves(json.loads(text)):
        if not isinstance(value, bool):
            assert value not in sensitive
    for value in sensitive:
        assert not _appears(value, text), value
        assert not _appears(value, logs), value
    # Not vacuous: the run logged, at both levels, under the synthetic id.
    levels = {r.levelno for r in caplog.records}
    assert {logging.DEBUG, logging.INFO} <= levels
    assert all(_VUID in r.getMessage() for r in caplog.records)


@pytest.mark.spec("VSD-01-003")
@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r["case"].update(leaked_field="Sensitive Detail 4242"),
        lambda r: r["case"].update(created="Sensitive Detail 4242"),
        lambda r: r["vendors"][0].update(status="Sensitive Detail 4242"),
        lambda r: r["case"].update({"Sensitive Detail 4242": 1}),
    ],
)
def test_a_refused_run_leaks_no_source_value(
    edit: Edit,
    tmp_path: Path,
    every_log: tuple[pytest.LogCaptureFixture, _Everything],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog, handler = every_log
    root = _checkout(tmp_path)
    document = _source()
    edit(document["reads"])
    source = _outside(tmp_path, document)
    monkeypatch.setattr(check_module, "repo_root", lambda: root)
    assert check_module.main(["sanitize", str(source), "--vuid", _VUID]) == 1
    out, err = capsys.readouterr()
    assert "vince-data:" in err
    logs = "\n".join([caplog.text, *handler.lines, out, err])
    for value in _sensitive(document["reads"]):
        assert not _appears(value, logs), value
    assert not (root / sanitized_path(_VUID)).exists()


# AC-4: read from outside the checkout, accepted by the check ------------


def test_a_source_inside_the_checkout_is_refused(tmp_path: Path) -> None:
    root = _checkout(tmp_path)
    inside = root / "case.json"
    inside.write_text(json.dumps(_source()), encoding="utf-8")
    with pytest.raises(SanitizeError, match="inside the repository"):
        sanitize_file(inside, root, _VUID)
    assert not (root / sanitized_path(_VUID)).exists()


def test_a_source_in_another_git_checkout_is_refused(tmp_path: Path) -> None:
    other = tmp_path / "other-worktree"
    (other / "cases").mkdir(parents=True)
    (other / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    source = other / "cases" / "case.json"
    source.write_text(json.dumps(_source()), encoding="utf-8")
    with pytest.raises(SanitizeError, match="another git checkout"):
        sanitize_file(source, _checkout(tmp_path), _VUID)


@pytest.mark.parametrize(
    ("content", "reason"),
    [(None, "FileNotFoundError"), (b"\xff\xfe{", "UnicodeDecodeError")],
)
def test_a_source_that_cannot_be_read_is_refused(
    tmp_path: Path, content: bytes | None, reason: str
) -> None:
    source = tmp_path / "outside.json"
    if content is not None:
        source.write_bytes(content)
    with pytest.raises(SanitizeError, match=reason):
        sanitize_file(source, _checkout(tmp_path), _VUID)


def test_a_source_that_is_not_json_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "outside.json"
    source.write_text("{Sensitive Detail", encoding="utf-8")
    with pytest.raises(SanitizeError, match="JSONDecodeError") as raised:
        sanitize_file(source, _checkout(tmp_path), _VUID)
    assert "Sensitive" not in str(raised.value)


@pytest.mark.spec("VSD-02-005")
@pytest.mark.parametrize("stem", _SOURCES)
def test_the_output_passes_the_check_with_no_cleared_case(
    stem: str, tmp_path: Path
) -> None:
    root = _checkout(tmp_path)
    path = sanitize_file(_outside(tmp_path, _source(stem)), root, _VUID)
    assert path == f"{FIXTURE_DIR}/sanitized/{_VUID}.json"
    assert check(root, [path, *generated_fixtures()]) == []


# The verifier (VSD-02-005) ----------------------------------------------


def _written(stem: str = _SOURCES[0]) -> str:
    return sanitize(_source(stem), _VUID)


@pytest.mark.spec("VSD-02-005")
@pytest.mark.parametrize("stem", _SOURCES)
def test_sanitizing_the_output_again_changes_nothing(stem: str) -> None:
    text = _written(stem)
    assert verify_sanitized(sanitized_path(_VUID), text) is None


@pytest.mark.spec("VSD-02-005")
@pytest.mark.parametrize(
    ("edit", "reason"),
    [
        (
            lambda t: t.replace("Example Org Alpha", "Real Vendor Inc"),
            "differs",
        ),
        (lambda t: t.replace('"Lorem ', '"Embargoed '), "differs"),
        (lambda t: t.replace("2090-01-04", "2026-01-05"), "differs"),
        (lambda t: t.replace('"pk": 8001', '"pk": 17'), "differs"),
        (
            lambda t: t.replace('"pinned"', '"note_to_self": 1, "pinned"', 1),
            "refuses",
        ),
        (lambda t: t.replace(_VUID, "123456"), "refuses"),
        (lambda t: t[:-3], "does not parse"),
    ],
)
def test_an_edited_sanitizer_file_is_refused(
    edit: TextEdit, reason: str
) -> None:
    text = edit(_written())
    fault = verify_sanitized(sanitized_path(_VUID), text)
    assert fault is not None and reason in fault


@pytest.mark.spec("VSD-02-005")
def test_a_hand_made_file_with_the_sanitizer_marker_is_refused() -> None:
    reads = _reads()
    reads["case"]["vuid"] = _VUID  # type: ignore[index]
    text = json.dumps({**marker_for(SANITIZER), "reads": reads}, indent=2)
    path = sanitized_path(_VUID)
    [fault] = file_faults(path, text + "\n", frozenset())
    assert "differs from what the sanitizer writes" in fault


@pytest.mark.spec("VSD-02-005")
def test_a_sanitizer_file_at_another_path_is_refused() -> None:
    fault = verify_sanitized(f"{FIXTURE_DIR}/sanitized/other.json", _written())
    assert fault is not None and "only to" in fault


def test_a_file_naming_no_case_id_is_refused() -> None:
    text = json.dumps({**marker_for(SANITIZER), "reads": {}})
    fault = verify_sanitized(sanitized_path(_VUID), text)
    assert fault is not None and "names no case id" in fault
