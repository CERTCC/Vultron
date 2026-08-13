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

"""DataLayer core-vocabulary round-trip tests (DL-05-001, DL-05-002).

Verifies that dl.read() and dl.list_objects() return core domain objects
(vultron/core/models/) rather than wire vocabulary types
(vultron/wire/as2/vocab/objects/) for persisted types that have a registered
CORE_VOCABULARY counterpart.

AC-4: a saved core object reads back as the same core type.
AC-2: reconstruction uses CORE_VOCABULARY, not the wire VOCABULARY.
AC-3: AS2 Activity types (no core counterpart) still reconstruct via wire path.
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.datalayer_sqlite.schema import VultronObjectRecord
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_record import VulnerabilityRecord
from vultron.core.states import CS_vfd, RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_CONTEXT = "urn:uuid:case-context-fixture"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_instance(core_cls):
    """Build a minimal valid instance for any supported core domain type."""
    if core_cls in (CaseStatus, ParticipantStatus):
        return core_cls(context=_CASE_CONTEXT)
    if core_cls is EmbargoEvent:
        return core_cls(context=_CASE_CONTEXT, end_time=_NOW)
    if core_cls is EmbargoPolicy:
        return core_cls(
            actor_id="urn:uuid:actor-fixture",
            inbox="https://example.org/inbox",
            preferred_duration=timedelta(days=90),
        )
    if core_cls is VulnerabilityRecord:
        return core_cls(name="CVE-2024-XXXX")
    return core_cls()


@pytest.fixture
def dl():
    instance = SqliteDataLayer("sqlite:///:memory:")
    yield instance
    instance.clear_all()
    instance.close()


# ---------------------------------------------------------------------------
# AC-4: saved core object reads back as the same core type
# ---------------------------------------------------------------------------


# CaseActor stores type_="Service" (an enum value), not "CaseActor", so the
# CORE_VOCABULARY lookup by stored type_ does not apply to it. Actor types with
# enum-valued type_ fields are handled by the wire fallback path; improving them
# is a separate concern.
@pytest.mark.parametrize(
    "core_cls",
    [
        VulnerabilityCase,
        VulnerabilityReport,
        CaseParticipant,
        CaseStatus,
        ParticipantStatus,
        EmbargoEvent,
        EmbargoPolicy,
        VulnerabilityRecord,
    ],
)
def test_read_returns_core_type(dl, core_cls):
    """dl.read() returns the core domain type for any registered CORE_VOCABULARY type."""
    obj = _make_instance(core_cls)
    dl.save(obj)
    result = dl.read(obj.id_)
    assert result is not None
    assert isinstance(
        result, core_cls
    ), f"Expected {core_cls.__name__}, got {type(result).__name__}"


@pytest.mark.parametrize(
    "core_cls",
    [
        VulnerabilityCase,
        VulnerabilityReport,
        CaseParticipant,
    ],
)
def test_list_objects_returns_core_type(dl, core_cls):
    """dl.list_objects() returns core domain objects for CORE_VOCABULARY types."""
    obj1 = core_cls()
    obj2 = core_cls()
    dl.save(obj1)
    dl.save(obj2)
    results = dl.list_objects(core_cls.__name__)
    assert len(results) == 2
    for item in results:
        assert isinstance(
            item, core_cls
        ), f"Expected {core_cls.__name__}, got {type(item).__name__}"


def test_read_preserves_core_object_id(dl):
    """Round-tripped core object retains its original id_."""
    case = VulnerabilityCase()
    original_id = case.id_
    dl.save(case)
    result = dl.read(original_id)
    assert result is not None
    assert result.id_ == original_id


def test_read_does_not_return_wire_type_for_core_entity(dl):
    """dl.read() MUST NOT return as_VulnerabilityCase for a saved VulnerabilityCase."""
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    case = VulnerabilityCase()
    dl.save(case)
    result = dl.read(case.id_)
    assert result is not None
    assert not isinstance(result, as_VulnerabilityCase), (
        "dl.read() returned a wire type (as_VulnerabilityCase) instead of the "
        "core type (VulnerabilityCase) — CORE_VOCABULARY lookup is not used."
    )


def test_list_objects_does_not_return_wire_type_for_core_entity(dl):
    """dl.list_objects() MUST NOT return wire types for CORE_VOCABULARY types."""
    from vultron.wire.as2.vocab.objects.vulnerability_report import (
        as_VulnerabilityReport,
    )

    report = VulnerabilityReport()
    dl.save(report)
    results = dl.list_objects("VulnerabilityReport")
    assert len(results) == 1
    assert not isinstance(results[0], as_VulnerabilityReport), (
        "dl.list_objects() returned a wire type instead of the core type "
        "— CORE_VOCABULARY lookup is not used."
    )


# ---------------------------------------------------------------------------
# AC-3: wire fallback for AS2 Activity types (no core counterpart)
# ---------------------------------------------------------------------------


def test_read_wire_only_type_still_works(dl):
    """Types not in CORE_VOCABULARY (e.g. as_Note) still reconstruct via wire path."""
    note = as_Note(content="Hello from wire")
    dl.save(note)
    result = dl.read(note.id_)
    assert result is not None
    assert isinstance(result, as_Note)


def test_core_entity_type_string_matches_class_name(dl):
    """Stored type_ string matches the core class name (required for CORE_VOCABULARY lookup)."""
    case = VulnerabilityCase()
    dl.save(case)
    result = dl.read(case.id_)
    assert result is not None
    assert result.type_ == VulnerabilityCase.__name__


# ---------------------------------------------------------------------------
# DL-05-002: a row that fails core validation still reads back as core (#2232)
# ---------------------------------------------------------------------------


def _insert_raw_row(dl, id_, type_, data):
    """Insert *data* verbatim, bypassing object_to_record normalisation.

    Mirrors the ``crud.create`` + ``StorableRecord`` write path, which stores
    ``record.data_`` as given, skipping ``Record.from_obj``'s wire→core
    normalisation (issue #2283).
    """
    with Session(dl._engine) as session:
        session.add(
            VultronObjectRecord(id_=id_, type_=type_, actor_id=None, data=data)
        )
        session.commit()


def _mixed_spelling_case_row(case_id):
    """A stored case row whose nested participant uses wire (camelCase) keys.

    Snake_case at the case level — so ``case_participants`` is populated — but
    each entry is dumped ``by_alias``, which is what makes core validation of
    the *participant* fail while the case itself looks well formed.
    """
    status = as_ParticipantStatus(
        context=case_id, rm_state=RM.ACCEPTED, vfd_state=CS_vfd.vfd
    )
    participant = as_CaseParticipant(
        id_="urn:uuid:participant-2232",
        attributed_to="https://example.org/actors/finder",
        context=case_id,
        case_roles=[CVDRole.FINDER],
        participant_statuses=[status],
    )
    case = as_VulnerabilityCase(
        id_=case_id, name="mixed", case_participants=[participant]
    )
    data = case.model_dump(mode="json")
    data["case_participants"] = [
        participant.model_dump(mode="json", by_alias=True, exclude_none=True)
    ]
    return data


def test_mixed_spelling_row_fails_core_validation():
    """Guard the premise: the fixture row really does fail core validation.

    Without this, the read-path tests below could pass for the wrong reason —
    a row that validates cleanly never exercises the fallback at all.
    """
    case_id = "urn:uuid:case-2232-premise"
    with pytest.raises(VultronValidationError):
        VulnerabilityCase.model_validate(_mixed_spelling_case_row(case_id))


def test_read_projects_wire_fallback_back_to_core(dl):
    """A row failing core validation reads back as the core type, not the wire one.

    Before #2232 the shape guard on ``CaseParticipant`` turned this row into an
    ``as_VulnerabilityCase`` from ``dl.read()``, and ``resolve_case`` then raised
    ``Expected VulnerabilityCase, got as_VulnerabilityCase`` — a 422 on every
    subsequent case operation (fcv-reject demo, Phase 3 add-note-to-case).
    The read path now projects the wire fallback through ``to_core()``.
    """
    case_id = "urn:uuid:case-2232-read"
    _insert_raw_row(
        dl, case_id, "VulnerabilityCase", _mixed_spelling_case_row(case_id)
    )

    result = dl.read(case_id)

    assert result is not None
    assert not isinstance(result, as_VulnerabilityCase)
    assert isinstance(result, VulnerabilityCase), (
        f"Expected VulnerabilityCase, got {type(result).__name__} — the wire "
        "fallback was returned un-projected (DL-05-002, issue #2232)."
    )


def test_read_projection_preserves_participant_rm_state(dl):
    """The projected core object keeps the participant's RM ladder position.

    A projection that reset ``rm`` to ``RM.START`` would satisfy the type
    assertion above while silently rewinding protocol state — that is #2264.
    """
    case_id = "urn:uuid:case-2232-ladder"
    _insert_raw_row(
        dl, case_id, "VulnerabilityCase", _mixed_spelling_case_row(case_id)
    )

    result = dl.read(case_id)

    assert isinstance(result, VulnerabilityCase)
    assert len(result.case_participants) == 1
    participant = result.case_participants[0]
    assert isinstance(participant, CaseParticipant)
    assert participant.participant_statuses
    assert (
        participant_status_rm_state(participant.participant_statuses[0])
        is RM.ACCEPTED
    )
