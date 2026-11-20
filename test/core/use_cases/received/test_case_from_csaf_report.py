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
"""A case created from an initial CSAF report starts from what the report says.

Receive-path tests for CSAF-02-001 to CSAF-02-003, CSAF-03-001 to
CSAF-03-009 and CP-01-022 to CP-01-029.  The Vendor receives the Finder's
``Offer(VulnerabilityReport)``, converts its CSAF document into the
``caseInputs`` of its ``Create(CaseProposal)`` (CP-01-026) and marks what the
conversion used on its own claims record; a separate CASE_MANAGER, in its own
store, receives that sealed proposal and creates the case from those inputs
(CP-01-024).  ``_created_by_fallback`` takes the ``caseInputs`` off, so the
CASE_MANAGER fills the case from the CSAF document on the Offer the proposal
carries and keeps its own record of it (CP-01-025, CP-01-029).
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from test.core.use_cases.received._csaf_receipt import (
    RECEIVED_AT,
    REPORT_ID,
    VENDOR,
    CaseManager,
    Receipt,
    csaf,
    document,
)
from test.support.act_clock import clock_at
from test.support.act_runner import run_in_act, run_tree
from test.support.ledger import ledger_entries
from test.support.objects import make
from test.support.received import received_event
from test.support.report_proposal import proposal_nodes
from test.support.signing import resigned
from test.wire.csaf._documents import section, vulnerability_report_document
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.proposal import CASE_PROPOSAL_KEY
from vultron.core.models.actor import VultronOrganization, VultronService
from vultron.core.models.attached_document import AttachedDocument
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_proposal import CaseProposal
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.events.case import CreateCaseReceivedEvent
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_claims import ClaimOutcome
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.models.vulnerability_item import (
    NoteCategory,
    VulnerabilityItem,
)
from vultron.core.states.cs.states import CS_pxa
from vultron.core.states.em import EM
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

pytestmark = pytest.mark.usefixtures("case_actor_service_url")

_TITLE = "Buffer overflow in Example Widget"
_SUMMARY_NOTE = "A short summary."
_SOONER = "2027-01-15T00:00:00Z"
_LATER = "2027-03-01T00:00:00Z"
_PAST = "2026-10-01T00:00:00Z"


def _quiet_document(**vul: Any) -> dict[str, Any]:
    """A report document whose one vulnerability states only *vul*."""
    data = vulnerability_report_document()
    entry = data["vulnerabilities"][0]
    for key in (
        "disclosure_date",
        "metrics",
        "first_known_exploitation_dates",
    ):
        entry.pop(key)
    entry.update(vul)
    return data


def _ssvc(key: str) -> list[dict[str, Any]]:
    return [
        {
            "content": {
                "ssvc_v2": {
                    "schemaVersion": "2.0.0",
                    "timestamp": "2026-10-01T00:00:00Z",
                    "selections": [
                        {
                            "namespace": "ssvc",
                            "key": "E",
                            "version": "1.1.0",
                            "values": [{"key": key}],
                        }
                    ],
                }
            },
            "products": ["WIDGET-1"],
        }
    ]


def _created(receipt: Receipt) -> tuple[CaseManager, VulnerabilityCase]:
    """Deliver *receipt*'s proposal, as sent, to a separate CASE_MANAGER."""
    receipt.handle()
    manager = CaseManager()
    result = manager.receive(receipt.proposal_body())
    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    return manager, manager.case()


def _created_by_fallback(
    receipt: Receipt, at: datetime = RECEIVED_AT
) -> tuple[CaseManager, VulnerabilityCase]:
    """Deliver *receipt*'s proposal with no ``caseInputs``, so a separate
    CASE_MANAGER reads the carried Offer's document itself (CP-01-025)."""
    receipt.handle()
    manager = CaseManager()
    result = manager.receive(
        receipt.proposal_body_without_case_inputs(), at=at
    )
    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    return manager, manager.case()


def _embargo_end(manager: CaseManager, case: VulnerabilityCase) -> datetime:
    assert case.em_state is EM.ACTIVE
    return _stored_end(manager, str(case.active_embargo_id))


def _stored_end(manager: CaseManager, embargo_id: str) -> datetime:
    """The end of the embargo *manager* stores as *embargo_id*."""
    embargo = manager.dl.read(embargo_id)
    assert isinstance(embargo, EmbargoEvent)
    return embargo.end_time


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp).astimezone(UTC)


@pytest.mark.spec("CSAF-02-001", "CSAF-03-007")
def test_a_missing_name_and_summary_come_from_the_csaf_document() -> None:
    receipt = Receipt(csaf(_quiet_document()), report_name=None)

    manager, case = _created(receipt)

    assert (case.name, case.summary) == (_TITLE, _SUMMARY_NOTE)
    record = receipt.record()
    assert record.outcomes["name"] is ClaimOutcome.APPLIED
    assert record.outcomes["summary"] is ClaimOutcome.APPLIED
    assert manager.records() == []


@pytest.mark.spec("CSAF-03-007")
def test_the_description_note_is_the_summary_when_there_is_no_summary_note() -> (
    None
):
    data = _quiet_document()
    section(data, "document")["notes"] = [
        {"category": "description", "text": "A longer description."}
    ]
    receipt = Receipt(csaf(data), report_name=None)

    _, case = _created(receipt)

    assert case.summary == "A longer description."


@pytest.mark.spec("CSAF-03-006")
def test_a_case_starts_with_its_reports_name_and_summary() -> None:
    receipt = Receipt(
        report_name="Widget overflow", report_summary="It overflows."
    )

    _, case = _created(receipt)

    assert (case.name, case.summary) == ("Widget overflow", "It overflows.")


@pytest.mark.spec("CSAF-02-003")
def test_a_vultron_field_beats_the_csaf_value() -> None:
    proposed_end = _when(_LATER)
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER)),
        report_name="Widget overflow",
        proposed_embargo_end=proposed_end,
    )

    manager, case = _created_by_fallback(receipt)

    assert case.name == "Widget overflow"
    assert case.summary == _SUMMARY_NOTE
    assert _embargo_end(manager, case) == proposed_end
    assert receipt.record().outcomes["name"] is ClaimOutcome.OVERRIDDEN
    [record] = manager.records()
    assert record.outcomes["name"] is ClaimOutcome.OVERRIDDEN
    assert (
        record.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.OVERRIDDEN
    )


@pytest.mark.spec("CSAF-03-001")
def test_a_future_disclosure_date_proposes_the_embargo_end() -> None:
    receipt = Receipt(csaf(_quiet_document(disclosure_date=_SOONER)))

    manager, case = _created_by_fallback(receipt)

    assert _embargo_end(manager, case) == _when(_SOONER)
    [record] = manager.records()
    assert (
        record.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.APPLIED
    )


@pytest.mark.spec("CSAF-03-002")
def test_the_earliest_future_disclosure_date_wins() -> None:
    data = _quiet_document(disclosure_date=_LATER)
    second = dict(data["vulnerabilities"][0])
    second["cve"] = "CVE-2026-0002"
    second["disclosure_date"] = _SOONER
    data["vulnerabilities"].append(second)
    receipt = Receipt(csaf(data))

    manager, case = _created(receipt)

    assert _embargo_end(manager, case) == _when(_SOONER)


@pytest.mark.spec("CSAF-03-003")
def test_a_past_disclosure_date_states_the_vul_is_public() -> None:
    receipt = Receipt(csaf(_quiet_document(disclosure_date=_PAST)))

    _, case = _created(receipt)

    assert case.current_status.pxa.state is CS_pxa.Pxa
    assert case.em_state is EM.NONE
    assert case.active_embargo_id is None


@pytest.mark.spec("CSAF-03-004")
@pytest.mark.parametrize(
    ("key", "pxa"),
    [("P", CS_pxa.PXa), ("A", CS_pxa.pxA), ("N", CS_pxa.pxa)],
    ids=["poc", "active", "none"],
)
def test_ssvc_exploitation_poc_sets_x_and_active_sets_a(
    key: str, pxa: CS_pxa
) -> None:
    receipt = Receipt(csaf(_quiet_document(metrics=_ssvc(key))))

    _, case = _created(receipt)

    # An exploit made public makes the public aware (pX to PX).
    assert case.current_status.pxa.state is pxa
    assert (case.em_state is EM.NONE) is (key != "N")


@pytest.mark.spec("CSAF-03-005")
def test_a_first_known_exploitation_date_sets_a() -> None:
    entry = {
        "date": "2026-10-02T00:00:00Z",
        "exploitation_date": "2026-09-30T00:00:00Z",
    }
    receipt = Receipt(
        csaf(_quiet_document(first_known_exploitation_dates=[entry]))
    )

    _, case = _created(receipt)

    assert case.current_status.pxa.state is CS_pxa.pxA
    assert case.em_state is EM.NONE


@pytest.mark.spec("CSAF-02-001", "CSAF-04-004", "CP-01-028")
def test_the_side_that_converts_the_document_marks_what_it_used() -> None:
    """The receiver converts the document, so its record says what the
    proposal took, and the CASE_MANAGER, reading no document, keeps none."""
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER)), report_name=None
    )

    manager, _ = _created(receipt)

    outcomes = receipt.record().outcomes
    assert outcomes["name"] is ClaimOutcome.APPLIED
    assert (
        outcomes["vulnerabilities[0].disclosure_date"] is ClaimOutcome.APPLIED
    )
    assert outcomes["distribution_label"] is ClaimOutcome.DISPLAY_ONLY
    assert manager.records() == []


@pytest.mark.spec("CSAF-04-004", "CP-01-023")
def test_the_receiver_marks_the_date_its_proposal_carries() -> None:
    """The receiver judges no date, so its record marks the disclosure date
    by what its proposal carries, even when the Offer's own proposed end or
    the document's X will decide the embargo at the CASE_MANAGER."""
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER, metrics=_ssvc("P"))),
        proposed_embargo_end=_when(_LATER),
    )

    manager, case = _created(receipt)

    outcomes = receipt.record().outcomes
    assert (
        outcomes["vulnerabilities[0].disclosure_date"] is ClaimOutcome.APPLIED
    )
    assert outcomes["vulnerabilities[0].exploitation"] is ClaimOutcome.APPLIED
    # X set: the case starts with no embargo (EP-04-020).
    assert case.current_status.pxa.state is CS_pxa.PXa
    assert case.em_state is EM.NONE
    assert manager.records() == []


@pytest.mark.spec("CSAF-02-001", "CSAF-04-004")
def test_the_case_manager_marks_what_it_read_when_no_inputs_are_stated() -> (
    None
):
    """Without ``caseInputs`` the CASE_MANAGER reads the document itself and
    keeps its own record, keyed on the case it filled."""
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER)), report_name=None
    )

    manager, _ = _created_by_fallback(receipt)

    [record] = manager.records()
    assert record.reading == receipt.record().reading
    assert record.case_id == manager.case().id_
    assert record.outcomes["name"] is ClaimOutcome.APPLIED


@pytest.mark.spec("CSAF-02-002")
def test_a_document_of_another_category_changes_no_case_data() -> None:
    data = _quiet_document(disclosure_date=_PAST, metrics=_ssvc("A"))
    section(data, "document")["category"] = "csaf_security_advisory"
    receipt = Receipt(csaf(data), report_name=None)

    manager, case = _created(receipt)

    assert case.name is None
    assert case.current_status.pxa.state is CS_pxa.pxa
    assert case.em_state is EM.ACTIVE
    assert (case.vulnerability_items, case.case_references) == ([], [])
    [record] = manager.records()
    assert set(record.outcomes.values()) == {ClaimOutcome.DISPLAY_ONLY}


@pytest.mark.spec("CSAF-02-002")
def test_csaf_on_a_report_that_already_has_a_case_changes_no_case_data() -> (
    None
):
    first = Receipt(report_name="Widget overflow")
    manager, case = _created(first)
    later = Receipt(
        csaf(_quiet_document(disclosure_date=_PAST, metrics=_ssvc("A"))),
        report_name=None,
    )
    later.handle()

    result = manager.receive(later.proposal_body())

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    unchanged = manager.case()
    assert unchanged.id_ == case.id_
    assert unchanged.name == "Widget overflow"
    assert unchanged.current_status.pxa.state is CS_pxa.pxa
    assert unchanged.em_state is case.em_state
    assert unchanged.vulnerability_items == case.vulnerability_items == []
    assert unchanged.case_references == case.case_references == []
    # Nor stores an item or reference the case does not list.
    assert list(manager.dl.list_objects("VulnerabilityItem")) == []
    assert list(manager.dl.list_objects("CaseReference")) == []
    assert manager.records() == []


def test_the_first_vulnerability_report_document_fills_the_case() -> None:
    other = _quiet_document(disclosure_date=_PAST)
    section(other, "document")["title"] = "A second account"
    receipt = Receipt(
        csaf(_quiet_document()),
        document(json.dumps(other), f"{REPORT_ID}/csaf-2"),
        report_name=None,
    )

    _, case = _created(receipt)

    assert case.name == _TITLE
    assert case.current_status.pxa.state is CS_pxa.pxa
    second = next(
        r for r in receipt.records() if r.reading.claims.name != _TITLE
    )
    assert set(second.outcomes.values()) == {ClaimOutcome.DISPLAY_ONLY}


@pytest.mark.spec("CSAF-03-001", "CSAF-03-003")
def test_the_reference_time_is_the_case_managers_receipt_of_the_proposal() -> (
    None
):
    """A date between the receiver's receipt and the CASE_MANAGER's is past.

    Both receipts are in the past: the new case is stamped at the act's
    instant while its ``Create`` is still stamped by the clock (ADR-0176
    slice 4), so an act instant ahead of the clock would date the case after
    its genesis entry (CLP-14-013).
    """
    between = RECEIVED_AT + timedelta(hours=12)
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=between.isoformat()))
    )
    later = between + timedelta(days=1)

    manager, case = _created_by_fallback(receipt, at=later)

    assert case.current_status.pxa.state is CS_pxa.Pxa
    assert case.em_state is EM.NONE
    [record] = manager.records()
    assert record.received_at == later
    # The new case is stamped at the act's instant (ADR-0176).
    assert case.published == later


@pytest.mark.spec("CSAF-02-003")
def test_an_offer_embargo_that_has_run_out_sets_no_csaf_date_aside() -> None:
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_SOONER)),
        proposed_embargo_end=_when(_PAST),
    )

    manager, case = _created_by_fallback(receipt)

    assert _embargo_end(manager, case) == _when(_SOONER)
    [record] = manager.records()
    assert (
        record.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.APPLIED
    )


@pytest.mark.spec("CSAF-04-004")
def test_two_cases_from_one_report_each_keep_their_record() -> None:
    """A second proposer gets a case of its own (CBT-06-002), filled and
    recorded apart from the first."""
    manager = CaseManager()
    document_ = csaf(_quiet_document(disclosure_date=_SOONER))
    for receiver in (VENDOR, "https://coordinator.example.org/actors/coord"):
        receipt = Receipt(document_, receiver_id=receiver, report_name=None)
        receipt.handle()
        result = manager.receive(receipt.proposal_body_without_case_inputs())
        assert result.disposition is HandlerDisposition.APPLIED, result.reason

    cases = manager.cases()
    assert len(cases) == 2
    assert {c.name for c in cases} == {_TITLE}
    records = manager.records()
    assert {r.case_id for r in records} == {c.id_ for c in cases}
    for record in records:
        assert record.outcomes["name"] is ClaimOutcome.APPLIED


@pytest.mark.spec("CSAF-02-002")
def test_csaf_on_the_proposal_itself_changes_no_case_data() -> None:
    """A proposal with no carried Offer: the document on its own report is
    on another activity than the initial Offer, so it fills nothing."""
    report = make(
        VulnerabilityReport,
        id_=REPORT_ID,
        name="Widget overflow",
        content="The widget overflows its buffer.",
        attachment=[
            csaf(_quiet_document(disclosure_date=_PAST, metrics=_ssvc("A")))
        ],
    )
    manager = CaseManager()
    proposal = make(
        as_CaseProposal,
        attributed_to=VENDOR,
        object_=report,
        target=manager.actor_id,
    )
    activity = make(
        as_Create,
        actor=make(VultronOrganization, id_=VENDOR),
        object_=proposal,
        to=[manager.actor_id],
    )

    result = manager.receive_activity(activity)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    case = manager.case()
    assert case.name == "Widget overflow"
    assert case.current_status.pxa.state is CS_pxa.pxa
    assert case.em_state is EM.ACTIVE
    assert manager.records() == []


@pytest.mark.spec("CSAF-03-001")
def test_a_csaf_embargo_end_does_not_reach_the_next_proposal() -> None:
    """The CSAF date seeded as one proposal's terms is that execution's
    alone: a later proposal for another report, with no document and no
    ``proposedEmbargo``, states no terms (BT-09)."""
    manager = CaseManager()
    first = Receipt(csaf(_quiet_document(disclosure_date=_SOONER)))
    first.handle()
    result = manager.receive(first.proposal_body())
    assert result.disposition is HandlerDisposition.APPLIED, result.reason

    second = Receipt(
        report_id="https://finder.example.org/reports/gadget",
        receiver_id="https://coordinator.example.org/actors/coord",
    )
    second.handle()
    result = manager.receive(second.proposal_body())

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    [case] = [
        c
        for c in manager.cases()
        if second.report_id
        in {
            r if isinstance(r, str) else r.id_ for r in c.vulnerability_reports
        }
    ]
    embargo = manager.dl.read(str(case.active_embargo_id))
    assert not (
        isinstance(embargo, EmbargoEvent)
        and embargo.end_time == _when(_SOONER)
    )


_BULLETIN = "https://vendor.example.org/bulletins/17"
_WRITE_UP = "https://reporter.example.org/widget"


def _items(
    manager: CaseManager, case: VulnerabilityCase
) -> list[VulnerabilityItem]:
    """The case's vulnerability items, each read from the store by its id."""
    items = [manager.dl.read(str(ref)) for ref in case.vulnerability_items]
    assert all(isinstance(item, VulnerabilityItem) for item in items), items
    return [item for item in items if isinstance(item, VulnerabilityItem)]


def _references(
    manager: CaseManager, case: VulnerabilityCase
) -> list[CaseReference]:
    """The case's references, each read from the store by its id."""
    refs = [manager.dl.read(str(ref)) for ref in case.case_references]
    assert all(isinstance(ref, CaseReference) for ref in refs), refs
    return [ref for ref in refs if isinstance(ref, CaseReference)]


def _two_vulnerabilities() -> dict[str, Any]:
    """A report document with a second vulnerability, named only by an id."""
    data = _quiet_document()
    data["vulnerabilities"].append(
        {
            "ids": [{"system_name": "VU#", "text": "VU#123456"}],
            "title": "Widget crash",
            "references": [{"url": "https://cert.example.org/vu/123456"}],
        }
    )
    return data


@pytest.mark.spec("CSAF-03-008", "CM-05-008", "CM-05-009")
def test_each_csaf_vulnerability_becomes_a_vulnerability_item() -> None:
    receipt = Receipt(csaf(_two_vulnerabilities()))

    manager, case = _created(receipt)

    first, second = _items(manager, case)
    # The CSAF ``cve`` is the item's first ``ids`` entry (CM-05-018).
    assert [(i.system_name, i.identifier) for i in first.ids] == [
        ("CVE", "CVE-2026-0001"),
        ("Example tracker", "EX-17"),
    ]
    assert first.name == "Widget overflow"
    [note] = first.vul_notes
    assert (note.category, note.content, note.name) == (
        NoteCategory.DESCRIPTION,
        "The widget overflows its buffer.",
        "What goes wrong",
    )
    [first_ref] = first.references
    assert isinstance(first_ref, CaseReference)
    assert (first_ref.url.href, first_ref.name) == (
        _BULLETIN,
        "The vendor's bulletin",
    )
    # An identifier is copied as written, never read as a CVE (CM-05-008).
    assert [(i.system_name, i.identifier) for i in second.ids] == [
        ("VU#", "VU#123456")
    ]
    assert second.name == "Widget crash"
    # One act, one instant: no clock is read below its edge (ADR-0176).
    assert {first.published, second.published, first_ref.published} == {
        case.published
    }
    record = receipt.record()
    for path in (
        "vulnerabilities[0].cve",
        "vulnerabilities[0].ids[0]",
        "vulnerabilities[0].title",
        "vulnerabilities[0].notes[0]",
        "vulnerabilities[0].references[0]",
        "vulnerabilities[1].ids[0]",
    ):
        assert record.outcomes[path] is ClaimOutcome.APPLIED, path


@pytest.mark.spec("CSAF-03-008")
def test_a_vulnerability_with_no_cve_and_no_ids_makes_no_item() -> None:
    data = _quiet_document()
    data["vulnerabilities"].append({"title": "An unnamed flaw"})
    receipt = Receipt(csaf(data))

    manager, case = _created(receipt)

    [item] = _items(manager, case)
    assert ("CVE", "CVE-2026-0001") in [
        (i.system_name, i.identifier) for i in item.ids
    ]
    record = receipt.record()
    assert (
        record.outcomes["vulnerabilities[1].title"]
        is ClaimOutcome.DISPLAY_ONLY
    )


@pytest.mark.spec("CSAF-03-009", "CM-05-004", "CM-05-005")
def test_each_csaf_reference_becomes_a_case_reference() -> None:
    data = _two_vulnerabilities()
    data["document"]["references"].append(
        {"url": "https://reporter.example.org/widget/poc", "category": "self"}
    )
    receipt = Receipt(csaf(data))

    manager, case = _created(receipt)

    refs = _references(manager, case)
    assert [(r.url.href, r.name, r.url.rel) for r in refs] == [
        (_WRITE_UP, "The reporter's write-up", []),
        ("https://reporter.example.org/widget/poc", None, []),
    ]
    # A vulnerability's own references stay on its item, not on the case.
    assert _BULLETIN not in {r.url.href for r in refs}
    record = receipt.record()
    assert record.outcomes["references[0]"] is ClaimOutcome.APPLIED
    assert record.outcomes["references[1]"] is ClaimOutcome.APPLIED


@pytest.mark.spec("CSAF-03-008", "CSAF-03-009", "CLP-07-013")
def test_the_case_create_carries_the_items_and_references_inline() -> None:
    """The case's creation is the act that states its items and references,
    so its ``Create`` carries them in full, and the owner's replica reads
    them from it rather than from ids it cannot resolve."""
    receipt = Receipt(csaf(_two_vulnerabilities()))
    manager, case = _created(receipt)

    activity = parse_activity(manager.case_create_body())

    assert isinstance(activity, as_Create)
    carried = activity.object_
    assert isinstance(carried, VulnerabilityCase)
    assert carried.vulnerability_items == _items(manager, case)
    assert carried.case_references == _references(manager, case)


@pytest.mark.spec("CLP-07-021", "CSAF-03-008", "CSAF-03-009")
def test_each_item_and_reference_is_an_add_entry_after_the_genesis_entry() -> (
    None
):
    """Each record the creation wrote is one Add carrying it in full, with
    the case as its target, so a replica lists it as the entry states."""
    receipt = Receipt(csaf(_two_vulnerabilities()))
    manager, case = _created(receipt)

    entries = ledger_entries(manager.dl, case.id_)
    kinds = [entry.semantic_type for entry in entries]
    assert kinds[0] == "create_case"
    added = [
        entry
        for entry in entries
        if entry.semantic_type
        in ("add_vulnerability_item_to_case", "add_case_reference_to_case")
    ]
    items, references = _items(manager, case), _references(manager, case)
    assert len(items) == 2 and references
    assert [entry.semantic_type for entry in added] == [
        *(["add_vulnerability_item_to_case"] * len(items)),
        *(["add_case_reference_to_case"] * len(references)),
    ]
    expected = [record.id_ for record in (*items, *references)]
    for entry, object_id in zip(added, expected, strict=True):
        snapshot = entry.payload_snapshot
        assert snapshot["type"] == "Add"
        assert snapshot["target"] == case.id_
        assert isinstance(snapshot["object"], dict)
        assert snapshot["object"]["id"] == object_id
    assert "create_vulnerability_item" not in kinds


@pytest.mark.spec("CSAF-03-008", "CSAF-03-009", "AKM-02-004")
def test_the_owner_replica_holds_the_items_and_references_it_was_sent() -> (
    None
):
    """The owner seeds its replica from the Create, so its copy of the case
    holds the items and references the CASE_MANAGER stored (AKM-02-004)."""
    receipt = Receipt(csaf(_two_vulnerabilities()))
    manager, case = _created(receipt)
    event = received_event(
        parse_activity(manager.case_create_body()),
        receiving_actor_id=VENDOR,
    )
    assert isinstance(event, CreateCaseReceivedEvent)

    with clock_at(RECEIVED_AT):
        result = run_in_act(
            CreateCaseReceivedUseCase(
                receipt.dl,
                event,
                trigger_activity=TriggerActivityAdapter(receipt.dl),
            ),
            at=RECEIVED_AT,
        )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    replica = receipt.dl.read(case.id_)
    assert isinstance(replica, VulnerabilityCase)
    assert replica.vulnerability_items == _items(manager, case)
    assert replica.case_references == _references(manager, case)


@pytest.mark.spec("CSAF-03-009")
def test_a_failed_reference_write_creates_no_case() -> None:
    """The items and references are written in the creation act, so one
    that cannot be written leaves no case and no item behind (ADR-0146)."""
    receipt = Receipt(csaf(_two_vulnerabilities()))
    receipt.handle()
    manager = CaseManager()
    create = manager.dl.create

    def refuse_references(obj: Any) -> None:
        if obj.type_ == "CaseReference":
            raise ValueError("refused for the test")
        create(obj)

    with patch.object(manager.dl, "create", side_effect=refuse_references):
        result = manager.receive(receipt.proposal_body())

    assert result.disposition is not HandlerDisposition.APPLIED
    assert manager.cases() == []
    assert manager.dl.list_objects("VulnerabilityItem") == []


# ---------------------------------------------------------------------------
# A proposal that states its case inputs (CP-01-022 to CP-01-026)
# ---------------------------------------------------------------------------

_OWNER_ADVISORY = "https://vendor.example.org/advisories/widget"


def _owner_inputs(**changes: Any) -> dict[str, Any]:
    """``caseInputs`` as the case owner states them, in their wire form."""
    inputs: dict[str, Any] = {
        "name": "Owner's name for the case",
        "summary": "Owner's summary.",
        "exploitPublic": False,
        "attacksObserved": False,
        "proposedItems": [
            {
                "ids": [{"systemName": "CVE", "identifier": "CVE-2026-9999"}],
                "name": "Owner's item",
                "referenceLinks": [
                    {"type": "Link", "href": _OWNER_ADVISORY, "name": "Adv"}
                ],
            }
        ],
        "referenceLinks": [{"type": "Link", "href": _BULLETIN}],
    }
    inputs.update(changes)
    return inputs


def _with_inputs(receipt: Receipt, inputs: dict[str, Any]) -> dict[str, Any]:
    """*receipt*'s sent proposal, with *inputs* stated as its caseInputs."""
    receipt.handle()

    def state(body: dict[str, Any]) -> None:
        body["object"]["caseInputs"] = inputs

    return resigned(receipt.proposal_body(), alter=state)


def _created_from(
    body: dict[str, Any], at: datetime | None = None
) -> tuple[CaseManager, VulnerabilityCase]:
    manager = CaseManager()
    result = (
        manager.receive(body) if at is None else manager.receive(body, at=at)
    )
    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    return manager, manager.case()


def _noisy_document() -> dict[str, Any]:
    """A document that states P/X/A, a date, items and references."""
    data = _two_vulnerabilities()
    entry = data["vulnerabilities"][0]
    entry["disclosure_date"] = _SOONER
    entry["metrics"] = _ssvc("A")
    return data


@pytest.mark.spec("CP-01-022", "CP-01-024", "CP-01-028")
def test_a_case_is_built_from_the_case_inputs_a_proposal_states() -> None:
    """The case takes the owner's inputs, and no document is read: no claims
    record is written and nothing of the document reaches the case."""
    body = _with_inputs(
        Receipt(csaf(_noisy_document()), report_name=None),
        _owner_inputs(disclosureDate=_LATER),
    )

    manager, case = _created_from(body)

    assert (case.name, case.summary) == (
        "Owner's name for the case",
        "Owner's summary.",
    )
    assert case.current_status.pxa.state is CS_pxa.pxa
    [item] = _items(manager, case)
    assert [i.identifier for i in item.ids] == ["CVE-2026-9999"]
    assert item.name == "Owner's item"
    [ref] = item.references
    assert isinstance(ref, CaseReference)
    assert (ref.url.href, ref.name) == (_OWNER_ADVISORY, "Adv")
    [case_ref] = _references(manager, case)
    assert case_ref.url.href == _BULLETIN
    assert _embargo_end(manager, case) == _when(_LATER)
    assert manager.records() == []


@pytest.mark.spec("CP-01-024")
def test_emptied_inputs_are_never_refilled_from_the_document() -> None:
    """All or nothing: an empty item list and false X and A are the owner's
    word, though the document states items and attacks."""
    body = _with_inputs(
        Receipt(csaf(_noisy_document())),
        _owner_inputs(proposedItems=[], referenceLinks=[]),
    )

    manager, case = _created_from(body)

    assert (case.vulnerability_items, case.case_references) == ([], [])
    assert case.current_status.pxa.state is CS_pxa.pxa
    assert manager.records() == []


@pytest.mark.spec("CP-01-024", "EP-04-020")
def test_stated_x_or_a_starts_the_case_with_no_embargo() -> None:
    body = _with_inputs(
        Receipt(), _owner_inputs(attacksObserved=True, disclosureDate=_LATER)
    )

    _, case = _created_from(body)

    assert case.current_status.pxa.state is CS_pxa.pxA
    assert case.em_state is EM.NONE


@pytest.mark.spec("CP-01-023", "CSAF-03-003")
def test_a_stated_disclosure_date_that_has_passed_makes_the_case_public() -> (
    None
):
    body = _with_inputs(Receipt(), _owner_inputs(disclosureDate=_PAST))

    _, case = _created_from(body)

    assert case.current_status.pxa.state is CS_pxa.Pxa
    assert case.em_state is EM.NONE


@pytest.mark.spec("CP-01-023", "CSAF-03-001")
def test_the_stated_date_is_judged_when_the_case_is_created() -> None:
    """A date still ahead at the receiver's receipt but passed by the time
    the CASE_MANAGER creates the case makes the case public."""
    body = _with_inputs(Receipt(), _owner_inputs(disclosureDate=_SOONER))

    _, case = _created_from(body, at=_when(_SOONER) + timedelta(days=1))

    assert case.current_status.pxa.state is CS_pxa.Pxa
    assert case.em_state is EM.NONE


@pytest.mark.spec("CP-01-021", "CSAF-02-003")
def test_the_offers_proposed_embargo_beats_the_stated_date() -> None:
    """The Offer's end wins even when the stated date is earlier."""
    proposed_end = _when(_LATER)
    body = _with_inputs(
        Receipt(proposed_embargo_end=proposed_end),
        _owner_inputs(disclosureDate=_SOONER),
    )

    manager, case = _created_from(body)

    assert _embargo_end(manager, case) == proposed_end


def _owner_with_default(receipt: Receipt, days: int) -> Receipt:
    """*receipt*'s receiver, publishing an actor default of *days* (EP-01-001)."""
    receipt.dl.save(
        make(
            VultronService,
            id_=VENDOR,
            embargo_policy=make(
                EmbargoPolicy,
                id_=EmbargoPolicy.build_id(VENDOR),
                attributed_to=VENDOR,
                preferred_duration=timedelta(days=days),
            ),
        )
    )
    return receipt


@pytest.mark.spec("CP-01-024", "EP-04-003", "EP-04-016")
@pytest.mark.parametrize(
    ("default_days", "date", "active_end", "pending_end"),
    [
        (30, _LATER, RECEIVED_AT + timedelta(days=30), _when(_LATER)),
        (365, _SOONER, _when(_SOONER), RECEIVED_AT + timedelta(days=365)),
    ],
    ids=["default-shorter", "date-shorter"],
)
def test_a_stated_date_is_weighed_against_the_owners_actor_default(
    default_days: int, date: str, active_end: datetime, pending_end: datetime
) -> None:
    """The stated date is the Reporter's proposal: the shorter of it and the
    owner's actor default becomes active, the longer a pending revision."""
    receipt = _owner_with_default(Receipt(), days=default_days)

    manager, case = _created_from(
        _with_inputs(receipt, _owner_inputs(disclosureDate=date))
    )

    assert case.em_state is EM.REVISE
    assert _stored_end(manager, str(case.active_embargo_id)) == active_end
    assert [
        _stored_end(manager, revision_id)
        for revision_id in case.pending_embargo_proposal_index
    ] == [pending_end]


@pytest.mark.spec("CP-01-024")
def test_empty_case_inputs_give_a_case_with_nothing_the_owner_left_out() -> (
    None
):
    """All or nothing: inputs that state no name leave the case unnamed, even
    though the report and its document name it."""
    body = _with_inputs(
        Receipt(csaf(_quiet_document()), report_name="Widget overflow"), {}
    )

    manager, case = _created_from(body)

    assert (case.name, case.summary) == (None, None)
    assert case.vulnerability_items == []
    assert manager.records() == []


@pytest.mark.spec("CP-01-025", "CP-01-029")
def test_a_proposal_with_no_case_inputs_is_filled_from_the_document() -> None:
    """The CASE_MANAGER's fallback: it reads the carried Offer's document and
    records what each claimed value became."""
    receipt = Receipt(csaf(_quiet_document(disclosure_date=_SOONER)))

    manager, case = _created_by_fallback(receipt)

    assert case.name == "Widget overflow"
    assert _embargo_end(manager, case) == _when(_SOONER)
    [record] = manager.records()
    assert (
        record.outcomes["vulnerabilities[0].disclosure_date"]
        is ClaimOutcome.APPLIED
    )
    assert record.outcomes["name"] is ClaimOutcome.OVERRIDDEN


@pytest.mark.spec("CP-01-026", "CP-01-023", "CP-01-027")
def test_the_receiver_states_the_case_inputs_of_a_csaf_report() -> None:
    """The proposal carries the document's inputs, the disclosure date as
    the document states it though it has passed, and no P."""
    receipt = Receipt(
        csaf(_quiet_document(disclosure_date=_PAST, metrics=_ssvc("P"))),
        report_name=None,
    )
    receipt.handle()

    inputs = receipt.proposal_body()["object"]["caseInputs"]

    assert (inputs["name"], inputs["summary"]) == (_TITLE, _SUMMARY_NOTE)
    assert inputs["exploitPublic"] is True
    assert inputs["attacksObserved"] is False
    assert datetime.fromisoformat(inputs["disclosureDate"]) == _when(_PAST)
    assert not {"public", "pxa"} & set(inputs)
    [item] = inputs["proposedItems"]
    assert "id" not in item


@pytest.mark.spec("CP-01-026")
@pytest.mark.parametrize(
    "attachments",
    [(), (document("not a CSAF document"),)],
    ids=["no-document", "not-csaf"],
)
def test_a_report_with_no_csaf_report_document_sends_no_case_inputs(
    attachments: tuple[AttachedDocument, ...],
) -> None:
    receipt = Receipt(*attachments)
    receipt.handle()

    assert "caseInputs" not in receipt.proposal_body()["object"]


@pytest.mark.spec("CP-01-026", "CSAF-02-002")
def test_a_document_of_another_category_sends_no_case_inputs() -> None:
    data = _quiet_document(disclosure_date=_SOONER)
    section(data, "document")["category"] = "csaf_security_advisory"
    receipt = Receipt(csaf(data))
    receipt.handle()

    assert "caseInputs" not in receipt.proposal_body()["object"]
    assert set(receipt.record().outcomes.values()) == {
        ClaimOutcome.DISPLAY_ONLY
    }


class _OwnerEdits(py_trees.behaviour.Behaviour):
    """The receiver changes its proposal between conversion and send: it
    renames the case and drops the item named *dropped*."""

    def __init__(self, name: str, dropped: str) -> None:
        super().__init__(name="OwnerEdits")
        self._name = name
        self._dropped = dropped
        self._board = self.attach_blackboard_client(name="OwnerEdits")
        self._board.register_key(
            key=f"/{CASE_PROPOSAL_KEY}", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        proposal = self._board.get(f"/{CASE_PROPOSAL_KEY}")
        assert isinstance(proposal, CaseProposal)
        inputs = proposal.case_inputs
        assert inputs is not None
        edited = proposal.model_copy()
        edited.case_inputs = inputs.model_copy(
            update={
                "name": self._name,
                "proposed_items": [
                    item
                    for item in inputs.proposed_items
                    if item.name != self._dropped
                ],
            }
        )
        self._board.set(f"/{CASE_PROPOSAL_KEY}", edited)
        return Status.SUCCESS


@pytest.mark.spec("CP-01-026")
def test_the_receiver_may_change_its_proposal_before_it_is_sent() -> None:
    receipt = Receipt(csaf(_two_vulnerabilities()), report_name=None)
    # Keep the report and its claims record, and propose nothing yet.
    receipt.handle(actor_config=ActorConfig(auto_create_case=False))
    assert receipt.sent_bodies() == []
    tree = proposal_nodes(
        REPORT_ID,
        readings=receipt.event.claims_readings,
        between=[_OwnerEdits("Owner's name", dropped="Widget crash")],
    )
    bridge = BTBridge(
        datalayer=receipt.dl,
        trigger_activity=TriggerActivityAdapter(receipt.dl),
    )

    result = run_tree(bridge, tree=tree, actor_id=VENDOR, at=RECEIVED_AT)

    assert result.status is Status.SUCCESS, result.feedback_message
    inputs = receipt.proposal_body()["object"]["caseInputs"]
    assert inputs["name"] == "Owner's name"
    assert [i["name"] for i in inputs["proposedItems"]] == ["Widget overflow"]
    # The record says what the conversion took, marked once the proposal
    # is sent; the owner's later change is its own (CSAF-04-004).
    assert receipt.record().outcomes["name"] is ClaimOutcome.APPLIED
    manager, case = _created_from(receipt.proposal_body())
    assert case.name == "Owner's name"
    assert [item.name for item in _items(manager, case)] == ["Widget overflow"]


@pytest.mark.spec("CP-01-024", "CP-01-026", "CP-01-028", "CSAF-04-005")
def test_a_csaf_report_reaches_a_separate_case_manager_as_case_inputs() -> (
    None
):
    """Two actors: the case takes the document's name, summary, items,
    references and embargo end from the proposal's ``caseInputs``, and only
    the receiver holds a claims record."""
    data = _two_vulnerabilities()
    data["vulnerabilities"][0]["disclosure_date"] = _SOONER
    receipt = Receipt(csaf(data), report_name=None)

    manager, case = _created(receipt)

    assert "caseInputs" in receipt.proposal_body()["object"]
    assert (case.name, case.summary) == (_TITLE, _SUMMARY_NOTE)
    assert [item.name for item in _items(manager, case)] == [
        "Widget overflow",
        "Widget crash",
    ]
    assert [r.url.href for r in _references(manager, case)] == [_WRITE_UP]
    assert _embargo_end(manager, case) == _when(_SOONER)
    assert manager.records() == []
    assert receipt.record().case_id is None
    # The receiver's record is its own: no sealed body carries it.
    sent = json.dumps(receipt.sent_bodies())
    assert "ReportClaimsRecord" not in sent
    assert "display-only" not in sent
