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
"""The one core service that asks the participant-suggestion port (BT-24-008).

- It resolves the stored case's references, projects the case and hands the
  port only the suggestion context (BT-24-002, BT-24-003).
- Its answer is the port's, empty included (BT-24-004); a wrong-typed answer
  is a wiring error.
- A ratchet holds it to being the port's only caller in ``vultron/``.
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path

import pytest

from test.support.objects import make
from test.support.signatures import signature_of
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_suggestion import (
    ParticipantProfile,
    ParticipantSuggestion,
    SuggestionContext,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.participant_suggestion import (
    ParticipantSuggestionPort,
)
from vultron.core.services import participant_suggestion as service
from vultron.core.services.participant_suggestion import (
    suggest_case_participants,
    suggestion_context,
)
from vultron.enums import CVDRole
from vultron.errors import VultronNotFoundError

_OWNER = "https://example.org/actors/owner"
_VENDOR = "https://example.org/actors/vendor"
_OTHER = "https://example.org/actors/other-inc"
_CASE = "https://example.org/cases/c-1"
_REPORT = "https://example.org/reports/r-1"

_SUGGESTION = ParticipantSuggestion(
    actor_id=_OTHER,
    role=CVDRole.VENDOR,
    rationale="the report says Other Inc. bundles libexample",
)


class _RecordingPort:
    """A port adapter that answers fixed and records what it was asked."""

    def __init__(self, answer: Sequence[object]) -> None:
        self.answer = answer
        self.asked: list[object] = []

    def suggest_participants(
        self, context: SuggestionContext
    ) -> Sequence[ParticipantSuggestion]:
        self.asked.append(context)
        return self.answer  # type: ignore[return-value]


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)


def _stored_case(dl: SqliteDataLayer) -> VulnerabilityCase:
    """A case as the store holds it: reports and participants by id."""
    case = make(VulnerabilityCase, id_=_CASE, attributed_to=_OWNER)
    report = make(
        VulnerabilityReport,
        id_=_REPORT,
        attributed_to=_OWNER,
        content="libexample 2.1 is bundled by Other Inc.",
    )
    dl.create(report)
    case.add_report(report.id_)
    for actor_id, role in (
        (_OWNER, CVDRole.CASE_OWNER),
        (_VENDOR, CVDRole.VENDOR),
    ):
        participant = make(
            CaseParticipant,
            attributed_to=actor_id,
            context=_CASE,
            case_roles=[role],
        )
        case.add_participant(participant)
        dl.create(participant)
    dl.save(case)
    stored = dl.read_case(_CASE)
    assert stored is not None
    assert all(isinstance(p, str) for p in stored.case_participants)
    return stored


def test_the_recording_port_conforms_to_the_port() -> None:
    assert isinstance(_RecordingPort([]), ParticipantSuggestionPort)


@pytest.mark.spec("BT-24-001")
@pytest.mark.spec("BT-24-002")
@pytest.mark.spec("BT-24-008")
def test_the_port_is_asked_about_the_projected_context_only(
    dl: SqliteDataLayer,
) -> None:
    case = _stored_case(dl)
    port = _RecordingPort([_SUGGESTION])

    assert suggest_case_participants(case, port, dl) == [_SUGGESTION]

    [asked] = port.asked
    assert type(asked) is SuggestionContext
    assert asked.id_ == _CASE
    assert [r.content for r in asked.vulnerability_reports] == [
        "libexample 2.1 is bundled by Other Inc."
    ]
    assert asked.case_participants == [
        ParticipantProfile(
            attributed_to=_OWNER, case_roles=[CVDRole.CASE_OWNER]
        ),
        ParticipantProfile(attributed_to=_VENDOR, case_roles=[CVDRole.VENDOR]),
    ]
    # The stored case keeps its references; the projection read a copy.
    assert all(isinstance(p, str) for p in case.case_participants)


def test_a_case_already_carrying_its_objects_reads_nothing_more() -> None:
    """Objects the case holds inline are projected as they are."""
    participant = make(
        CaseParticipant,
        attributed_to=_VENDOR,
        context=_CASE,
        case_roles=[CVDRole.VENDOR],
    )
    case = make(
        VulnerabilityCase,
        id_=_CASE,
        attributed_to=_OWNER,
        case_participants=[participant],
    )
    empty = SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)
    context = suggestion_context(case, empty)
    assert [p.attributed_to for p in context.vendors] == [_VENDOR]


@pytest.mark.spec("BT-24-004")
def test_an_empty_answer_is_valid(dl: SqliteDataLayer) -> None:
    assert (
        suggest_case_participants(_stored_case(dl), _RecordingPort([]), dl)
        == []
    )


def test_a_wrong_typed_answer_is_a_wiring_error(dl: SqliteDataLayer) -> None:
    port = _RecordingPort([_SUGGESTION, {"actor_id": _OTHER}])
    with pytest.raises(TypeError, match=r"answered with \['dict'\]"):
        suggest_case_participants(_stored_case(dl), port, dl)


@pytest.mark.parametrize(
    "missing", [_REPORT, "participant"], ids=["report", "participant"]
)
def test_a_reference_the_store_lacks_is_refused(
    dl: SqliteDataLayer, missing: str
) -> None:
    case = _stored_case(dl)
    if missing == "participant":
        missing = str(case.case_participants[0])
    dl.delete(
        "VulnerabilityReport" if missing == _REPORT else "CaseParticipant",
        missing,
    )
    port = _RecordingPort([])
    with pytest.raises(VultronNotFoundError, match=missing):
        suggestion_context(case, dl)
    with pytest.raises(VultronNotFoundError):
        suggest_case_participants(case, port, dl)
    assert port.asked == []


# --- the service is the port's only caller (BT-24-008) --------------------

_PORT_METHOD = "suggest_participants"
_VULTRON = Path(__file__).resolve().parents[3] / "vultron"
_SERVICE = Path(service.__file__).resolve()


def _port_calls() -> dict[Path, int]:
    """Each module in ``vultron/`` that calls the port's method, and how often."""
    calls: dict[Path, int] = {}
    for path in sorted(_VULTRON.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == _PORT_METHOD
        )
        if count:
            calls[path] = count
    return calls


@pytest.mark.spec("BT-24-008")
def test_the_service_is_the_only_caller_of_the_port() -> None:
    calls = _port_calls()
    assert calls.get(_SERVICE) == 1, (
        "the scan found no call from the service; it is broken or the "
        "method was renamed"
    )
    others = sorted(
        str(p.relative_to(_VULTRON)) for p in calls if p != _SERVICE
    )
    assert others == [], (
        f"{others} call {_PORT_METHOD}() directly; ask through "
        "suggest_case_participants, which projects the case first (BT-24-008)"
    )


def test_the_port_declares_the_scanned_method() -> None:
    assert _PORT_METHOD in vars(ParticipantSuggestionPort)


@pytest.mark.spec("BT-24-002")
def test_the_port_takes_the_suggestion_context_not_the_case() -> None:
    import typing

    hints = typing.get_type_hints(
        ParticipantSuggestionPort.suggest_participants
    )
    params = list(
        signature_of(ParticipantSuggestionPort.suggest_participants).parameters
    )
    assert params == ["self", "context"]
    assert hints["context"] is SuggestionContext
    assert not issubclass(SuggestionContext, VulnerabilityCase)
