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


# --- has_case_statuses ----------------------------------------------------


def test_has_case_statuses_true_when_non_empty():
    from vultron.core.models._helpers import has_case_statuses
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_status import CaseStatus

    case = VulnerabilityCase(
        id_="https://example.org/cases/x1",
        case_statuses=[CaseStatus(context="https://example.org/cases/x1")],
    )
    assert has_case_statuses(case) is True


def test_has_case_statuses_false_when_empty():
    from vultron.core.models._helpers import has_case_statuses
    from vultron.core.models.case import VulnerabilityCase

    # No attributed_to → _init_case_statuses skips seeding → stays empty
    case = VulnerabilityCase(
        id_="https://example.org/cases/x2",
        case_statuses=[],
    )
    assert has_case_statuses(case) is False


def test_has_case_statuses_false_when_default():
    """VulnerabilityCase without attributed_to keeps case_statuses empty."""
    from vultron.core.models._helpers import has_case_statuses
    from vultron.core.models.case import VulnerabilityCase

    case = VulnerabilityCase(id_="https://example.org/cases/x3")
    assert has_case_statuses(case) is False
