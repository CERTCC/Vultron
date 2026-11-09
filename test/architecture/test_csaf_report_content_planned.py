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
"""Planned behavior for CSAF documents in reports (ADR-0184, CSAF-01 to CSAF-05).

Strict-``xfail`` tests for requirements written before the code that satisfies
them exists; see ``notes/spec-authoring-rules.md`` § "Use a Strict ``xfail``
for Not-Yet-Implemented Specs", and ``notes/csaf-report-content.md`` for the
planned layout.

One probe stands in for every planned requirement: a test module elsewhere
under ``test/`` carries the requirement's ID in a ``@pytest.mark.spec`` marker.
Each tracking issue's acceptance criteria name the behavioral tests it writes,
so the issue that builds a requirement is the only one whose change flips that
requirement's probe. A probe keyed on a module or field name would flip when
an earlier task created the name, and turn that task's build red on a probe it
does not own.

When the behavioral test lands, the probe XPASSes, ``strict=True`` fails the
build, and the builder deletes the probe. That promotion is the point: this
module is a ratchet, not a test of the feature.

CSAF-05-004 already holds, so its test is a real check, not a probe.
"""

import re
from functools import cache
from pathlib import Path

import pytest

from test.architecture import _corpus

_SEND = "Tracked by #6092 (source #5131)."
_RECEIVE = "Tracked by #6090 (source #5131)."
_CASE = "Tracked by #6091 (source #5131)."
_MODELS = "Tracked by #6089 (source #5131)."
_WATCH = "Tracked by #6094 (source #5131)."
_RECORDS = (
    "Tracked by #6093, which waits on #5132 (vulnerability records on a case)."
)


_HERE = Path(__file__).resolve()
_TEST_ROOT = _corpus.REPO_ROOT / "test"
_SPEC_MARKER = re.compile(r"spec\(([^)]*)\)")
_CSAF_ID = re.compile(r"""["'](CSAF-\d{2}-\d{3})["']""")
#: The CSAF Technical Committee keeps its test documents under this path of
#: its repository (CSAF-05-004).
_TC_TEST_DATA = "csaf_2.1/test/"


def _other_modules_mentioning(fragment: str) -> list[tuple[Path, str]]:
    """Return the test modules other than this one whose source holds ``fragment``."""
    return [
        (path, source)
        for path, source in _corpus.sources_mentioning(
            fragment, under=_TEST_ROOT
        )
        if path.resolve() != _HERE
    ]


@cache
def _csaf_ids_marked_elsewhere() -> frozenset[str]:
    """Return the CSAF IDs that a ``spec`` marker in another test module names."""
    return frozenset(
        spec_id
        for _, text in _other_modules_mentioning("CSAF-")
        for marker_args in _SPEC_MARKER.findall(text)
        for spec_id in _CSAF_ID.findall(marker_args)
    )


def _has_behavioral_test(request: pytest.FixtureRequest) -> bool:
    """Return whether another test module marks this probe's spec ID."""
    marker = request.node.get_closest_marker("spec")
    assert marker is not None and marker.args, "a probe needs a spec marker"
    return set(marker.args) <= _csaf_ids_marked_elsewhere()


@pytest.mark.spec("CSAF-01-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-01-001: the sender attaches no CSAF Document yet. {_SEND}",
)
def test_a_sender_carries_csaf_as_an_attached_document(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-01-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-01-002: no CSAF Document is sent, so none has a mediaType. {_SEND}",
)
def test_the_csaf_document_is_labelled_application_json(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-01-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-01-003: no receiver recognizes CSAF 2.1 yet. {_RECEIVE}",
)
def test_a_receiver_recognizes_csaf_by_schema_and_version(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-001: no receiver fills gaps from CSAF yet. {_CASE}",
)
def test_the_initial_report_may_fill_gaps_from_csaf(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-002: no CSAF reading exists to limit yet. {_CASE}",
)
def test_csaf_outside_the_initial_report_changes_no_case_data(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-003: no CSAF value competes with a Vultron field yet. {_CASE}",
)
def test_a_vultron_field_beats_the_csaf_value(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-004")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-004: the sender fills no field from CSAF yet. {_SEND}",
)
def test_a_sender_fills_vultron_fields_that_agree_with_its_csaf(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-005: no CSAF value is read yet. {_RECEIVE}",
)
def test_an_omitted_csaf_field_or_schema_default_is_no_statement(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-006: no receiver reads CSAF leniently yet. {_RECEIVE}",
)
def test_a_broken_csaf_attachment_never_refuses_the_report(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-02-007")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-02-007: the sender checks no CSAF document yet. {_SEND}",
)
def test_a_sender_does_not_attach_schema_invalid_csaf(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-001: no disclosure date becomes an embargo end yet. {_CASE}",
)
def test_a_future_disclosure_date_proposes_the_embargo_end(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-002: no disclosure date is read yet. {_CASE}",
)
def test_the_earliest_future_disclosure_date_wins(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-003: no past disclosure date sets P yet. {_CASE}",
)
def test_a_past_disclosure_date_states_the_vul_is_public(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-004")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-004: no SSVC Exploitation value is read yet. {_CASE}",
)
def test_ssvc_exploitation_poc_sets_x_and_active_sets_a(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-005: no exploitation date is read yet. {_CASE}",
)
def test_a_first_known_exploitation_date_sets_a(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-006: a case takes no name from its report yet. {_CASE}",
)
def test_a_case_starts_with_its_reports_name_and_summary(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-007")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-007: no CSAF title or summary note is read yet. {_CASE}",
)
def test_a_missing_name_and_summary_come_from_the_csaf_document(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-008")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-008: the case has no vulnerability records. {_RECORDS}",
)
def test_each_csaf_vulnerability_becomes_a_vulnerability_record(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-03-009")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-03-009: the case has no case references. {_RECORDS}",
)
def test_each_csaf_reference_becomes_a_case_reference(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-001: no CSAF schema verdict is recorded yet. {_RECEIVE}",
)
def test_receipt_records_a_schema_verdict(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-002: no CSAF schema verdict exists yet. {_RECEIVE}",
)
def test_the_verdict_never_says_valid_csaf(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-003: no lenient CSAF read exists yet. {_RECEIVE}",
)
def test_a_schema_invalid_document_is_read_field_by_field(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-004")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-004: no claims record is stored yet. {_RECEIVE}",
)
def test_the_report_keeps_a_record_of_what_its_csaf_claimed(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-005: no claims record exists yet. {_RECEIVE}",
)
def test_the_claims_record_is_never_sent(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-006: no case-split signal is recorded yet. {_CASE}",
)
def test_disagreeing_vulnerabilities_raise_a_case_split_signal(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-007")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-007: no candidate-parties signal is recorded yet. {_CASE}",
)
def test_several_affected_vendors_raise_a_candidate_parties_signal(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-008")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-008: no signal exists yet. {_CASE}",
)
def test_a_signal_never_splits_suggests_or_invites(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-009")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-009: submit-report takes no CSAF document yet. {_SEND}",
)
def test_submit_report_refuses_invalid_csaf_with_422(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-04-010")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-04-010: submit-report takes no CSAF document yet. {_SEND}",
)
def test_submit_report_fills_missing_fields_from_csaf(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-05-001: no pinned CSAF draft exists yet. {_MODELS}",
)
def test_one_pin_names_the_csaf_draft(request: pytest.FixtureRequest) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-05-002: no pinned local copy exists yet. {_MODELS}",
)
def test_models_come_from_the_pinned_local_copy(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-05-003: no generated models exist yet. {_MODELS}",
)
def test_regeneration_reproduces_the_committed_models(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-004")
def test_the_suite_never_reads_the_tc_test_documents() -> None:
    readers = [
        str(path.relative_to(_TEST_ROOT))
        for path, _ in _other_modules_mentioning(_TC_TEST_DATA)
    ]
    assert readers == [], (
        f"CSAF-05-004: these test modules name the CSAF TC test data: {readers}"
    )


@pytest.mark.spec("CSAF-05-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-05-005: no CSAF draft-watch workflow exists yet. {_WATCH}",
)
def test_a_scheduled_job_watches_the_csaf_draft(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-05-006: no CSAF draft-watch workflow exists yet. {_WATCH}",
)
def test_the_watch_job_keeps_one_open_issue(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)


@pytest.mark.spec("CSAF-05-007")
@pytest.mark.xfail(
    strict=True,
    reason=f"CSAF-05-007: no CSAF draft-watch workflow exists yet. {_WATCH}",
)
def test_the_watch_issue_names_the_fields_affected(
    request: pytest.FixtureRequest,
) -> None:
    assert _has_behavioral_test(request)
