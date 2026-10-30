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

"""Regression tests for core/models/_helpers.py — _as_id must live in the
models layer, not use_cases.

Issue #1428: BT import-direction violation — behaviors/ imported _as_id from
use_cases/_helpers, violating the rule that behaviors/ must not import from
use_cases/.
"""

import ast
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from test.support.case_owner import CASE_OWNER_ID
from vultron.core.models import _helpers
from vultron.core.models._helpers import (
    format_timestamp,
    now_utc,
    now_utc_after,
    require_future_aware,
    timestamp_serializer,
)
from vultron.demo.determinism import SteppingClock

# --- Architecture ratchet ------------------------------------------------


def _imports_from_use_cases(path: str) -> list[str]:
    """Return lines in *path* that import from use_cases."""
    with open(path) as f:
        src = f.read()
    tree = ast.parse(src)
    violations = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and "use_cases" in node.module
        ):
            violations.append(
                f"line {node.lineno}: from {node.module} import ..."
            )
    return violations


def test_common_py_no_use_cases_import():
    """common.py must not import _as_id from use_cases._helpers (BT-IDM-02 violation)."""
    path = "vultron/core/behaviors/case/nodes/participant/common.py"
    violations = _imports_from_use_cases(path)
    assert violations == [], (
        f"{path} still imports from use_cases:\n" + "\n".join(violations)
    )


# --- Behavioural correctness -------------------------------------------


def test_as_id_none():
    from vultron.core.models._helpers import _as_id

    assert _as_id(None) is None


def test_as_id_str():
    from vultron.core.models._helpers import _as_id

    assert _as_id("urn:uuid:abc") == "urn:uuid:abc"


def test_as_id_object_with_id_():
    from vultron.core.models._helpers import _as_id

    class Obj:
        id_ = "urn:uuid:xyz"

    assert _as_id(Obj()) == "urn:uuid:xyz"


def test_as_id_object_without_id_():
    from vultron.core.models._helpers import _as_id

    class Obj:
        def __str__(self):
            return "fallback"

    assert _as_id(Obj()) == "fallback"


# --- status_recency_key (CM-29-001) ---------------------------------------


def test_status_recency_key_prefers_updated_over_published():
    from datetime import datetime

    from vultron.core.models._helpers import status_recency_key

    updated = datetime(2026, 6, 1, tzinfo=UTC)
    published = datetime(2026, 1, 1, tzinfo=UTC)
    assert status_recency_key(updated, published) == updated


def test_status_recency_key_falls_back_to_published():
    from datetime import datetime

    from vultron.core.models._helpers import status_recency_key

    published = datetime(2026, 1, 1, tzinfo=UTC)
    assert status_recency_key(None, published) == published


def test_status_recency_key_timestampless_sorts_to_bottom():
    from datetime import datetime

    from vultron.core.models._helpers import status_recency_key

    key = status_recency_key(None, None)
    assert key == datetime.min.replace(tzinfo=UTC)
    assert key.tzinfo is UTC


def test_status_recency_key_normalises_naive_to_utc():
    """Naive timestamps (wire ISO strings without offset) are treated as UTC.

    Regression for #2979: a naive ``updated`` compared against the aware
    ``datetime.min`` floor would otherwise raise ``TypeError`` in ``max()``.
    """
    from datetime import datetime

    from vultron.core.models._helpers import status_recency_key

    naive = datetime(2026, 1, 1)  # noqa: DTZ001 — deliberately naive
    key = status_recency_key(naive, None)
    assert key == datetime(2026, 1, 1, tzinfo=UTC)
    # Comparable against the timestampless floor without raising.
    assert key > status_recency_key(None, None)


# --- as_utc ---------------------------------------------------------------


def test_as_utc_with_none_returns_none():
    from vultron.core.models._helpers import as_utc

    assert as_utc(None) is None


def test_as_utc_with_naive_datetime_returns_utc_aware():
    from datetime import datetime

    from vultron.core.models._helpers import as_utc

    naive = datetime(2026, 1, 1, 12, 0, 0)  # noqa: DTZ001 — deliberately naive
    result = as_utc(naive)
    assert result is not None
    assert result.tzinfo is UTC


def test_as_utc_with_aware_datetime_returns_same():
    from datetime import datetime

    from vultron.core.models._helpers import as_utc

    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = as_utc(aware)
    assert result is not None
    assert result == aware


def test_as_utc_with_datetime_never_returns_none():
    """as_utc(datetime) MUST NOT return None — parse_published relies on this invariant."""
    from datetime import datetime

    from vultron.core.models._helpers import as_utc

    naive = datetime(2026, 6, 15)  # noqa: DTZ001 — deliberately naive
    aware = datetime(2026, 6, 15, tzinfo=UTC)
    assert as_utc(naive) is not None
    assert as_utc(aware) is not None


# --- parse_published -------------------------------------------------------


def test_parse_published_with_none_returns_none():
    from vultron.core.models._helpers import parse_published

    assert parse_published(None) is None


def test_parse_published_with_invalid_string_returns_none():
    from vultron.core.models._helpers import parse_published

    assert parse_published("not-a-date") is None


def test_parse_published_with_non_string_non_datetime_returns_none():
    from vultron.core.models._helpers import parse_published

    assert parse_published(12345) is None
    assert parse_published(3.14) is None
    assert parse_published([]) is None


def test_parse_published_with_datetime_never_returns_none():
    """Regression for #3221: datetime input must not return None.

    The dead ``None if aware is None else`` guard misled mypy into inferring
    that ``parse_published`` could return ``None`` from a ``datetime`` input,
    causing callers to over-guard.
    """
    from datetime import datetime

    from vultron.core.models._helpers import parse_published

    naive = datetime(2026, 6, 15, 12, 0, 0)  # noqa: DTZ001 — deliberately naive
    aware_utc = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    assert parse_published(naive) is not None
    assert parse_published(aware_utc) is not None


def test_parse_published_with_naive_datetime_returns_utc():
    from datetime import datetime

    from vultron.core.models._helpers import parse_published

    naive = datetime(2026, 6, 15, 12, 0, 0)  # noqa: DTZ001 — deliberately naive
    result = parse_published(naive)
    assert result is not None
    assert result.tzinfo is UTC
    assert result.year == 2026
    assert result.month == 6
    assert result.day == 15


def test_parse_published_with_aware_non_utc_converts_to_utc():
    from datetime import datetime, timedelta, timezone

    from vultron.core.models._helpers import parse_published

    plus5 = timezone(timedelta(hours=5))
    aware_plus5 = datetime(2026, 6, 15, 17, 0, 0, tzinfo=plus5)
    result = parse_published(aware_plus5)
    assert result is not None
    assert result.tzinfo is UTC
    assert result.hour == 12  # 17:00+05:00 → 12:00 UTC


def test_parse_published_with_valid_iso_string_returns_datetime():
    from datetime import datetime

    from vultron.core.models._helpers import parse_published

    result = parse_published("2026-06-15T12:00:00+00:00")
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is UTC


def test_parse_published_with_naive_iso_string_returns_utc():
    from datetime import datetime

    from vultron.core.models._helpers import parse_published

    result = parse_published("2026-06-15T12:00:00")
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is UTC


# --- has_case_statuses ----------------------------------------------------


def test_has_case_statuses_true_when_non_empty():
    from vultron.core.models.case import VulnerabilityCase, has_case_statuses
    from vultron.core.models.case_status import CaseStatus

    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_="https://example.org/cases/x1",
        case_statuses=[CaseStatus(context="https://example.org/cases/x1")],
    )
    assert has_case_statuses(case) is True


def test_has_case_statuses_false_when_empty():
    from vultron.core.models.case import VulnerabilityCase, has_case_statuses

    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_="https://example.org/cases/x2"
    )
    case.case_statuses = []
    assert has_case_statuses(case) is False


def test_has_case_statuses_true_when_default():
    """A new case is seeded with one status, since it always has an owner."""
    from vultron.core.models.case import VulnerabilityCase, has_case_statuses

    case = VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_="https://example.org/cases/x3"
    )
    assert has_case_statuses(case) is True


# --- parse_published -------------------------------------------------------


def test_parse_published_returns_utc_datetime_for_valid_datetime_input():
    """parse_published(datetime) must return a UTC datetime, never None.

    The dead ``None if aware is None else`` branch at line 78 caused type
    checkers to infer that parse_published can return None for a datetime
    input, prompting unnecessary None-guards in callers.  This test pins the
    non-None contract for the datetime path (Bug #3221).
    """
    from datetime import datetime

    from vultron.core.models._helpers import parse_published

    dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    result = parse_published(dt)
    assert result is not None
    assert result.tzinfo == UTC
    assert result == dt


def test_parse_published_returns_utc_datetime_for_valid_iso_string():
    """parse_published(str) must return a UTC datetime for a valid ISO string."""
    from datetime import datetime

    from vultron.core.models._helpers import parse_published

    result = parse_published("2026-01-15T12:00:00+05:30")
    assert result is not None
    assert result.tzinfo == UTC
    assert result == datetime(2026, 1, 15, 6, 30, 0, tzinfo=UTC)


def test_parse_published_returns_none_for_invalid_string():
    from vultron.core.models._helpers import parse_published

    assert parse_published("not-a-date") is None


def test_parse_published_returns_none_for_non_datetime_type():
    from vultron.core.models._helpers import parse_published

    assert parse_published(42) is None
    assert parse_published(None) is None


# --- strip_annotated ------------------------------------------------------


def test_strip_annotated_unwraps_non_empty_string_to_str():
    """``NonEmptyString`` is ``Annotated[str, ...]``; introspection sees ``str``.

    The IRI branch of every reference union is ``NonEmptyString`` (CS-08-001),
    so code that classifies a union branch with ``is str`` must look through
    the wrapper — ``_is_generic_object_ref`` and ``_annotation_branches`` both
    do, via this helper.
    """
    from typing import Annotated

    from pydantic import AfterValidator

    from vultron.core.models._helpers import strip_annotated
    from vultron.primitives import NonEmptyString

    assert strip_annotated(NonEmptyString) is str
    assert strip_annotated(Annotated[int, AfterValidator(abs)]) is int


def test_strip_annotated_leaves_a_bare_type_alone():
    from vultron.core.models._helpers import strip_annotated

    assert strip_annotated(str) is str
    assert strip_annotated(list[str]) == list[str]
    assert strip_annotated(str | None) == (str | None)


_PINNED = datetime(2026, 5, 4, 12, 0, 0, 987654, tzinfo=UTC)
_TICK = timedelta(microseconds=1)


@pytest.fixture
def _frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _helpers, "datetime", SteppingClock(_PINNED, step=timedelta(0))
    )


@pytest.mark.spec("CS-13-008")
def test_now_utc_keeps_microseconds(_frozen_clock: None) -> None:
    assert now_utc() == _PINNED
    assert now_utc().microsecond == 987654


@pytest.mark.spec("CS-13-007")
@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (
            datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC),
            "2026-10-30T12:00:00.000000+00:00",
        ),
        (
            datetime(2026, 10, 30, 12, 0, 0, 120000, tzinfo=UTC),
            "2026-10-30T12:00:00.120000+00:00",
        ),
        (
            datetime(
                2026, 10, 30, 17, 0, 0, tzinfo=timezone(timedelta(hours=5))
            ),
            "2026-10-30T17:00:00.000000+05:00",
        ),
        (
            datetime(2026, 10, 30, 12, 0, 0),  # noqa: DTZ001
            "2026-10-30T12:00:00.000000+00:00",
        ),
    ],
    ids=["whole-second", "fractional", "carried-offset", "naive-read-as-utc"],
)
def test_one_instant_serializes_to_one_string(
    instant: datetime, expected: str
) -> None:
    """Six digits whether or not the microseconds are zero; offset kept."""
    assert format_timestamp(instant) == expected
    reparsed = datetime.fromisoformat(expected)
    assert format_timestamp(reparsed) == expected


@pytest.mark.spec("CS-13-007")
@pytest.mark.parametrize("as_any", [False, True], ids=["plain", "as-any"])
def test_timestamp_serializer_leaves_a_non_datetime_member_alone(
    as_any: bool,
) -> None:
    """A union field keeps its other members' own JSON form."""
    from pydantic import BaseModel

    class _Closes(BaseModel):
        closed: datetime | bool | None = None
        _serialize_closed = timestamp_serializer("closed")

    def dump(model: _Closes) -> dict[str, object]:
        return model.model_dump(mode="json", serialize_as_any=as_any)

    whole = datetime(2026, 10, 30, 12, 0, 0, tzinfo=UTC)
    assert dump(_Closes(closed=whole)) == {
        "closed": "2026-10-30T12:00:00.000000+00:00"
    }
    assert dump(_Closes(closed=True)) == {"closed": True}
    assert dump(_Closes()) == {"closed": None}


@pytest.mark.parametrize(
    "latest",
    [None, _PINNED - _TICK],
    ids=["no-latest", "latest-earlier"],
)
def test_now_utc_after_returns_now_utc_when_the_clock_is_ahead(
    _frozen_clock: None, latest: datetime | None
) -> None:
    assert now_utc_after(latest) == _PINNED


@pytest.mark.parametrize(
    "latest",
    [_PINNED, _PINNED + timedelta(seconds=5, microseconds=400)],
    ids=["same-tick", "peer-clock-ahead"],
)
def test_now_utc_after_bumps_one_microsecond_past_latest(
    _frozen_clock: None, latest: datetime
) -> None:
    result = now_utc_after(latest)
    assert result == latest + _TICK
    assert result > latest


def test_now_utc_after_returns_a_bump_in_utc_for_a_peer_offset(
    _frozen_clock: None,
) -> None:
    plus_five = timezone(timedelta(hours=5))
    latest = (_PINNED + timedelta(seconds=2)).astimezone(plus_five)
    result = now_utc_after(latest)
    assert result == _PINNED + timedelta(seconds=2) + _TICK
    assert result.utcoffset() == timedelta(0)


def test_require_future_aware_compares_against_now_utc(
    _frozen_clock: None,
) -> None:
    # The pinned clock is long past, so only a read through now_utc() lets a
    # value one second after it count as the future.
    future = _PINNED + timedelta(seconds=1)
    assert require_future_aware(future) == future
    with pytest.raises(ValueError, match="must be in the future"):
        require_future_aware(_PINNED)


# --- CS-13-002 ratchet: every application clock read goes through now_utc --

_VULTRON = Path(__file__).resolve().parents[3] / "vultron"
# Repo tooling (history, ADR and spec CLIs), not the CVD prototype CS-13 scopes.
_CLOCK_EXEMPT = _VULTRON / "metadata"
_CLOCK_CALLS = {"now", "utcnow", "today"}
_CLOCK_TYPES = {"datetime", "date"}


def _direct_clock_reads(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    allowed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "now_utc":
            allowed.update(id(n) for n in ast.walk(node))
    reads = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and id(node) not in allowed
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _CLOCK_CALLS
            and (
                (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id in _CLOCK_TYPES
                )
                or (
                    isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr in _CLOCK_TYPES
                )
            )
        ):
            reads.append(f"{path.relative_to(_VULTRON.parent)}:{node.lineno}")
    return reads


def test_application_code_reads_the_clock_only_through_now_utc() -> None:
    """CS-13-002: no ``datetime.now()`` outside ``now_utc`` itself."""
    reads = [
        read
        for path in sorted(_VULTRON.rglob("*.py"))
        if not path.is_relative_to(_CLOCK_EXEMPT)
        for read in _direct_clock_reads(path)
    ]
    assert reads == [], (
        "read the clock through now_utc() (CS-13-002):\n" + "\n".join(reads)
    )
