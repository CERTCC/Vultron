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

"""Tests for SqliteDataLayer nested-object dehydration, rehydration, and hydrate().

Covers: dehydration (object_ stored as ID string), rehydration via dl.read(),
TestRehydrateFields (_rehydrate_fields expansion), and hydrate() for list fields.
Fixtures (dl) come from conftest.
"""

from vultron.wire.as2.factories import rm_submit_report_activity

# ---------------------------------------------------------------------------
# Nested-object dehydration integration tests
# ---------------------------------------------------------------------------


def test_activity_with_nested_object_stores_id_reference_not_inline_copy(dl):
    """Storing an activity with a nested object writes only the nested ID."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Test CVE",
        content="A critical vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    dl.create(report)
    dl.create(offer)

    raw = dl.get(offer.type_, offer.id_)
    assert raw is not None
    stored_object_field = raw["data_"]["object_"]
    assert isinstance(
        stored_object_field, str
    ), f"Expected object_ to be stored as ID string, got {type(stored_object_field)}"
    assert stored_object_field == report.id_


def test_activity_nested_object_retrievable_separately_after_dehydration(dl):
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Test CVE 2",
        content="Another vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    dl.create(report)
    dl.create(offer)

    retrieved_report = dl.read(report.id_)
    assert retrieved_report is not None
    assert retrieved_report.id_ == report.id_  # type: ignore[union-attr]


def test_reading_activity_back_yields_expanded_nested_object(dl):
    """After DL-REHYDRATE, dl.read() expands dehydrated object_ fields.

    Previously ``dl.read()`` returned a string ID for the nested ``object_``
    field; after the rehydration pipeline the full typed object is returned.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Test CVE 3",
        content="Yet another vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    dl.create(report)
    dl.create(offer)

    retrieved_offer = dl.read(offer.id_)
    assert retrieved_offer is not None
    assert isinstance(retrieved_offer.object_, as_VulnerabilityReport)  # type: ignore[union-attr]
    assert retrieved_offer.object_.id_ == report.id_  # type: ignore[union-attr]


def test_rehydration_restores_nested_object_from_datalayer(dl):
    from vultron.wire.as2.rehydration import rehydrate
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Test CVE 4",
        content="One more vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    dl.create(report)
    dl.create(offer)

    stored_offer = dl.read(offer.id_)
    assert stored_offer is not None
    full_offer = rehydrate(stored_offer, dl=dl)
    assert full_offer.object_ is not None  # type: ignore[union-attr]
    assert full_offer.object_.id_ == report.id_  # type: ignore[union-attr]
    assert full_offer.object_.type_ == "VulnerabilityReport"  # type: ignore[union-attr]


def test_rehydration_does_not_mutate_stored_record(dl):
    from vultron.wire.as2.rehydration import rehydrate
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = as_VulnerabilityReport(
        name="Test CVE 5",
        content="Final vulnerability",
        attributed_to="https://example.org/finder",
    )
    offer = rm_submit_report_activity(
        report,
        "https://example.org/finder",
        actor="https://example.org/finder",
    )

    dl.create(report)
    dl.create(offer)

    stored_offer = dl.read(offer.id_)
    assert stored_offer is not None
    rehydrate(stored_offer, dl=dl)

    raw = dl.get(offer.type_, offer.id_)
    assert raw is not None
    stored_object_field = raw["data_"]["object_"]
    assert isinstance(stored_object_field, str)
    assert stored_object_field == report.id_


# ---------------------------------------------------------------------------
# hydrate() tests (CBT-05-005)
# ---------------------------------------------------------------------------


def test_hydrate_expands_list_ref_field(dl):
    """hydrate() resolves case_participants string IDs to stored objects."""
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case_actor_id = "https://example.org/actors/case-actor-hydrate"
    case = as_VulnerabilityCase()

    participant = as_CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        attributed_to=case_actor_id,
        context=case.id_,
        name="test-participant",
    )
    dl.save(participant)

    case.case_participants = [participant.id_]
    dl.save(case)

    stored_case = dl.read(case.id_)
    assert stored_case is not None
    assert isinstance(stored_case.case_participants[0], str)

    hydrated = dl.hydrate(stored_case)
    assert hydrated is not stored_case
    assert len(hydrated.case_participants) == 1
    assert isinstance(hydrated.case_participants[0], as_CaseParticipant)
    assert hydrated.case_participants[0].id_ == participant.id_


def test_hydrate_leaves_already_expanded_participants_unchanged(dl):
    """hydrate() leaves non-string participants unchanged."""
    from vultron.enums.roles import CVDRole
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case_actor_id = "https://example.org/actors/case-actor-noop"
    case = as_VulnerabilityCase()
    participant = as_CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        attributed_to=case_actor_id,
        context=case.id_,
        name="already-expanded",
    )
    dl.save(participant)
    case.case_participants = [participant]
    dl.save(case)

    stored_case = dl.read(case.id_)
    hydrated = dl.hydrate(stored_case)
    assert len(hydrated.case_participants) == 1


def test_hydrate_keeps_unresolvable_string_ids(dl):
    """hydrate() keeps participant IDs that don't exist in the DataLayer."""
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    missing_id = "urn:uuid:00000000-0000-0000-0000-000000000000"
    case = as_VulnerabilityCase()
    case.case_participants = [missing_id]
    dl.save(case)

    stored_case = dl.read(case.id_)
    hydrated = dl.hydrate(stored_case)
    assert hydrated.case_participants[0] == missing_id


def test_hydrate_warns_for_unresolvable_string_ids(dl, caplog):
    """hydrate() logs a WARNING when a list item ID cannot be resolved."""
    import logging

    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    missing_id = "urn:uuid:00000000-0000-0000-0000-000000000001"
    case = as_VulnerabilityCase()
    case.case_participants = [missing_id]
    dl.save(case)

    stored_case = dl.read(case.id_)
    with caplog.at_level(logging.WARNING):
        dl.hydrate(stored_case)

    assert any(
        missing_id in record.message
        for record in caplog.records
        if record.levelname == "WARNING"
    ), "Expected a WARNING log mentioning the unresolvable participant ID"
