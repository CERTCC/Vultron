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

"""Regression tests for core/models/_helpers.py — _as_id and
_report_phase_status_id must live in the models layer, not use_cases.

Issue #1428: BT import-direction violation — behaviors/ imported _as_id and
_report_phase_status_id from use_cases/_helpers, violating the rule that
behaviors/ must not import from use_cases/.
"""

import ast

# --- Architecture ratchet ------------------------------------------------


def _imports_from_use_cases(path: str) -> list[str]:
    """Return lines in *path* that import from use_cases."""
    with open(path) as f:
        src = f.read()
    tree = ast.parse(src)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "use_cases" in node.module:
                violations.append(
                    f"line {node.lineno}: from {node.module} import ..."
                )
    return violations


def test_common_py_no_use_cases_import():
    """common.py must not import _as_id / _report_phase_status_id from
    use_cases._helpers (BT-IDM-02 violation)."""
    path = "vultron/core/behaviors/case/nodes/participant/common.py"
    violations = _imports_from_use_cases(path)
    assert (
        violations == []
    ), f"{path} still imports from use_cases:\n" + "\n".join(violations)


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


def test_report_phase_status_id_deterministic():
    from vultron.core.models._helpers import _report_phase_status_id

    a = _report_phase_status_id("actor1", "report1", "RECEIVED")
    b = _report_phase_status_id("actor1", "report1", "RECEIVED")
    assert a == b


def test_report_phase_status_id_urn_format():
    from vultron.core.models._helpers import _report_phase_status_id

    result = _report_phase_status_id("actor1", "report1", "RECEIVED")
    assert result.startswith("urn:uuid:")


def test_report_phase_status_id_different_states():
    from vultron.core.models._helpers import _report_phase_status_id

    id_received = _report_phase_status_id("actor1", "report1", "RECEIVED")
    id_valid = _report_phase_status_id("actor1", "report1", "VALID")
    assert id_received != id_valid


# --- status_recency_key (CM-29-001) ---------------------------------------


def test_status_recency_key_prefers_updated_over_published():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import status_recency_key

    updated = datetime(2026, 6, 1, tzinfo=timezone.utc)
    published = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert status_recency_key(updated, published) == updated


def test_status_recency_key_falls_back_to_published():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import status_recency_key

    published = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert status_recency_key(None, published) == published


def test_status_recency_key_timestampless_sorts_to_bottom():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import status_recency_key

    key = status_recency_key(None, None)
    assert key == datetime.min.replace(tzinfo=timezone.utc)
    assert key.tzinfo is timezone.utc


def test_status_recency_key_normalises_naive_to_utc():
    """Naive timestamps (wire ISO strings without offset) are treated as UTC.

    Regression for #2979: a naive ``updated`` compared against the aware
    ``datetime.min`` floor would otherwise raise ``TypeError`` in ``max()``.
    """
    from datetime import datetime, timezone

    from vultron.core.models._helpers import status_recency_key

    naive = datetime(2026, 1, 1)  # no tzinfo
    key = status_recency_key(naive, None)
    assert key == datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Comparable against the timestampless floor without raising.
    assert key > status_recency_key(None, None)


# --- as_utc ---------------------------------------------------------------


def test_as_utc_with_none_returns_none():
    from vultron.core.models._helpers import as_utc

    assert as_utc(None) is None


def test_as_utc_with_naive_datetime_returns_utc_aware():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import as_utc

    naive = datetime(2026, 1, 1, 12, 0, 0)
    result = as_utc(naive)
    assert result is not None
    assert result.tzinfo is timezone.utc


def test_as_utc_with_aware_datetime_returns_same():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import as_utc

    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = as_utc(aware)
    assert result is not None
    assert result == aware


def test_as_utc_with_datetime_never_returns_none():
    """as_utc(datetime) MUST NOT return None — parse_published relies on this invariant."""
    from datetime import datetime, timezone

    from vultron.core.models._helpers import as_utc

    naive = datetime(2026, 6, 15)
    aware = datetime(2026, 6, 15, tzinfo=timezone.utc)
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
    from datetime import datetime, timezone

    from vultron.core.models._helpers import parse_published

    naive = datetime(2026, 6, 15, 12, 0, 0)
    aware_utc = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_published(naive) is not None
    assert parse_published(aware_utc) is not None


def test_parse_published_with_naive_datetime_returns_utc():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import parse_published

    naive = datetime(2026, 6, 15, 12, 0, 0)
    result = parse_published(naive)
    assert result is not None
    assert result.tzinfo is timezone.utc
    assert result.year == 2026
    assert result.month == 6
    assert result.day == 15


def test_parse_published_with_aware_non_utc_converts_to_utc():
    from datetime import datetime, timezone, timedelta

    from vultron.core.models._helpers import parse_published

    plus5 = timezone(timedelta(hours=5))
    aware_plus5 = datetime(2026, 6, 15, 17, 0, 0, tzinfo=plus5)
    result = parse_published(aware_plus5)
    assert result is not None
    assert result.tzinfo is timezone.utc
    assert result.hour == 12  # 17:00+05:00 → 12:00 UTC


def test_parse_published_with_valid_iso_string_returns_datetime():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import parse_published

    result = parse_published("2026-06-15T12:00:00+00:00")
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is timezone.utc


def test_parse_published_with_naive_iso_string_returns_utc():
    from datetime import datetime, timezone

    from vultron.core.models._helpers import parse_published

    result = parse_published("2026-06-15T12:00:00")
    assert result is not None
    assert isinstance(result, datetime)
    assert result.tzinfo is timezone.utc


# --- has_case_statuses ----------------------------------------------------


def test_has_case_statuses_true_when_non_empty():
    from vultron.core.models.case import has_case_statuses
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_status import CaseStatus

    case = VulnerabilityCase(
        id_="https://example.org/cases/x1",
        case_statuses=[CaseStatus(context="https://example.org/cases/x1")],
    )
    assert has_case_statuses(case) is True


def test_has_case_statuses_false_when_empty():
    from vultron.core.models.case import has_case_statuses
    from vultron.core.models.case import VulnerabilityCase

    # No attributed_to → _init_case_statuses skips seeding → stays empty
    case = VulnerabilityCase(
        id_="https://example.org/cases/x2",
        case_statuses=[],
    )
    assert has_case_statuses(case) is False


def test_has_case_statuses_false_when_default():
    """VulnerabilityCase without attributed_to keeps case_statuses empty."""
    from vultron.core.models.case import has_case_statuses
    from vultron.core.models.case import VulnerabilityCase

    case = VulnerabilityCase(id_="https://example.org/cases/x3")
    assert has_case_statuses(case) is False
