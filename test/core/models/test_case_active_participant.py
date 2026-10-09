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
"""The one active-participant predicate (CM-10-004, ADR-0114, #4046 AC-1)."""

import re

import pytest
from pydantic import ValidationError

from test.support.embargo_register import activate
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.states.rm import RM

CASE_ID = "https://example.org/cases/active-predicate"
ACTOR_ID = "https://example.org/actors/participant"
EMBARGO_ID = f"{CASE_ID}/embargoes/e1"
REVISION_ID = f"{CASE_ID}/embargoes/e2"
S = EmbargoConsentState


def _case(*, embargo: bool) -> VulnerabilityCase:
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=ACTOR_ID)
    if embargo:
        activate(case, EMBARGO_ID)
    return case


def _participant(
    *,
    joined: bool = True,
    consents: dict[str, EmbargoConsentState] | None = None,
    rm_state: RM = RM.ACCEPTED,
) -> CaseParticipant:
    return CaseParticipant(
        attributed_to=ACTOR_ID,
        context=CASE_ID,
        joined=joined,
        embargo_consents=[
            EmbargoConsent(embargo_id=eid, state=state)
            for eid, state in (consents or {}).items()
        ],
        participant_statuses=[
            ParticipantStatus(
                context=CASE_ID,
                attributed_to=ACTOR_ID,
                rm=RmDimension(state=rm_state),
            )
        ],
    )


def test_joined_defaults_true_and_round_trips() -> None:
    """Every record today is seated or accepted, so ``joined`` defaults True."""
    assert CaseParticipant(attributed_to=ACTOR_ID, context=CASE_ID).joined
    inert = _participant(joined=False)
    restored = CaseParticipant.model_validate(inert.model_dump(by_alias=True))
    assert restored.joined is False


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize(
    "consents",
    [
        {EMBARGO_ID: S.UNINVITED},
        {EMBARGO_ID: S.INVITED},
        {EMBARGO_ID: S.DECLINED},
        {EMBARGO_ID: S.TIMED_OUT},
        {EMBARGO_ID: S.AGREED},
    ],
    ids=["never-asked", "invited", "declined", "timed-out", "agreed"],
)
def test_joined_participant_is_active_with_no_embargo(
    consents: dict[str, EmbargoConsentState],
) -> None:
    """With no active embargo, any participant that joined is active.

    The consent rows are not consulted: there is nothing to be bound by.
    """
    case = _case(embargo=False)
    assert not case.embargo_in_force
    assert case.is_active_participant(_participant(consents=consents))


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize(
    ("consents", "active"),
    [
        ({EMBARGO_ID: S.AGREED}, True),
        ({EMBARGO_ID: S.AGREED, REVISION_ID: S.INVITED}, True),
        ({EMBARGO_ID: S.UNINVITED}, False),
        ({EMBARGO_ID: S.INVITED}, False),
        ({EMBARGO_ID: S.TIMED_OUT}, False),
        ({EMBARGO_ID: S.DECLINED}, False),
        ({EMBARGO_ID: S.UNINVITED, REVISION_ID: S.AGREED}, False),
    ],
    ids=[
        "signatory",
        "signatory-asked-about-revision",
        "never-asked",
        "invited",
        "timed-out",
        "declined",
        "agreed-another-embargo-only",
    ],
)
def test_active_embargo_requires_signatory(
    consents: dict[str, EmbargoConsentState], active: bool
) -> None:
    """While an embargo is active, only a signatory of it is active."""
    case = _case(embargo=True)
    assert case.embargo_in_force
    assert (
        case.is_active_participant(_participant(consents=consents)) is active
    )


@pytest.mark.spec("CM-10-004", "CM-18-001")
def test_longer_revision_excludes_a_non_accepting_signatory() -> None:
    """A participant that signed A lapses from the gate when a longer B activates.

    Nothing is written to its rows at activation; the gate reads
    ``is_signatory(active_embargo_id)`` and the lapse is derived.
    """
    case = _case(embargo=True)
    participant = _participant(consents={EMBARGO_ID: S.AGREED})
    assert case.is_active_participant(participant)

    # The revision's proposal writes the participant's UNINVITED row for it.
    participant.write_uninvited_rows([REVISION_ID])
    activate(case, REVISION_ID)

    assert participant.has_lapsed(case.embargo_register)
    assert not case.is_active_participant(participant)
    assert participant.consent_for(EMBARGO_ID) is S.AGREED

    participant.apply_pec_transition(
        REVISION_ID,
        PEC_Trigger.AGREE,
        entry_status=case.embargo_register_status(REVISION_ID),
    )
    assert case.is_active_participant(participant)
    assert not participant.has_lapsed(case.embargo_register)


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize("embargo", [False, True])
def test_unjoined_participant_is_inert(embargo: bool) -> None:
    """A participant that has not accepted its stub Invite is never active."""
    case = _case(embargo=embargo)
    participant = _participant(joined=False, consents={EMBARGO_ID: S.AGREED})
    assert not case.is_active_participant(participant)


@pytest.mark.parametrize("embargo", [False, True])
def test_closed_participant_stays_active(embargo: bool) -> None:
    """RM.CLOSED is not part of the active check (CM-23-002, #4100).

    A closed participant's replica still learns how the case ended, so the
    shared selection drops it only where CM-23-004 is named.
    """
    case = _case(embargo=embargo)
    participant = _participant(
        rm_state=RM.CLOSED, consents={EMBARGO_ID: S.AGREED}
    )
    assert participant.rm_closed
    assert case.is_active_participant(participant)


def test_no_statuses_is_not_closed() -> None:
    participant = CaseParticipant(attributed_to=ACTOR_ID, context=CASE_ID)
    assert not participant.rm_closed


# ---------------------------------------------------------------------------
# The removal fact and the computed activeParticipants view (#4079, ADR-0116)
# ---------------------------------------------------------------------------

REMOVAL_ID = f"{CASE_ID}/activities/remove-1"


@pytest.mark.spec("CM-31-001", "CS-08-002")
def test_removal_fact_is_stored_and_can_be_set_and_cleared() -> None:
    """The fact is a stored ``NonEmptyString | None``, set and cleared directly.

    No field stores the active answer: ``removed`` reads the fact, and the
    record round-trips with it through both serializations.
    """
    participant = _participant()
    assert participant.removal_activity is None
    assert not participant.removed

    participant.removal_activity = REMOVAL_ID
    assert participant.removed
    for dumped in (
        participant.model_dump(mode="json"),
        participant.model_dump(by_alias=True),
    ):
        restored = CaseParticipant.model_validate(dumped)
        assert restored.removal_activity == REMOVAL_ID
        assert restored == participant
    assert (
        participant.model_dump(by_alias=True)["removalActivity"] == REMOVAL_ID
    )

    participant.removal_activity = None
    assert not participant.removed


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("blank", ["", "   "])
def test_removal_fact_refuses_a_blank_value(blank: str) -> None:
    """If present, then non-empty: at construction and on assignment."""
    with pytest.raises(ValidationError):
        CaseParticipant(
            attributed_to=ACTOR_ID, context=CASE_ID, removal_activity=blank
        )
    participant = _participant()
    with pytest.raises(ValidationError):
        participant.removal_activity = blank
    assert participant.removal_activity is None


@pytest.mark.spec("CM-31-002")
def test_no_participant_property_reads_as_active() -> None:
    """The active answer lives on the case; the record holds only its inputs."""
    names = set(dir(CaseParticipant)) | set(CaseParticipant.model_fields)
    reads_as_active = re.compile(r"(^|_)(is_)?active(_|$)", re.IGNORECASE)
    assert not sorted(n for n in names if reads_as_active.search(n))


@pytest.mark.spec("CM-31-001", "CM-31-002", "CM-10-004")
@pytest.mark.parametrize("embargo", [False, True])
@pytest.mark.parametrize(
    "consents",
    [
        {EMBARGO_ID: S.UNINVITED},
        {EMBARGO_ID: S.INVITED},
        {EMBARGO_ID: S.DECLINED},
        {EMBARGO_ID: S.AGREED},
    ],
    ids=["never-asked", "invited", "declined", "signatory"],
)
def test_removed_participant_is_inert_whatever_its_consent(
    embargo: bool, consents: dict[str, EmbargoConsentState]
) -> None:
    """A removed participant is inert, embargo or not, signatory or not."""
    case = _case(embargo=embargo)
    participant = _participant(consents=consents)
    participant.removal_activity = REMOVAL_ID

    assert not case.is_active_participant(participant)
    case.case_participants[:] = [participant]
    assert case.active_participants == []


@pytest.mark.spec("CM-31-002")
def test_clearing_the_fact_makes_a_signatory_active_again() -> None:
    """The check turns false to true when the fact is cleared (#4081, #4084)."""
    case = _case(embargo=True)
    participant = _participant(consents={EMBARGO_ID: S.AGREED})
    participant.removal_activity = REMOVAL_ID
    assert not case.is_active_participant(participant)

    participant.removal_activity = None

    assert case.is_active_participant(participant)


def _carrying_case(*participants: CaseParticipant) -> VulnerabilityCase:
    case = _case(embargo=True)
    case.case_participants[:] = list(participants)
    return case


def _signatory(
    name: str, *, removal_activity: str | None = None, joined: bool = True
) -> CaseParticipant:
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{name}",
        attributed_to=f"https://example.org/actors/{name}",
        context=CASE_ID,
        joined=joined,
        removal_activity=removal_activity,
        embargo_consents=[
            EmbargoConsent(embargo_id=EMBARGO_ID, state=S.AGREED)
        ],
    )


@pytest.mark.spec("CM-31-003")
def test_active_participants_lists_the_active_records_in_roster_order() -> (
    None
):
    """The view is the case-level check over the records the case carries."""
    first = _signatory("first")
    removed = _signatory("removed", removal_activity=REMOVAL_ID)
    unjoined = _signatory("unjoined", joined=False)
    last = _signatory("last")
    case = _carrying_case(last, removed, unjoined, first)
    case.case_participants.append(f"{CASE_ID}/participants/bare-reference")

    assert case.active_participants == [last.id_, first.id_]


@pytest.mark.spec("CM-31-003", "ARCH-12-003", "ARCH-23-005")
def test_active_participants_is_published_by_alias_and_round_trips() -> None:
    """Serialized by alias, never stored, and read back despite forbid."""
    case = _carrying_case(
        _signatory("kept"), _signatory("removed", removal_activity=REMOVAL_ID)
    )

    wire = case.model_dump(by_alias=True, mode="json")
    assert wire["activeParticipants"] == [f"{CASE_ID}/participants/kept"]
    assert VulnerabilityCase.model_validate(wire) == case
    assert (
        VulnerabilityCase.model_validate(case.model_dump(by_alias=True))
        == case
    )

    stored = case.model_dump(mode="json")
    assert "active_participants" not in stored
    assert "activeParticipants" not in stored
    assert VulnerabilityCase.model_validate(stored) == case


@pytest.mark.spec("ARCH-23-005")
def test_contradicting_active_participants_is_refused() -> None:
    """A supplied view that disagrees with the carried records is refused."""
    case = _carrying_case(
        _signatory("kept"), _signatory("removed", removal_activity=REMOVAL_ID)
    )
    wire = case.model_dump(by_alias=True, mode="json")
    wire["activeParticipants"] = [
        f"{CASE_ID}/participants/kept",
        f"{CASE_ID}/participants/removed",
    ]

    with pytest.raises(ValidationError):
        VulnerabilityCase.model_validate(wire)


@pytest.mark.spec("ARCH-23-005", "VM-10-001")
def test_only_the_default_context_reads_back_as_no_override() -> None:
    """The default ``@context`` round-trips as ``None``; another is kept."""
    case = _carrying_case(_signatory("kept"))
    wire = case.model_dump(by_alias=True, mode="json")
    assert wire["@context"]
    assert VulnerabilityCase.model_validate(wire).context_ is None

    other = "https://example.org/other-context.jsonld"
    restored = VulnerabilityCase.model_validate({**wire, "@context": other})
    assert restored.context_ == other
    assert restored.model_dump(by_alias=True)["@context"] == other


@pytest.mark.spec("CM-31-003")
def test_active_participants_is_left_out_while_the_roster_holds_a_reference() -> (
    None
):
    """A case that cannot evaluate every roster entry publishes no view.

    A bare reference cannot be checked, so a published list would be partial;
    CM-31-003 requires exactly the active participants.  The case still
    round-trips, and a supplied value is checked against the Python view.
    """
    kept = _signatory("kept")
    case = _carrying_case(kept)
    case.case_participants.append(f"{CASE_ID}/participants/bare-reference")

    wire = case.model_dump(by_alias=True, mode="json")
    assert "activeParticipants" not in wire
    assert "active_participants" not in wire
    assert VulnerabilityCase.model_validate(wire) == case

    assert (
        VulnerabilityCase.model_validate(
            {**wire, "activeParticipants": [kept.id_]}
        )
        == case
    )
    with pytest.raises(ValidationError):
        VulnerabilityCase.model_validate(
            {**wire, "activeParticipants": [f"{CASE_ID}/participants/other"]}
        )


@pytest.mark.spec("CM-31-003")
def test_a_reference_only_case_publishes_no_view() -> None:
    """A stored case holds participant references only: no view on the wire."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=ACTOR_ID)
    case.case_participants.append(f"{CASE_ID}/participants/stored")

    assert case.active_participants == []
    assert "activeParticipants" not in case.model_dump(by_alias=True)


@pytest.mark.spec("CM-31-003")
def test_an_empty_roster_publishes_an_empty_view() -> None:
    """With no roster entries the view is exact, and it is empty."""
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=ACTOR_ID)

    assert case.model_dump(by_alias=True)["activeParticipants"] == []
