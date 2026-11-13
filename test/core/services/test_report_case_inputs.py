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
"""The one mapping from a document's claims to the case inputs (CSAF-03)."""

from datetime import UTC, datetime, timedelta

import pytest

from vultron.core.models.report_claims import (
    CaseSplitDifference,
    ClaimedNote,
    ClaimedReference,
    ClaimedVulnerabilityId,
    ClaimOutcome,
    ReportClaims,
    VulnerabilityClaims,
)
from vultron.core.models.vulnerability_item import NoteCategory
from vultron.core.services.report_case_inputs import (
    StatedReportFields,
    case_inputs_from_claims,
    case_reference_from_claim,
    claims_signals,
    vulnerability_item_from_claims,
)

_NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
_LATER = _NOW + timedelta(days=30)
_SOONER = _NOW + timedelta(days=10)
_EARLIER = _NOW - timedelta(days=3)


def _claims(
    *vuls: VulnerabilityClaims,
    category: str = "csaf_vulnerability_report",
    name: str | None = "Overflow in the parser",
    summary: str | None = "A crafted file overflows the parser.",
    vendors: tuple[str, ...] = (),
) -> ReportClaims:
    return ReportClaims(
        document_category=category,
        name=name,
        summary=summary,
        vulnerabilities=list(vuls),
        known_affected_vendors=list(vendors),
    )


def test_unstated_name_and_summary_come_from_the_document() -> None:
    inputs = case_inputs_from_claims(_claims(), reference_time=_NOW)
    assert (inputs.name, inputs.summary) == (
        "Overflow in the parser",
        "A crafted file overflows the parser.",
    )
    assert inputs.outcomes == {
        "name": ClaimOutcome.APPLIED,
        "summary": ClaimOutcome.APPLIED,
    }


def test_stated_values_beat_the_document_and_mark_it_overridden() -> None:
    claims = _claims(VulnerabilityClaims(disclosure_date=_LATER))
    stated = StatedReportFields(
        name="Report name",
        summary="Report summary",
        proposed_embargo_end=_SOONER,
    )
    inputs = case_inputs_from_claims(
        claims, reference_time=_NOW, stated=stated
    )
    assert (inputs.name, inputs.summary, inputs.proposed_embargo_end) == (
        "Report name",
        "Report summary",
        _SOONER,
    )
    assert inputs.outcomes == {
        "name": ClaimOutcome.OVERRIDDEN,
        "summary": ClaimOutcome.OVERRIDDEN,
        "vulnerabilities[0].disclosure_date": ClaimOutcome.OVERRIDDEN,
    }


def test_the_earliest_future_disclosure_date_is_the_embargo_end() -> None:
    claims = _claims(
        VulnerabilityClaims(disclosure_date=_LATER),
        VulnerabilityClaims(disclosure_date=_SOONER),
    )
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert inputs.proposed_embargo_end == _SOONER
    assert inputs.embargo_eligible
    assert (
        inputs.outcomes["vulnerabilities[1].disclosure_date"]
        is ClaimOutcome.APPLIED
    )
    assert "vulnerabilities[0].disclosure_date" not in inputs.outcomes


@pytest.mark.parametrize("when", [_EARLIER, _NOW], ids=["before", "at"])
def test_a_disclosure_date_no_later_than_the_reference_time_sets_p(
    when: datetime,
) -> None:
    claims = _claims(VulnerabilityClaims(disclosure_date=when))
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert inputs.public
    assert inputs.proposed_embargo_end is None
    assert not inputs.embargo_eligible


def test_a_past_date_sets_p_even_beside_a_stated_embargo() -> None:
    claims = _claims(VulnerabilityClaims(disclosure_date=_EARLIER))
    inputs = case_inputs_from_claims(
        claims,
        reference_time=_NOW,
        stated=StatedReportFields(proposed_embargo_end=_LATER),
    )
    assert inputs.public
    assert (
        inputs.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.APPLIED
    )


@pytest.mark.parametrize(
    ("key", "x", "a"),
    [("P", True, False), ("A", False, True), ("N", False, False)],
    ids=["poc", "active", "none"],
)
def test_ssvc_exploitation_sets_x_or_a(key: str, x: bool, a: bool) -> None:
    claims = _claims(VulnerabilityClaims(exploitation=key))
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert (inputs.public, inputs.exploit_public, inputs.attacks_observed) == (
        False,
        x,
        a,
    )
    applied = "vulnerabilities[0].exploitation" in inputs.outcomes
    assert applied is (x or a)


def test_an_exploitation_date_sets_a() -> None:
    claims = _claims(
        VulnerabilityClaims(first_known_exploitation_dates=[_EARLIER])
    )
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert inputs.attacks_observed
    assert inputs.outcomes[
        "vulnerabilities[0].first_known_exploitation_dates[0]"
    ] is (ClaimOutcome.APPLIED)


def test_another_category_fills_nothing() -> None:
    claims = _claims(
        VulnerabilityClaims(disclosure_date=_EARLIER, exploitation="A"),
        category="csaf_security_advisory",
    )
    stated = StatedReportFields(name="Report name")
    inputs = case_inputs_from_claims(
        claims, reference_time=_NOW, stated=stated
    )
    assert not inputs.filled_from_document
    assert inputs.name == "Report name"
    assert inputs.summary is None
    assert inputs.embargo_eligible
    assert inputs.outcomes == {}


@pytest.mark.spec("CSAF-02-002")
def test_another_category_makes_no_items_or_references() -> None:
    claims = ReportClaims(
        document_category="csaf_security_advisory",
        references=[ClaimedReference(url="https://example.org/a")],
        vulnerabilities=[VulnerabilityClaims(cve="CVE-2026-0001")],
    )
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert (inputs.item_vulnerabilities, inputs.references) == ([], [])
    assert inputs.outcomes == {}


@pytest.mark.spec("CSAF-03-008", "CSAF-03-009")
def test_named_vulnerabilities_and_document_references_are_kept() -> None:
    named = VulnerabilityClaims(
        ids=[ClaimedVulnerabilityId(system_name="GHSA", text="GHSA-x")]
    )
    unnamed = VulnerabilityClaims(title="No identifier")
    reference = ClaimedReference(url="https://example.org/a")
    claims = ReportClaims(
        document_category="csaf_vulnerability_report",
        references=[reference],
        vulnerabilities=[unnamed, named],
    )
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert inputs.item_vulnerabilities == [named]
    assert inputs.references == [reference]
    assert inputs.outcomes == {
        "references[0]": ClaimOutcome.APPLIED,
        "vulnerabilities[1].ids[0]": ClaimOutcome.APPLIED,
    }


@pytest.mark.spec("CSAF-03-008", "CM-05-008")
def test_a_vulnerability_item_copies_the_identity_fields() -> None:
    vul = VulnerabilityClaims(
        cve="CVE-2026-0001",
        ids=[ClaimedVulnerabilityId(system_name="VU#", text="VU#1")],
        title="Overflow",
        notes=[
            ClaimedNote(
                category=NoteCategory.SUMMARY,
                text="It overflows.",
                audience="all",
            )
        ],
        references=[
            ClaimedReference(url="https://example.org/b", summary="Bulletin")
        ],
    )
    item = vulnerability_item_from_claims(vul, published=_NOW)
    assert (item.cve, item.title) == ("CVE-2026-0001", "Overflow")
    assert [(i.system_name, i.text) for i in item.ids] == [("VU#", "VU#1")]
    [note] = item.notes
    assert (note.category, note.text, note.title, note.audience) == (
        NoteCategory.SUMMARY,
        "It overflows.",
        None,
        "all",
    )
    [ref] = item.references
    assert not isinstance(ref, str)
    assert (ref.url.href, ref.name) == ("https://example.org/b", "Bulletin")
    assert item.published == ref.published == _NOW


@pytest.mark.spec("CSAF-03-008")
def test_a_vulnerability_with_no_identifier_makes_no_item() -> None:
    with pytest.raises(ValueError, match="no cve and no ids"):
        vulnerability_item_from_claims(
            VulnerabilityClaims(title="Unnamed"), published=_NOW
        )


@pytest.mark.spec("CSAF-03-009")
def test_a_case_reference_takes_the_url_and_summary() -> None:
    ref = case_reference_from_claim(
        ClaimedReference(
            url="https://example.org/c", summary="Write-up", category="self"
        ),
        published=_NOW,
    )
    assert (ref.url.href, ref.url.rel, ref.name) == (
        "https://example.org/c",
        [],
        "Write-up",
    )
    assert (
        case_reference_from_claim(
            ClaimedReference(url="https://example.org/d"), published=_NOW
        ).name
        is None
    )


def test_a_naive_reference_time_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        case_inputs_from_claims(
            _claims(), reference_time=_NOW.replace(tzinfo=None)
        )


def test_disagreeing_vulnerabilities_name_each_difference() -> None:
    claims = _claims(
        VulnerabilityClaims(disclosure_date=_EARLIER, exploitation="P"),
        VulnerabilityClaims(disclosure_date=_LATER),
    )
    split, _ = claims_signals(claims, reference_time=_NOW, receiver_name=None)
    assert split is not None
    assert split.differs_in == [
        CaseSplitDifference.PUBLIC_STATUS,
        CaseSplitDifference.EXPLOIT_PUBLIC,
        CaseSplitDifference.FUTURE_DISCLOSURE_DATE,
    ]


def test_agreeing_vulnerabilities_raise_no_split_signal() -> None:
    claims = _claims(
        VulnerabilityClaims(disclosure_date=_LATER, exploitation="A"),
        VulnerabilityClaims(
            disclosure_date=_LATER, first_known_exploitation_dates=[_EARLIER]
        ),
    )
    split, _ = claims_signals(claims, reference_time=_NOW, receiver_name=None)
    assert split is None


@pytest.mark.parametrize(
    ("vendors", "receiver", "expected"),
    [
        (("Vendor Inc",), "vendor inc ", None),
        (("Vendor Inc",), "Coordinator", ["Vendor Inc"]),
        (("Vendor Inc", "Other Co"), "Vendor Inc", ["Other Co"]),
        (("Vendor Inc", "Other Co"), None, ["Vendor Inc", "Other Co"]),
        ((), "Vendor Inc", None),
    ],
    ids=["only-self", "one-other", "several", "unnamed-receiver", "none"],
)
def test_candidate_parties_are_the_vendors_other_than_the_receiver(
    vendors: tuple[str, ...], receiver: str | None, expected: list[str] | None
) -> None:
    claims = _claims(vendors=vendors)
    _, parties = claims_signals(
        claims, reference_time=_NOW, receiver_name=receiver
    )
    assert (parties.vendors if parties else None) == expected


def test_no_future_date_is_applied_when_the_document_sets_x() -> None:
    claims = _claims(
        VulnerabilityClaims(disclosure_date=_LATER, exploitation="P")
    )
    inputs = case_inputs_from_claims(claims, reference_time=_NOW)
    assert inputs.proposed_embargo_end is None
    assert not inputs.embargo_eligible
    assert "vulnerabilities[0].disclosure_date" not in inputs.outcomes


def test_a_stated_end_is_not_taken_when_the_document_sets_x() -> None:
    """With X set the case takes no embargo, the stated one included, so the
    document's future date is neither applied nor overridden (EP-04-020)."""
    claims = _claims(
        VulnerabilityClaims(disclosure_date=_LATER, exploitation="P")
    )
    inputs = case_inputs_from_claims(
        claims,
        reference_time=_NOW,
        stated=StatedReportFields(proposed_embargo_end=_LATER),
    )
    assert inputs.proposed_embargo_end is None
    assert not inputs.embargo_eligible
    assert "vulnerabilities[0].disclosure_date" not in inputs.outcomes


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CSAF-03-008: the intake still copies a CSAF title to the item's "
    "`title`. Tracked by #6413.",
)
@pytest.mark.spec("CSAF-03-008")
def test_a_csaf_entrys_title_arrives_as_the_items_name() -> None:
    vul = VulnerabilityClaims(cve="CVE-2026-0001", title="Overflow")
    item = vulnerability_item_from_claims(vul, published=_NOW)
    assert item.name == "Overflow"
