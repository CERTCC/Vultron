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
"""A joined projection's actions from the state at its ledger position.

Beside one ``completed`` action per ledger act, the CSAF renderer derives
the work still open at the preview's position from the participants the
joined preview shows: an unanswered embargo invitation is an
``outstanding`` ``confirmation``, RM ``DEFERRED`` a ``deferred`` action,
and a participant that has left gives ``discontinued`` on its open actions
(CSAF-06-010, ADR-0219).
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from test.support.case_projection import (
    CASE_ID,
    COMMITTED_AT,
    EMBARGO_END,
    PROJECTOR,
    REPORTER,
    VENDOR,
    csaf_schema_validator,
    projected_case,
    projected_ledger,
)
from test.support.embargo_register import register
from test.support.objects import make
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_preview import CasePreview
from vultron.core.models.case_projection import (
    ProjectionCut,
    ProjectionInputs,
    PublicationStatus,
)
from vultron.core.models.case_projection_profile import (
    JOINED_PROFILE,
    PUBLIC_PROFILE,
    ProjectionProfile,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.csaf.projection import (
    EMBARGO_PHRASES,
    STATE_ACTION_SUMMARIES,
    render_csaf,
)

_EMBARGO = make(EmbargoEvent, context=CASE_ID, end_time=EMBARGO_END)
_REVISION = make(EmbargoEvent, context=CASE_ID, end_time=EMBARGO_END)
_REMOVE = "https://example.org/activities/remove-vendor"


def _at(day: int) -> datetime:
    return datetime(2026, 10, day, tzinfo=UTC)


def _status(state: RM, day: int) -> ParticipantStatus:
    return make(
        ParticipantStatus,
        context=CASE_ID,
        attributed_to=VENDOR,
        rm=RmDimension(state=state),
        published=_at(day),
    )


def _row(embargo: EmbargoEvent, state: EmbargoConsentState) -> EmbargoConsent:
    return make(EmbargoConsent, embargo_id=embargo.id_, state=state)


def _vendor(
    *,
    rm: tuple[RM, ...] = (RM.RECEIVED, RM.VALID, RM.ACCEPTED),
    rows: tuple[EmbargoConsent, ...] = (),
    removal_activity: str | None = None,
) -> CaseParticipant:
    """The vendor, with its RM history on consecutive days, its consent
    rows and its removal fact."""
    return make(
        CaseParticipant,
        attributed_to=VENDOR,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
        name="Example Vendor",
        participant_statuses=[
            _status(state, day) for day, state in enumerate(rm, start=1)
        ],
        embargo_consents=list(rows),
        removal_activity=removal_activity,
    )


def _render(
    participant: CaseParticipant,
    *,
    entries: list[EmbargoRegisterEntry] | None = None,
    profile: ProjectionProfile = JOINED_PROFILE,
    ledger: bool = True,
) -> dict[str, Any]:
    if entries is None:
        entries = register(active=_EMBARGO, proposed=[_REVISION])
    # Every register entry has a row (CM-18-005): the rest are UNINVITED.
    participant.write_uninvited_rows([entry.embargo_id for entry in entries])
    case = projected_case(
        case_participants=[participant], embargo_register=entries
    )
    cut = ProjectionCut.of(case, projected_ledger() if ledger else [], profile)
    inputs = ProjectionInputs(
        status=PublicationStatus.INTERIM,
        projecting_actor=PROJECTOR,
        position_committed_at=COMMITTED_AT,
    )
    rendered: dict[str, Any] = render_csaf(cut, inputs, category="csaf_base")
    return rendered


def _state_actions(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    """The actions the state at the position gives: those no ledger act
    made."""
    involvement = rendered["document"].get("involvement", {})
    return [
        action
        for action in involvement.get("actions", [])
        if action["status"] != "completed"
    ]


def _actor_name(rendered: dict[str, Any], action: dict[str, Any]) -> str:
    entities: dict[str, str] = {
        entity["entity_id"]: entity["name"]
        for entity in rendered["document"]["involvement"]["entities"]
    }
    (actor,) = action["acting_entity_refs"]
    return entities[actor]


# --- AC-1: outstanding -------------------------------------------------------


@pytest.mark.spec("CSAF-06-010")
@pytest.mark.parametrize(
    ("embargo", "register_status"),
    [
        (_EMBARGO, EmbargoRegisterStatus.ACTIVE),
        (_REVISION, EmbargoRegisterStatus.PROPOSED),
    ],
    ids=["in-force", "proposed"],
)
def test_an_unanswered_invitation_is_an_outstanding_confirmation(
    embargo: EmbargoEvent, register_status: EmbargoRegisterStatus
) -> None:
    rendered = _render(
        _vendor(rows=(_row(embargo, EmbargoConsentState.INVITED),))
    )

    (action,) = _state_actions(rendered)
    assert (action["category"], action["status"]) == (
        "confirmation",
        "outstanding",
    )
    assert _actor_name(rendered, action) == "Example Vendor"
    assert action["summary"] == STATE_ACTION_SUMMARIES[
        ("confirmation", "outstanding")
    ].format(embargo=EMBARGO_PHRASES[register_status])
    # A consent row carries no time, so the action is dated at the position.
    assert datetime.fromisoformat(action["date"]) == COMMITTED_AT
    assert csaf_schema_validator().is_valid(rendered)


def test_two_unanswered_invitations_are_two_confirmations() -> None:
    rendered = _render(
        _vendor(
            rows=(
                _row(_EMBARGO, EmbargoConsentState.INVITED),
                _row(_REVISION, EmbargoConsentState.INVITED),
            )
        )
    )

    actions = _state_actions(rendered)
    assert [action["action_id"] for action in actions] == [
        "STATE-1",
        "STATE-2",
    ]
    assert len({action["summary"] for action in actions}) == 2
    assert csaf_schema_validator().is_valid(rendered)


@pytest.mark.parametrize(
    "register_status",
    [
        EmbargoRegisterStatus.REJECTED,
        EmbargoRegisterStatus.CANCELLED,
        EmbargoRegisterStatus.SUPERSEDED,
    ],
)
def test_an_invitation_to_a_closed_embargo_version_is_not_open(
    register_status: EmbargoRegisterStatus,
) -> None:
    """An answer to a rejected, cancelled or replaced version changes
    nothing (CM-18-003), so its invitation is no longer outstanding."""
    entries = [
        EmbargoRegisterEntry(embargo=_REVISION, status=register_status),
        *register(active=_EMBARGO),
    ]
    rendered = _render(
        _vendor(rows=(_row(_REVISION, EmbargoConsentState.INVITED),)),
        entries=entries,
    )

    assert _state_actions(rendered) == []


def test_an_invitation_to_an_embargo_the_register_lacks_is_not_open() -> None:
    other = make(EmbargoEvent, context=CASE_ID, end_time=EMBARGO_END)
    rendered = _render(
        _vendor(rows=(_row(other, EmbargoConsentState.INVITED),))
    )

    assert _state_actions(rendered) == []


@pytest.mark.parametrize(
    "state",
    [
        EmbargoConsentState.UNINVITED,
        EmbargoConsentState.AGREED,
        EmbargoConsentState.DECLINED,
        EmbargoConsentState.TIMED_OUT,
    ],
)
def test_a_row_that_is_not_invited_gives_no_action(
    state: EmbargoConsentState,
) -> None:
    rendered = _render(_vendor(rows=(_row(_EMBARGO, state),)))

    assert _state_actions(rendered) == []


# --- AC-2: deferred ----------------------------------------------------------


@pytest.mark.spec("CSAF-06-010")
@pytest.mark.parametrize(
    ("rm", "category"),
    [
        ((RM.RECEIVED, RM.VALID, RM.DEFERRED), "assessment"),
        ((RM.VALID, RM.ACCEPTED, RM.DEFERRED), "coordination"),
    ],
    ids=["before-accepting", "after-accepting"],
)
def test_a_deferred_participant_gives_a_deferred_action(
    rm: tuple[RM, ...], category: str
) -> None:
    rendered = _render(_vendor(rm=rm))

    (action,) = _state_actions(rendered)
    assert (action["category"], action["status"]) == (category, "deferred")
    assert _actor_name(rendered, action) == "Example Vendor"
    assert action["summary"] == STATE_ACTION_SUMMARIES[(category, "deferred")]
    # The deferral's own time: the third status, on the third day.
    assert datetime.fromisoformat(action["date"]) == _at(3)
    assert csaf_schema_validator().is_valid(rendered)


def test_a_deferral_is_dated_by_the_first_status_of_its_run() -> None:
    rendered = _render(
        _vendor(rm=(RM.VALID, RM.DEFERRED, RM.DEFERRED, RM.DEFERRED))
    )

    (action,) = _state_actions(rendered)
    assert datetime.fromisoformat(action["date"]) == _at(2)


def test_a_deferral_that_ended_gives_no_action() -> None:
    rendered = _render(_vendor(rm=(RM.VALID, RM.DEFERRED, RM.ACCEPTED)))

    assert _state_actions(rendered) == []


def test_a_coordination_deferred_again_stays_coordination() -> None:
    rendered = _render(
        _vendor(rm=(RM.VALID, RM.DEFERRED, RM.ACCEPTED, RM.DEFERRED))
    )

    (action,) = _state_actions(rendered)
    assert action["category"] == "coordination"
    assert datetime.fromisoformat(action["date"]) == _at(4)


# --- AC-3: discontinued ------------------------------------------------------


@pytest.mark.spec("CSAF-06-010")
def test_a_removed_participant_discontinues_its_open_actions() -> None:
    rendered = _render(
        _vendor(
            rm=(RM.VALID, RM.ACCEPTED, RM.DEFERRED),
            rows=(_row(_REVISION, EmbargoConsentState.INVITED),),
            removal_activity=_REMOVE,
        )
    )

    actions = _state_actions(rendered)
    assert [(a["category"], a["status"]) for a in actions] == [
        ("confirmation", "discontinued"),
        ("coordination", "discontinued"),
    ]
    assert [a["summary"] for a in actions] == [
        STATE_ACTION_SUMMARIES[("confirmation", "discontinued")].format(
            embargo=EMBARGO_PHRASES[EmbargoRegisterStatus.PROPOSED]
        ),
        STATE_ACTION_SUMMARIES[("coordination", "discontinued")],
    ]
    # The removal fact carries no time, so both are dated at the position.
    assert [datetime.fromisoformat(a["date"]) for a in actions] == [
        COMMITTED_AT,
        COMMITTED_AT,
    ]
    assert csaf_schema_validator().is_valid(rendered)


def test_a_closed_participant_discontinues_its_open_invitation() -> None:
    """A participant in RM ``CLOSED`` may act on nothing further
    (CM-23-018), so its invitation will never be answered."""
    rendered = _render(
        _vendor(
            rm=(RM.VALID, RM.ACCEPTED, RM.CLOSED),
            rows=(_row(_EMBARGO, EmbargoConsentState.INVITED),),
        )
    )

    (action,) = _state_actions(rendered)
    assert (action["category"], action["status"]) == (
        "confirmation",
        "discontinued",
    )
    # Dated when the participant closed the report: the third status.
    assert datetime.fromisoformat(action["date"]) == _at(3)


@pytest.mark.spec("CSAF-06-010")
@pytest.mark.parametrize(
    ("rm", "category"),
    [
        ((RM.VALID, RM.DEFERRED, RM.CLOSED), "assessment"),
        ((RM.ACCEPTED, RM.DEFERRED, RM.DEFERRED, RM.CLOSED), "coordination"),
    ],
    ids=["before-accepting", "after-accepting"],
)
def test_closing_the_report_from_a_deferral_discontinues_it(
    rm: tuple[RM, ...], category: str
) -> None:
    rendered = _render(_vendor(rm=rm))

    (action,) = _state_actions(rendered)
    assert (action["category"], action["status"]) == (
        category,
        "discontinued",
    )
    assert datetime.fromisoformat(action["date"]) == _at(len(rm))


def test_closing_the_report_after_accepting_gives_no_action() -> None:
    rendered = _render(_vendor(rm=(RM.VALID, RM.ACCEPTED, RM.CLOSED)))

    assert _state_actions(rendered) == []


def test_a_removed_participant_with_nothing_open_gives_no_action() -> None:
    rendered = _render(_vendor(removal_activity=_REMOVE))

    assert _state_actions(rendered) == []


# --- AC-4: never attempted or planned ------------------------------------------


@pytest.mark.spec("CSAF-06-010")
@pytest.mark.parametrize("removed", [False, True], ids=["open", "removed"])
def test_no_action_is_attempted_or_planned(removed: bool) -> None:
    rendered = _render(
        _vendor(
            rm=(RM.VALID, RM.DEFERRED),
            rows=(
                _row(_EMBARGO, EmbargoConsentState.INVITED),
                _row(_REVISION, EmbargoConsentState.INVITED),
            ),
            removal_activity=_REMOVE if removed else None,
        )
    )

    statuses = {
        action["status"]
        for action in rendered["document"]["involvement"]["actions"]
    }
    expected = {"discontinued"} if removed else {"outstanding", "deferred"}
    assert statuses == {"completed"} | expected
    assert not statuses & {"attempted", "planned", "in_progress"}


# --- the cut alone -----------------------------------------------------------


def test_state_actions_alone_make_an_involvement() -> None:
    """A preview whose cut ledger keeps no act still shows the open work."""
    rendered = _render(
        _vendor(rows=(_row(_EMBARGO, EmbargoConsentState.INVITED),)),
        ledger=False,
    )

    (action,) = rendered["document"]["involvement"]["actions"]
    assert action["status"] == "outstanding"
    assert csaf_schema_validator().is_valid(rendered)


def test_the_public_projection_shows_no_open_work() -> None:
    """The public profile omits the participants and the register, so no
    state action can be derived."""
    rendered = _render(
        _vendor(
            rm=(RM.VALID, RM.DEFERRED),
            rows=(_row(_EMBARGO, EmbargoConsentState.INVITED),),
        ),
        profile=PUBLIC_PROFILE,
    )

    assert "involvement" not in rendered["document"]


def _parsed_participant(**fields: Any) -> CasePreview:
    """A preview parsed from its wire keys, its one participant holding an
    invited row to the embargo in force, with *fields* over it."""
    return CasePreview.model_validate(
        {
            "id": CASE_ID,
            "ledgerPosition": {"logIndex": 0, "entryHash": "ef"},
            "embargoRegister": [
                {"embargo": _EMBARGO.id_, "status": "ACTIVE"},
            ],
            "caseParticipants": [
                {
                    "type": "CaseParticipant",
                    "attributedTo": REPORTER,
                    "embargoConsents": [
                        {
                            "type": "EmbargoConsent",
                            "embargoId": _EMBARGO.id_,
                            "state": "INVITED",
                        }
                    ],
                    **fields,
                }
            ],
        }
    )


def _rendered(preview: CasePreview) -> dict[str, Any]:
    inputs = ProjectionInputs(
        status=PublicationStatus.INTERIM,
        projecting_actor=PROJECTOR,
        position_committed_at=COMMITTED_AT,
    )
    cut = ProjectionCut(preview=preview, profile=JOINED_PROFILE)
    rendered: dict[str, Any] = render_csaf(cut, inputs, category="csaf_base")
    return rendered


def test_a_register_naming_its_embargo_by_id_still_answers() -> None:
    (action,) = _state_actions(_rendered(_parsed_participant()))

    assert action["status"] == "outstanding"


@pytest.mark.parametrize(
    "fields",
    [
        {"attributedTo": {"type": "Redacted"}},
        {"embargoConsents": [{"type": "Redacted"}]},
        {
            "embargoConsents": [
                {
                    "type": "EmbargoConsent",
                    "embargoId": _EMBARGO.id_,
                    "state": {"type": "Redacted"},
                }
            ]
        },
    ],
    ids=["actor", "row", "row-state"],
)
def test_a_withheld_value_gives_no_state_action(
    fields: dict[str, Any],
) -> None:
    assert _state_actions(_rendered(_parsed_participant(**fields))) == []


def test_a_withheld_removal_or_status_does_not_discontinue() -> None:
    """A participant whose removal and statuses the preview withholds is
    not read as having left: its invitation stays outstanding."""
    preview = _parsed_participant(
        removalActivity={"type": "Redacted"},
        participantStatuses=[{"type": "Redacted"}],
    )

    (action,) = _state_actions(_rendered(preview))
    assert action["status"] == "outstanding"


def test_a_withheld_current_status_is_not_read_as_the_one_before() -> None:
    """A deferral followed by a withheld status is no longer known to be
    current, so it gives no action."""
    deferred = _status(RM.DEFERRED, 2).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    preview = _parsed_participant(
        embargoConsents=[],
        participantStatuses=[deferred, {"type": "Redacted"}],
    )

    assert _state_actions(_rendered(preview)) == []


def test_a_shown_deferral_with_a_withheld_time_is_dated_at_the_position() -> (
    None
):
    deferred = _status(RM.DEFERRED, 2).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    deferred["published"] = {"type": "Redacted"}
    preview = _parsed_participant(
        embargoConsents=[], participantStatuses=[deferred]
    )

    (action,) = _state_actions(_rendered(preview))
    assert action["status"] == "deferred"
    assert datetime.fromisoformat(action["date"]) == COMMITTED_AT


def _with_register(entry: dict[str, Any]) -> CasePreview:
    preview = _parsed_participant()
    data = preview.model_dump(mode="json", by_alias=True, exclude_none=True)
    data["embargoRegister"] = [entry]
    return CasePreview.model_validate(data)


@pytest.mark.parametrize(
    "entry",
    [
        {"embargo": _EMBARGO.id_, "status": {"type": "Redacted"}},
        {"embargo": {"type": "Redacted"}, "status": "ACTIVE"},
    ],
    ids=["status", "embargo"],
)
def test_a_withheld_register_value_opens_no_invitation(
    entry: dict[str, Any],
) -> None:
    assert _state_actions(_rendered(_with_register(entry))) == []


def test_a_withheld_row_embargo_opens_no_invitation() -> None:
    preview = _parsed_participant(
        embargoConsents=[
            {
                "type": "EmbargoConsent",
                "embargoId": {"type": "Redacted"},
                "state": "INVITED",
            }
        ]
    )

    assert _state_actions(_rendered(preview)) == []
