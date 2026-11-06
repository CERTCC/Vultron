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
"""Planned behaviour for CSAF documents in reports (ADR-0184, CSAF-01 to CSAF-03).

Strict-``xfail`` tests for protocol requirements written before the code that
satisfies them exists; see ``notes/spec-authoring-rules.md`` § "Use a
Strict ``xfail`` for Not-Yet-Implemented Specs", and
``notes/csaf-report-content.md`` for the planned layout.

Four probes stand in for the behaviour:

- the submit-report request accepts a CSAF document (the sender side:
  CSAF-01-001, CSAF-01-002, CSAF-02-004, CSAF-02-007);
- the CSAF reader package exists (recognition and the lenient receive side:
  CSAF-01-003, CSAF-02-006);
- the format-neutral report-claims model exists (the sender's statement at the
  initial report and the case inputs it fills: CSAF-02-001 to CSAF-02-003,
  CSAF-02-005, CSAF-03-001 to CSAF-03-007);
- the case holds vulnerability records and case references (CSAF-03-008,
  CSAF-03-009, both waiting on #5132).

When a piece lands, its tests XPASS, ``strict=True`` fails the build, and the
builder replaces each probe with the behavioural check the requirement's
``verification:`` names. That promotion is the point: this module is a
ratchet, not a test of the feature.
"""

from importlib.util import find_spec

import pytest

from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.use_cases.triggers.request_bodies.report import (
    SubmitReportRequest,
)

_TRACKED = "Tracked by #5911 (source #5131)."
_RECORDS = "Waits on #5132 (vulnerability records on a case)."


def _sender_attaches_csaf() -> bool:
    """Return whether the submit-report request takes a CSAF document."""
    return "csaf_document" in SubmitReportRequest.model_fields


def _csaf_reader_exists() -> bool:
    """Return whether the wire-side CSAF reader package exists."""
    return find_spec("vultron.wire.csaf") is not None


def _report_claims_exist() -> bool:
    """Return whether the format-neutral report-claims model exists."""
    return find_spec("vultron.core.models.report_claims") is not None


def _case_has(field: str) -> bool:
    """Return whether ``VulnerabilityCase`` declares ``field``."""
    return field in VulnerabilityCase.model_fields


@pytest.mark.spec("CSAF-01-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-01-001: the sender attaches no CSAF Document yet. {_TRACKED}",
)
def test_a_sender_carries_csaf_as_an_attached_document():
    assert _sender_attaches_csaf()


@pytest.mark.spec("CSAF-01-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-01-002: no CSAF Document is sent, so none has a mediaType. {_TRACKED}",
)
def test_the_csaf_document_is_labelled_application_json():
    assert _sender_attaches_csaf()


@pytest.mark.spec("CSAF-01-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-01-003: no receiver recognizes CSAF 2.1 yet. {_TRACKED}",
)
def test_a_receiver_recognizes_csaf_by_schema_and_version():
    assert _csaf_reader_exists()


@pytest.mark.spec("CSAF-02-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-001: no receiver fills gaps from CSAF yet. {_TRACKED}",
)
def test_the_initial_report_may_fill_gaps_from_csaf():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-02-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-002: no CSAF reading exists to limit yet. {_TRACKED}",
)
def test_csaf_outside_the_initial_report_changes_no_case_data():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-02-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-003: no CSAF value competes with a Vultron field yet. {_TRACKED}",
)
def test_a_vultron_field_beats_the_csaf_value():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-02-004")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-004: the sender fills no field from CSAF yet. {_TRACKED}",
)
def test_a_sender_fills_vultron_fields_that_agree_with_its_csaf():
    assert _sender_attaches_csaf()


@pytest.mark.spec("CSAF-02-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-005: no CSAF value is read yet. {_TRACKED}",
)
def test_an_omitted_csaf_field_or_schema_default_is_no_statement():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-02-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-006: no receiver reads CSAF leniently yet. {_TRACKED}",
)
def test_a_broken_csaf_attachment_never_refuses_the_report():
    assert _csaf_reader_exists()


@pytest.mark.spec("CSAF-02-007")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-007: the sender checks no CSAF document yet. {_TRACKED}",
)
def test_a_sender_does_not_attach_schema_invalid_csaf():
    assert _sender_attaches_csaf()


@pytest.mark.spec("CSAF-03-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-001: no disclosure date becomes an embargo end yet. {_TRACKED}",
)
def test_a_future_disclosure_date_proposes_the_embargo_end():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-002: no disclosure date is read yet. {_TRACKED}",
)
def test_the_earliest_future_disclosure_date_wins():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-003: no past disclosure date sets P yet. {_TRACKED}",
)
def test_a_past_disclosure_date_states_the_vul_is_public():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-004")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-004: no SSVC Exploitation value is read yet. {_TRACKED}",
)
def test_ssvc_exploitation_poc_sets_x_and_active_sets_a():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-005: no exploitation date is read yet. {_TRACKED}",
)
def test_a_first_known_exploitation_date_sets_a():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-006: a case takes no name from its report yet. {_TRACKED}",
)
def test_a_case_starts_with_its_reports_name_and_summary():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-007")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-007: no CSAF title or summary note is read yet. {_TRACKED}",
)
def test_a_missing_name_and_summary_come_from_the_csaf_document():
    assert _report_claims_exist()


@pytest.mark.spec("CSAF-03-008")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-008: the case has no vulnerability records. {_RECORDS}",
)
def test_each_csaf_vulnerability_becomes_a_vulnerability_record():
    assert _case_has("vulnerability_records")


@pytest.mark.spec("CSAF-03-009")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-009: the case has no case references. {_RECORDS}",
)
def test_each_csaf_reference_becomes_a_case_reference():
    assert _case_has("case_references")
