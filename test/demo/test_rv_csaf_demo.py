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
"""Tests for the rv-csaf scenario: a case that starts from a CSAF report (DEMOMA-28).

The scenario is composition (:mod:`vultron.demo.helpers.story`), so the tests
sit on its story's shape, on its two own fragments driven against a stand-in
cast (:func:`~test.demo._helpers.story_state`), and on the shared opening's
CSAF form, :func:`~vultron.demo.helpers.vendor_story.reporter_tells_the_vendor`.
What the shared ending does is ``rv``'s to test (``test_rv_demo.py``).

``demo_gate`` and ``demo_check`` stay real throughout, and their labels and
outcomes are read off the check tree :func:`recording_checks` records, so an
assertion inside a check cannot propagate and pass the test while proving
nothing (``vultron/demo/AGENTS.md`` § "Gate Each Step on Its Cause", rule 8).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import JsonValue

import vultron.demo.scenario.rv_csaf_demo as demo
from test.demo._helpers import mock_case, story_state
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.coordinated_story import REPORTER
from vultron.demo.helpers.csaf_report import (
    CSAF_REPORT_SUMMARY,
    CSAF_REPORT_TITLE,
    VENDOR_DEFAULT_EMBARGO,
    csaf_disclosure_date,
)
from vultron.demo.helpers.story import Choose
from vultron.demo.helpers.vendor_story import (
    THE_VENDORS_CASE,
    VENDOR,
    opening as vendor_opening,
    the_reporter_asks_about_the_workaround,
)
from vultron.demo.helpers.workflow import report as workflow_report
from vultron.demo.scenario import rv_demo
from vultron.demo.utils.check_tree import (
    CheckKind,
    CheckOutcome,
    recording_checks,
    walk,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

_WRITTEN = datetime(2026, 3, 1, 12, 0, 0, 250000, tzinfo=UTC)
_DISCLOSURE = csaf_disclosure_date(_WRITTEN)


@contextlib.contextmanager
def _checks() -> Iterator[dict[str, CheckOutcome]]:
    """Record each gate's and check's outcome by label, through the real ones.

    The dict fills as the block leaves, so read it after the ``with``.
    """
    outcomes: dict[str, CheckOutcome] = {}
    with recording_checks() as recorder:
        yield outcomes
    outcomes.update(
        (node.label, node.outcome)
        for node in walk(recorder.tree())
        if node.kind in (CheckKind.CHECK, CheckKind.GATE)
    )


def _labelled(outcomes: dict[str, CheckOutcome], prefix: str) -> CheckOutcome:
    """The outcome of the one recorded node whose label starts with *prefix*."""
    matches = [o for label, o in outcomes.items() if label.startswith(prefix)]
    assert len(matches) == 1, (prefix, outcomes)
    return matches[0]


def _state():
    """The Reporter and the Vendor, on an open case whose roster is confirmed."""
    state = story_state(REPORTER, VENDOR, case=mock_case())
    state.keep(THE_VENDORS_CASE, str(state.case.id_))
    state.keep(demo.THE_CSAF_DISCLOSURE_DATE, _DISCLOSURE)
    return state


def _canonical_case(
    *, name: str = CSAF_REPORT_TITLE, summary: str = CSAF_REPORT_SUMMARY
) -> MagicMock:
    case = MagicMock()
    case.id_ = "urn:test:case"
    case.name = name
    case.summary = summary
    return case


def _proposal(context: str = "urn:test:report") -> as_EmbargoEvent:
    return as_EmbargoEvent(
        id_="urn:test:csaf-proposal",
        context=context,
        end_time=_DISCLOSURE,
    )


# ---------------------------------------------------------------------------
# The story and the cast
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-28-001")
def test_the_cast_is_the_reporter_the_vendor_and_the_case_actor() -> None:
    assert [role.name for role in demo.ROLES][:2] == [REPORTER, VENDOR]
    assert len(demo.ROLES) == 3


def test_the_story_parts_from_every_other_scenario_at_the_root() -> None:
    """Its only decision is the root's, so it shares no recorded prefix."""
    assert demo.STORY.path == (("reporter-whom-to-tell", "vendor-csaf"),)
    first = demo.STORY.items[0]
    assert isinstance(first, Choose)
    assert first.by == REPORTER


@pytest.mark.spec("DEMOMA-28-005")
def test_the_story_ends_with_rvs_fragments() -> None:
    """After the case starts, every fragment is the one rv tells (DEMOMA-17-001)."""
    rv_ending = rv_demo.STORY.items[-3:]
    assert demo.STORY.items[-4:] == (
        the_reporter_asks_about_the_workaround,
        *rv_ending,
    )
    assert demo.STORY.items[1:3] == (
        demo.the_reporter_sends_a_csaf_report,
        demo.the_case_starts_from_the_csaf_report,
    )


# ---------------------------------------------------------------------------
# The opening: the policy, then the CSAF submission
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-28-002")
class TestTheReporterSendsACsafReport:
    """The Vendor publishes its default; then the Reporter sends the document."""

    def test_the_policy_is_published_before_the_document_is_sent(self) -> None:
        state = story_state(REPORTER, VENDOR)
        order: list[str] = []

        with (
            patch.object(
                demo,
                "publish_embargo_policy",
                side_effect=lambda *a, **kw: order.append("policy"),
            ) as policy,
            patch.object(demo, "from_now", return_value=_WRITTEN),
            patch.object(
                demo,
                "reporter_tells_the_vendor",
                side_effect=lambda *a, **kw: order.append("submit"),
            ) as submit,
            _checks() as outcomes,
        ):
            demo.the_reporter_sends_a_csaf_report(state)

        assert order == ["policy", "submit"]
        assert policy.call_args.args == (
            state.client(VENDOR),
            state.actor(VENDOR).actor,
            VENDOR_DEFAULT_EMBARGO,
        )
        document: dict[str, Any] = submit.call_args.kwargs["csaf_document"]
        assert document["document"]["title"] == CSAF_REPORT_TITLE
        assert state.kept(demo.THE_CSAF_DISCLOSURE_DATE) == _DISCLOSURE
        assert set(outcomes.values()) == {CheckOutcome.PASSED}

    def test_a_policy_that_fails_sends_no_report(self) -> None:
        """Without the default, the M3 check would read an uncontested case."""
        state = story_state(REPORTER, VENDOR)

        with (
            patch.object(
                demo,
                "publish_embargo_policy",
                side_effect=AssertionError("policy refused"),
            ),
            patch.object(demo, "reporter_tells_the_vendor") as submit,
            _checks() as outcomes,
        ):
            demo.the_reporter_sends_a_csaf_report(state)

        submit.assert_not_called()
        assert _labelled(outcomes, "Vendor1 publishes") is CheckOutcome.FAILED

    def test_a_refused_submission_is_reported_under_its_own_name(
        self,
    ) -> None:
        """The policy passed, so its gate must not carry the submission's fault."""
        state = story_state(REPORTER, VENDOR)

        with (
            patch.object(demo, "publish_embargo_policy"),
            patch.object(
                demo,
                "reporter_tells_the_vendor",
                side_effect=AssertionError("submit-report refused"),
            ),
            _checks() as outcomes,
        ):
            demo.the_reporter_sends_a_csaf_report(state)

        assert (
            _labelled(outcomes, "Reporter sends Vendor1")
            is CheckOutcome.FAILED
        )
        assert _labelled(outcomes, "Vendor1 publishes") is CheckOutcome.PASSED

    @pytest.mark.parametrize(
        "document",
        [None, {"document": {"title": CSAF_REPORT_TITLE}}],
        ids=["plain-report", "csaf-report"],
    )
    def test_the_opening_passes_on_the_document_or_none(
        self, document: dict[str, JsonValue] | None
    ) -> None:
        """One submission call: the CSAF form attaches it, the plain form none."""
        state = story_state(REPORTER, VENDOR)
        report, offer, case = MagicMock(), MagicMock(), mock_case()

        with (
            patch.object(
                vendor_opening,
                "reporter_submits_report",
                return_value=(report, offer),
            ) as submits,
            patch.object(
                vendor_opening, "run_direct_path_rm_triage", return_value=case
            ),
            patch.object(vendor_opening, "wait_for_case_participants"),
            patch.object(vendor_opening, "await_reporter_case_replica"),
            patch.object(
                vendor_opening.as_VulnerabilityCase,
                "model_validate",
                return_value=case,
            ),
        ):
            vendor_opening.reporter_tells_the_vendor(
                state, csaf_document=document
            )

        submits.assert_called_once()
        kwargs = submits.call_args.kwargs
        assert kwargs["csaf_document"] is document
        assert set(kwargs) == {
            "receiver_client",
            "reporter",
            "receiver",
            "reporter_client",
            "csaf_document",
        }
        assert state.offer is offer


@pytest.mark.spec("DEMOMA-28-002")
@pytest.mark.parametrize(
    ("document", "report_name", "sent_name"),
    [
        (None, None, workflow_report._DEMO_REPORT_NAME),
        (None, "Stated name", "Stated name"),
        ({"document": {"title": CSAF_REPORT_TITLE}}, None, None),
        (
            {"document": {"title": CSAF_REPORT_TITLE}},
            "Stated name",
            "Stated name",
        ),
    ],
    ids=["plain", "plain-named", "csaf-unnamed", "csaf-named"],
)
def test_the_submission_states_a_name_only_when_it_has_one(
    document: dict[str, JsonValue] | None,
    report_name: str | None,
    sent_name: str | None,
) -> None:
    """With a document and no name the trigger names the report (CSAF-04-010)."""
    with (
        patch.object(workflow_report, "_provision_case_actor"),
        patch.object(
            ActorSession, "submit_report", autospec=True
        ) as submit_report,
        patch.object(
            workflow_report,
            "parse_submit_report_offer",
            return_value=(MagicMock(), MagicMock()),
        ),
        patch.object(workflow_report, "wait_for_report_submission_stored"),
        patch.object(workflow_report, "verify_receiver_verified_sender_key"),
    ):
        workflow_report.reporter_submits_report(
            receiver_client=MagicMock(),
            reporter=MagicMock(),
            receiver=MagicMock(),
            reporter_client=MagicMock(),
            report_name=report_name,
            csaf_document=document,
        )

    kwargs = submit_report.call_args.kwargs
    assert kwargs["csaf_document"] is document
    assert kwargs["report_name"] == sent_name
    assert kwargs["proposed_embargo_end_time"] is None


# ---------------------------------------------------------------------------
# The checks: M1 to M3
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-28-003")
class TestTheCaseStartsFromTheCsafReport:
    """The canonical case's name, summary and embargo are the document's."""

    @contextlib.contextmanager
    def _run(
        self, *, case: MagicMock, proposal: object
    ) -> Iterator[tuple[dict[str, CheckOutcome], dict[str, Any]]]:
        state = _state()
        state.report.id_ = "urn:test:report"
        state.offer.proposed_embargo = proposal
        state.case_actor_client.actor_id = "urn:test:case-actor"
        with (
            patch.object(demo, "required_participants_are_present") as m1,
            patch.object(
                demo, "verify_case_actor_holds_records", return_value=case
            ),
            patch.object(demo, "verify_reporter_terms_won") as won,
            _checks() as outcomes,
        ):
            demo.the_case_starts_from_the_csaf_report(state)
        yield (
            outcomes,
            {"m1": m1, "won": won, "client": state.case_actor_client},
        )

    def test_a_case_built_from_the_document_passes_every_check(self) -> None:
        case = _canonical_case()
        with self._run(case=case, proposal=_proposal()) as (outcomes, mocks):
            pass

        assert set(outcomes.values()) == {CheckOutcome.PASSED}, outcomes
        assert mocks["m1"].call_args.kwargs["check"].startswith("M1: ")
        won = mocks["won"]
        assert won.call_args.args == (
            mocks["client"],
            "urn:test:case-actor",
            case,
            "urn:test:csaf-proposal",
            _DISCLOSURE,
        )
        assert won.call_args.kwargs["default"] == VENDOR_DEFAULT_EMBARGO
        assert won.call_args.kwargs["revision_check"].startswith("M3: ")

    @pytest.mark.parametrize(
        "case",
        [
            _canonical_case(name="Remote Code Execution in Network Stack"),
            _canonical_case(summary="A different summary."),
        ],
        ids=["name-not-the-title", "summary-not-the-note"],
    )
    def test_a_case_not_filled_from_the_document_fails_m2(
        self, case: MagicMock
    ) -> None:
        with self._run(case=case, proposal=_proposal()) as (outcomes, _):
            pass

        assert _labelled(outcomes, "M2: ") is CheckOutcome.FAILED

    def test_an_offer_with_no_proposed_embargo_fails_m3(self) -> None:
        with self._run(case=_canonical_case(), proposal=None) as (
            outcomes,
            mocks,
        ):
            pass

        assert _labelled(outcomes, "M3: the Offer") is CheckOutcome.FAILED
        mocks["won"].assert_not_called()

    def test_terms_about_another_subject_fail_m3(self) -> None:
        with self._run(
            case=_canonical_case(), proposal=_proposal("urn:test:other")
        ) as (outcomes, mocks):
            pass

        assert _labelled(outcomes, "M3: the Offer") is CheckOutcome.FAILED
        mocks["won"].assert_not_called()

    def test_a_canonical_case_that_cannot_be_read_skips_m2_and_m3(
        self,
    ) -> None:
        state = _state()
        with (
            patch.object(demo, "required_participants_are_present"),
            patch.object(
                demo,
                "verify_case_actor_holds_records",
                side_effect=AssertionError("absent from the CaseActor"),
            ),
            patch.object(demo, "verify_reporter_terms_won") as won,
            _checks() as outcomes,
        ):
            demo.the_case_starts_from_the_csaf_report(state)

        won.assert_not_called()
        assert not any(label.startswith("M2") for label in outcomes)
        assert (
            _labelled(outcomes, "Dedicated case-actor container")
            is CheckOutcome.FAILED
        )
