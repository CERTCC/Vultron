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

"""Initial embargo eligibility and duration at case creation (EP-04, ADR-0096).

Drives ``InitializeDefaultEmbargoNode`` end to end, so each assertion is about
the embargo the case is actually created with, not a blackboard value.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import py_trees
import pytest
from py_trees.common import Status

from test.conftest import seed_case_owner_participant
from test.core.behaviors.bt_harness import BTTestScenario
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo_resolution import (
    CaseEmbargoAlreadyInitializedNode,
    CaseNotEmbargoEligibleNode,
)
from vultron.core.behaviors.case.nodes.embargo_revision import (
    CreationTimeRevision,
)
from vultron.core.behaviors.embargo.nodes import em_state as em_state_module
from vultron.core.models._helpers import _as_id
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.services.embargo_duration import EmbargoDurationSource
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.use_cases.triggers._helpers import find_embargo_proposal_id
from vultron.errors import BtNodePreconditionError, VultronValidationError

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-resolution"

# Distinct from every default in play, so a pinned duration names its source.
SENDER_PROPOSAL = timedelta(days=20)
ACTOR_DEFAULT = timedelta(days=30)
PROTOCOL_DEFAULT = timedelta(hours=96)


@pytest.fixture
def case_obj(bt_scenario: BTTestScenario) -> VulnerabilityCase:
    bt_scenario.dl.create(CaseActor(id_=ACTOR_ID, name="Vendor Co"))
    case = VulnerabilityCase(id_=CASE_ID, name="Case", attributed_to=ACTOR_ID)
    seed_case_owner_participant(bt_scenario.dl, case)
    bt_scenario.dl.create(case)
    return case


def _profile(
    duration: timedelta | None = None, actor_id: str = ACTOR_ID
) -> VultronOrganization:
    """An inline actor profile, with a published policy of *duration*.

    The tree reads the CASE_OWNER's actor default only from the profile the
    ``Create(CaseProposal)`` carried inline, handed to it as ``owner_profile``
    (CP-01-010).
    """
    if duration is None:
        return VultronOrganization(id_=actor_id)
    return VultronOrganization(
        id_=actor_id,
        embargo_policy=EmbargoPolicy(
            actor_id=actor_id,
            inbox=f"{actor_id}/inbox",
            preferred_duration=duration,
        ),
    )


def _store_policy_record(
    bt_scenario: BTTestScenario, duration: timedelta, actor_id: str
) -> None:
    """A free-standing ``EmbargoPolicy`` record in the store — never read."""
    bt_scenario.dl.create(
        EmbargoPolicy(
            actor_id=actor_id,
            inbox=f"{actor_id}/inbox",
            preferred_duration=duration,
        )
    )


def _set_pxa(bt_scenario: BTTestScenario) -> None:
    case = cast(Any, bt_scenario.dl.read(CASE_ID))
    case.append_case_status(pxa_state=CS_pxa.Pxa)
    bt_scenario.dl.save(case)


def _run(
    bt_scenario: BTTestScenario,
    *,
    sender_proposal: timedelta | None = None,
    owner_policy: timedelta | None = None,
    actor_config: ActorConfig | None = None,
    **context: Any,
) -> tuple[Status, datetime, datetime]:
    extra: dict[str, Any] = dict(context)
    extra.setdefault("owner_profile", _profile(owner_policy))
    if sender_proposal is not None:
        extra["sender_proposed_embargo_duration"] = sender_proposal
    before = datetime.now(tz=UTC)
    result = bt_scenario.run(
        InitializeDefaultEmbargoNode(
            actor_config=actor_config
            or ActorConfig(protocol_default_embargo_duration=PROTOCOL_DEFAULT)
        ),
        actor_id=ACTOR_ID,
        case_id=CASE_ID,
        **extra,
    )
    return result.status, before, datetime.now(tz=UTC)


def _active_embargo(bt_scenario: BTTestScenario) -> EmbargoEvent | None:
    case = cast(Any, bt_scenario.dl.read(CASE_ID))
    embargo_id = _as_id(case.active_embargo)
    if embargo_id is None:
        return None
    embargo = bt_scenario.dl.read(embargo_id)
    assert isinstance(embargo, EmbargoEvent)
    return embargo


def _assert_duration(
    embargo: EmbargoEvent | None,
    expected: timedelta,
    before: datetime,
    after: datetime,
) -> None:
    assert embargo is not None
    assert embargo.end_time is not None
    # ``from_now_utc`` stamps at second precision (CS-13-003), so the lower
    # bound drops the sub-second part ``datetime.now`` carries.
    floor = before.replace(microsecond=0)
    assert floor + expected <= embargo.end_time <= after + expected


def _em_state(bt_scenario: BTTestScenario) -> EM:
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case.current_status.em.state


# (sender proposal, actor default, P/X/A set) → expected duration, or None
# for "no embargo, case stays EM.NONE".
_RESOLUTION_TABLE = [
    pytest.param(False, False, False, PROTOCOL_DEFAULT, id="none-none-clear"),
    pytest.param(False, True, False, ACTOR_DEFAULT, id="none-actor-clear"),
    pytest.param(True, False, False, SENDER_PROPOSAL, id="sender-none-clear"),
    pytest.param(True, True, False, SENDER_PROPOSAL, id="sender-actor-clear"),
    pytest.param(False, False, True, None, id="none-none-pxa"),
    pytest.param(False, True, True, None, id="none-actor-pxa"),
    pytest.param(True, False, True, None, id="sender-none-pxa"),
    pytest.param(True, True, True, None, id="sender-actor-pxa"),
]


@pytest.mark.spec("EP-04-005")
@pytest.mark.spec("EP-04-006")
@pytest.mark.spec("EP-04-010")
def test_only_the_case_owners_policy_is_the_actor_default(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """A shorter policy published by another actor is not a candidate."""
    other = "https://example.org/actors/other"
    bt_scenario.dl.create(_profile(timedelta(days=5), other))
    _store_policy_record(bt_scenario, timedelta(days=5), other)

    _, before, after = _run(bt_scenario, owner_policy=ACTOR_DEFAULT)

    _assert_duration(
        _active_embargo(bt_scenario), ACTOR_DEFAULT, before, after
    )


@pytest.mark.spec("EP-04-010")
@pytest.mark.spec("CP-01-010")
def test_a_policy_record_in_the_store_is_not_the_actor_default(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """The store-wide scan is retired (#4027): a shorter ``EmbargoPolicy``
    naming the owner, but not on the inline profile, is never a candidate."""
    _store_policy_record(bt_scenario, timedelta(days=5), ACTOR_ID)

    _, before, after = _run(bt_scenario)

    _assert_duration(
        _active_embargo(bt_scenario), PROTOCOL_DEFAULT, before, after
    )


@pytest.mark.spec("EP-04-008")
@pytest.mark.parametrize(
    ("has_sender", "has_actor_default", "pxa_set", "expected"),
    _RESOLUTION_TABLE,
)
def test_initial_embargo_resolution_table(
    bt_scenario: BTTestScenario,
    case_obj: VulnerabilityCase,
    has_sender: bool,
    has_actor_default: bool,
    pxa_set: bool,
    expected: timedelta | None,
) -> None:
    if pxa_set:
        _set_pxa(bt_scenario)

    status, before, after = _run(
        bt_scenario,
        sender_proposal=SENDER_PROPOSAL if has_sender else None,
        owner_policy=ACTOR_DEFAULT if has_actor_default else None,
    )

    assert status == Status.SUCCESS
    if expected is None:
        assert _active_embargo(bt_scenario) is None
        assert _em_state(bt_scenario) == EM.NONE
    else:
        _assert_duration(_active_embargo(bt_scenario), expected, before, after)
        # Both parties proposed: the shorter is active and the longer is a
        # pending revision, so the EM state observed is REVISE (EP-04-003).
        contested = has_sender and has_actor_default
        assert _em_state(bt_scenario) == (
            EM.REVISE if contested else EM.ACTIVE
        )


@pytest.mark.spec("EP-04-005")
def test_no_policy_no_proposal_uses_configured_protocol_default(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    configured = timedelta(days=5)
    status, before, after = _run(
        bt_scenario,
        actor_config=ActorConfig(protocol_default_embargo_duration=configured),
    )

    assert status == Status.SUCCESS
    _assert_duration(_active_embargo(bt_scenario), configured, before, after)


def test_unconfigured_protocol_default_is_72_hours(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    status, before, after = _run(bt_scenario, actor_config=ActorConfig())

    assert status == Status.SUCCESS
    _assert_duration(
        _active_embargo(bt_scenario), timedelta(hours=72), before, after
    )


@pytest.mark.spec("EP-04-006")
def test_protocol_default_does_not_compete_with_longer_actor_default(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """A 30-day actor default yields 30 days, not the shorter 96 h fallback."""
    _, before, after = _run(bt_scenario, owner_policy=timedelta(days=30))

    _assert_duration(
        _active_embargo(bt_scenario), timedelta(days=30), before, after
    )


@pytest.mark.spec("EP-04-007")
def test_protocol_default_is_not_a_minimum(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """A proposal shorter than the protocol default is honored as stated."""
    short = timedelta(hours=24)
    _, before, after = _run(bt_scenario, owner_policy=short)

    _assert_duration(_active_embargo(bt_scenario), short, before, after)


@pytest.mark.spec("CP-01-010")
@pytest.mark.parametrize(
    "profile",
    [None, "foreign", "not-an-actor"],
    ids=["absent", "another-actors-profile", "not-an-actor"],
)
def test_no_inline_profile_for_the_owner_fails_and_creates_nothing(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase, profile: Any
) -> None:
    """Without the CASE_OWNER's own inline profile there is no actor default
    to read, and the node fetches none: it fails before creating anything."""
    value = {
        None: None,
        "foreign": _profile(
            timedelta(days=5), "https://example.org/actors/other"
        ),
        "not-an-actor": "https://example.org/actors/vendor",
    }[profile]

    status, _, _ = _run(bt_scenario, owner_profile=value)

    assert status == Status.FAILURE
    assert _active_embargo(bt_scenario) is None
    assert list(bt_scenario.dl.list_objects("EmbargoEvent")) == []


@pytest.mark.spec("EP-04-008")
def test_pxa_set_creates_no_embargo_event(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """The refusal arm runs before creation, so no orphan EmbargoEvent exists."""
    _set_pxa(bt_scenario)

    status, _, _ = _run(bt_scenario)

    assert status == Status.SUCCESS
    assert list(bt_scenario.dl.list_objects("EmbargoEvent")) == []


@pytest.mark.spec("EP-04-008")
def test_pxa_refusal_is_logged(
    bt_scenario: BTTestScenario,
    case_obj: VulnerabilityCase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_pxa(bt_scenario)

    with caplog.at_level(logging.INFO):
        _run(bt_scenario)

    assert any(
        "EP-04-008" in record.getMessage() and CASE_ID in record.getMessage()
        for record in caplog.records
    )


class TestCaseNotEmbargoEligibleNode:
    def test_eligible_case_is_failure(
        self, bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
    ) -> None:
        result = bt_scenario.run(
            CaseNotEmbargoEligibleNode(), actor_id=ACTOR_ID, case_id=CASE_ID
        )
        assert result.status == Status.FAILURE

    def test_pxa_set_is_success(
        self, bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
    ) -> None:
        _set_pxa(bt_scenario)
        result = bt_scenario.run(
            CaseNotEmbargoEligibleNode(), actor_id=ACTOR_ID, case_id=CASE_ID
        )
        assert result.status == Status.SUCCESS

    def test_missing_case_raises_rather_than_admitting(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An unanswerable guard escapes; FAILURE would run the creation arm."""
        result = bt_scenario.run(
            CaseNotEmbargoEligibleNode(),
            actor_id=ACTOR_ID,
            case_id="https://example.org/cases/absent",
        )
        assert result.status == Status.FAILURE
        assert "VultronNotFoundError" in result.feedback_message

    def test_missing_datalayer_raises_rather_than_admitting(self) -> None:
        """No store to read is an unanswerable guard, not "eligible"."""
        node = CaseNotEmbargoEligibleNode()
        assert node.datalayer is None
        with pytest.raises(BtNodePreconditionError, match="DataLayer"):
            node.update()

    def test_missing_case_fails_the_whole_subtree(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An unreadable case is not silently treated as "no embargo"."""
        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(),
            actor_id=ACTOR_ID,
            case_id="https://example.org/cases/absent",
        )
        assert result.status == Status.FAILURE
        assert list(bt_scenario.dl.list_objects("EmbargoEvent")) == []

    def test_store_error_creates_no_embargo_event(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VulnerabilityCase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed eligibility read fails the tree before creation runs."""

        def _broken(self: EmbargoLifecycle, **_: Any) -> None:
            raise RuntimeError("store unavailable")

        monkeypatch.setattr(
            EmbargoLifecycle, "assert_embargo_eligible", _broken
        )

        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(), actor_id=ACTOR_ID, case_id=CASE_ID
        )

        assert result.status == Status.FAILURE
        assert list(bt_scenario.dl.list_objects("EmbargoEvent")) == []
        assert _active_embargo(bt_scenario) is None


@pytest.mark.spec("EP-04-003")
@pytest.mark.parametrize(
    "proposal", [timedelta(0), timedelta(days=-1)], ids=["zero", "negative"]
)
def test_non_positive_sender_proposal_creates_no_embargo(
    bt_scenario: BTTestScenario,
    case_obj: VulnerabilityCase,
    proposal: timedelta,
) -> None:
    """A proposal that would end the embargo on arrival is refused."""
    status, _, _ = _run(bt_scenario, sender_proposal=proposal)

    assert status == Status.FAILURE
    assert _active_embargo(bt_scenario) is None


@pytest.mark.spec("EP-04-003")
def test_a_tie_between_sender_and_actor_default_registers_no_revision(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """Equal terms leave nothing contested: ACTIVE, and no pending revision."""
    status, before, after = _run(
        bt_scenario, owner_policy=ACTOR_DEFAULT, sender_proposal=ACTOR_DEFAULT
    )

    assert status == Status.SUCCESS
    _assert_duration(
        _active_embargo(bt_scenario), ACTOR_DEFAULT, before, after
    )
    assert _em_state(bt_scenario) == EM.ACTIVE
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    assert case.proposed_embargoes == []


_UNSET = object()


class _RevisionProbe(py_trees.behaviour.Behaviour):
    """Capture ``creation_time_revision`` while the execution is still live.

    ``BTBridge`` scopes the key to one execution and restores it afterwards,
    so the value is only observable from inside the tree.
    """

    def __init__(self) -> None:
        super().__init__(name="RevisionProbe")
        self.seen: object = _UNSET

    def update(self) -> Status:
        self.seen = py_trees.blackboard.Blackboard.storage.get(
            "/creation_time_revision", _UNSET
        )
        return Status.SUCCESS


def _run_probing_revision(
    bt_scenario: BTTestScenario, *, sender_proposal: timedelta
) -> tuple[Status, object]:
    probe = _RevisionProbe()
    tree = py_trees.composites.Sequence(
        name="InitializeThenProbe",
        memory=False,
        children=[
            InitializeDefaultEmbargoNode(
                actor_config=ActorConfig(
                    protocol_default_embargo_duration=PROTOCOL_DEFAULT
                )
            ),
            probe,
        ],
    )
    result = bt_scenario.run(
        tree,
        actor_id=ACTOR_ID,
        case_id=CASE_ID,
        owner_profile=_profile(ACTOR_DEFAULT),
        sender_proposed_embargo_duration=sender_proposal,
    )
    return result.status, probe.seen


@pytest.mark.spec("EP-04-011")
def test_no_contest_publishes_no_revision(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """A tie still writes ``creation_time_revision`` — as ``None`` — so the
    relay never reads a revision from an earlier write (BT-17-003)."""
    status, seen = _run_probing_revision(
        bt_scenario, sender_proposal=ACTOR_DEFAULT
    )

    assert status == Status.SUCCESS
    assert seen is None


@pytest.mark.spec("EP-04-011")
def test_the_revision_key_does_not_outlive_its_execution(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """``BTBridge`` scopes the key, so a later execution that never reaches
    the registration (a redelivery) cannot read this one's revision."""
    status, seen = _run_probing_revision(
        bt_scenario, sender_proposal=SENDER_PROPOSAL
    )

    assert status == Status.SUCCESS
    assert isinstance(seen, CreationTimeRevision)
    assert (
        py_trees.blackboard.Blackboard.storage.get("/creation_time_revision")
        is None
    )


@pytest.mark.spec("EP-04-011")
def test_a_contest_publishes_the_indexed_revision(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """The published revision names the id the index holds and whose terms
    lost: here the owner's longer default (EP-04-011)."""
    status, revision = _run_probing_revision(
        bt_scenario, sender_proposal=SENDER_PROPOSAL
    )

    assert status == Status.SUCCESS
    assert isinstance(revision, CreationTimeRevision)
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    assert revision.case_id == CASE_ID
    assert case.proposed_embargoes == [revision.embargo_id]
    assert (
        case.pending_embargo_proposal_index[revision.embargo_id]
        == revision.proposal_id
    )
    assert revision.losing_source is EmbargoDurationSource.ACTOR_DEFAULT


def _sender_event(
    end_time: datetime, *, event_id: str, context: str = "urn:report:r-1"
) -> EmbargoEvent:
    return EmbargoEvent(id_=event_id, context=context, end_time=end_time)


@pytest.mark.spec("EP-04-004")
def test_a_sender_id_already_held_by_another_embargo_is_refused(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """The Reporter's event arrives under the Reporter's id (#3392).  When the
    store already holds that id for a different embargo, the case must not be
    bound to it: creation fails instead of activating foreign terms while
    shortest-wins compared the terms the sender stated."""
    foreign_id = "https://example.org/embargoes/reused"
    bt_scenario.dl.create(
        EmbargoEvent(
            id_=foreign_id,
            context="https://example.org/cases/some-other-case",
            end_time=datetime(2099, 1, 1, tzinfo=UTC),
        )
    )
    stated_end = datetime.now(tz=UTC) + timedelta(days=5)

    status, _, _ = _run(
        bt_scenario,
        sender_proposal=timedelta(days=5),
        sender_proposed_embargo=_sender_event(stated_end, event_id=foreign_id),
    )

    assert status == Status.FAILURE
    assert _active_embargo(bt_scenario) is None
    stored = bt_scenario.dl.read(foreign_id)
    assert isinstance(stored, EmbargoEvent)
    assert stored.context == "https://example.org/cases/some-other-case"


@pytest.mark.spec("EP-04-004")
def test_a_replay_of_the_same_sender_embargo_is_idempotent(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """A stored twin that *is* this embargo — same case, same end — is the
    replay the ``VultronAlreadyExistsError`` swallow always meant."""
    event_id = "https://example.org/embargoes/replayed"
    stated_end = datetime.now(tz=UTC).replace(microsecond=0) + timedelta(
        days=5
    )
    bt_scenario.dl.create(
        EmbargoEvent(id_=event_id, context=CASE_ID, end_time=stated_end)
    )

    status, _, _ = _run(
        bt_scenario,
        sender_proposal=timedelta(days=5),
        sender_proposed_embargo=_sender_event(stated_end, event_id=event_id),
    )

    assert status == Status.SUCCESS
    active = _active_embargo(bt_scenario)
    assert active is not None and active.id_ == event_id


@pytest.mark.spec("EP-04-003")
def test_a_longer_sender_duration_without_its_event_fails_loudly(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """When the actor default won and the sender's duration is longer, the
    revision needs the sender's event; a blackboard carrying the duration but
    not the event is inconsistent and must not report SUCCESS with the
    revision silently skipped (BT-HELPER-01)."""
    status, _, _ = _run(
        bt_scenario,
        owner_policy=ACTOR_DEFAULT,
        sender_proposal=ACTOR_DEFAULT + timedelta(days=30),
    )

    assert status == Status.FAILURE
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    assert case.proposed_embargoes == []


@pytest.mark.spec("EP-04-011")
def test_creation_time_revision_is_indexed_for_the_owners_default_selection(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """The shortest-wins loser is a revision like any other (EP-04-011).

    The sender's shorter terms win and the owner's longer default is the
    pending revision.  It must be reachable by ``find_embargo_proposal_id``,
    which reads only ``pending_embargo_proposal_index`` (EP-08-002); the
    relayed Invite to the winning party is asserted by the implementation's
    own tests.
    """
    status, _, _ = _run(
        bt_scenario,
        owner_policy=ACTOR_DEFAULT,
        sender_proposal=SENDER_PROPOSAL,
    )

    assert status == Status.SUCCESS
    assert _em_state(bt_scenario) == EM.REVISE
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    (loser_id,) = case.proposed_embargoes
    assert loser_id in case.pending_embargo_proposal_index
    assert (
        find_embargo_proposal_id(case, bt_scenario.dl)
        == case.pending_embargo_proposal_index[loser_id]
    )


@pytest.mark.spec("EP-04-012")
def test_a_rerun_after_the_embargo_exited_initializes_nothing(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """Creation-time initialization runs once per case (EP-04-012).

    First run: the protocol default becomes active.  The owner then ends the
    embargo, which clears ``active_embargo`` and leaves EM at ``EXITED``.  A
    second run — a redelivered ``Create(CaseProposal)`` reusing the case — must
    recognise that initialization already happened: SUCCESS, the EM state
    untouched, no embargo attached, and no new ``EmbargoEvent`` stored.
    """
    status, _, _ = _run(bt_scenario)
    assert status == Status.SUCCESS
    assert _em_state(bt_scenario) == EM.ACTIVE

    EmbargoLifecycle(persistence=bt_scenario.dl).terminate_active_embargo(
        case_id=CASE_ID, actor_id=ACTOR_ID
    )
    assert _em_state(bt_scenario) == EM.EXITED
    events_before = len(list(bt_scenario.dl.list_objects("EmbargoEvent")))

    status, _, _ = _run(bt_scenario)

    assert status == Status.SUCCESS
    assert _em_state(bt_scenario) == EM.EXITED
    assert _active_embargo(bt_scenario) is None
    events_after = len(list(bt_scenario.dl.list_objects("EmbargoEvent")))
    assert events_after == events_before


def _set_em(bt_scenario: BTTestScenario, em_state: EM) -> None:
    case = cast(Any, bt_scenario.dl.read(CASE_ID))
    case.append_case_status(em_state=em_state)
    bt_scenario.dl.save(case)


def _event_ids(bt_scenario: BTTestScenario) -> set[str]:
    return {e.id_ for e in bt_scenario.dl.list_objects("EmbargoEvent")}


@pytest.mark.spec("EP-04-012")
class TestCaseEmbargoAlreadyInitializedNode:
    """The once-per-case guard keys on the EM state, never the reference."""

    def _guard(self, bt_scenario: BTTestScenario) -> Status:
        return bt_scenario.run(
            CaseEmbargoAlreadyInitializedNode(),
            actor_id=ACTOR_ID,
            case_id=CASE_ID,
        ).status

    @pytest.mark.parametrize(
        "em_state", [state for state in EM if state != EM.NONE]
    )
    def test_every_state_but_none_is_already_initialized(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VulnerabilityCase,
        em_state: EM,
    ) -> None:
        """No active embargo is attached here: the state alone decides."""
        _set_em(bt_scenario, em_state)
        assert _active_embargo(bt_scenario) is None

        assert self._guard(bt_scenario) == Status.SUCCESS

    def test_none_is_not_initialized(
        self, bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
    ) -> None:
        assert _em_state(bt_scenario) == EM.NONE
        assert self._guard(bt_scenario) == Status.FAILURE

    def test_a_half_built_case_at_none_completes_initialization(
        self, bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
    ) -> None:
        """A redelivery finishing a case whose first attempt died before the
        embargo was set up must still initialize it (EP-04-012)."""
        assert _em_state(bt_scenario) == EM.NONE
        assert _active_embargo(bt_scenario) is None

        status, before, after = _run(bt_scenario)

        assert status == Status.SUCCESS
        assert _em_state(bt_scenario) == EM.ACTIVE
        _assert_duration(
            _active_embargo(bt_scenario), PROTOCOL_DEFAULT, before, after
        )

    @pytest.mark.parametrize(
        ("owner_policy", "sender_proposal", "expected"),
        [
            pytest.param(None, None, EM.ACTIVE, id="active"),
            pytest.param(
                ACTOR_DEFAULT, SENDER_PROPOSAL, EM.REVISE, id="revise"
            ),
        ],
    )
    def test_a_rerun_on_an_initialized_case_changes_nothing(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VulnerabilityCase,
        owner_policy: timedelta | None,
        sender_proposal: timedelta | None,
        expected: EM,
    ) -> None:
        """A rerun with different terms neither stores an event nor registers
        a revision: the proposal's terms are not reconciled (EP-04-012)."""
        status, _, _ = _run(
            bt_scenario,
            owner_policy=owner_policy,
            sender_proposal=sender_proposal,
        )
        assert status == Status.SUCCESS
        assert _em_state(bt_scenario) == expected
        first = cast(Any, bt_scenario.dl.read(CASE_ID))
        events_before = _event_ids(bt_scenario)

        status, _, _ = _run(
            bt_scenario,
            owner_policy=ACTOR_DEFAULT + timedelta(days=7),
            sender_proposal=timedelta(days=3),
        )

        assert status == Status.SUCCESS
        again = cast(Any, bt_scenario.dl.read(CASE_ID))
        assert again.current_status.em.state == expected
        assert again.active_embargo_id == first.active_embargo_id
        assert again.proposed_embargoes == first.proposed_embargoes
        assert _event_ids(bt_scenario) == events_before

    def test_skip_is_logged_with_the_case_and_state(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VulnerabilityCase,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _set_em(bt_scenario, EM.EXITED)

        with caplog.at_level(logging.INFO):
            assert self._guard(bt_scenario) == Status.SUCCESS

        assert any(
            record.levelno == logging.INFO
            and CASE_ID in record.getMessage()
            and "EXITED" in record.getMessage()
            and "EP-04-012" in record.getMessage()
            for record in caplog.records
        )

    def test_missing_case_raises_rather_than_admitting(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The real ``ReadEmStateNode`` returns FAILURE for an absent case;
        the guard turns it into a raise, which ``BTBridge`` reports."""
        absent = "https://example.org/cases/absent"
        result = bt_scenario.run(
            CaseEmbargoAlreadyInitializedNode(),
            actor_id=ACTOR_ID,
            case_id=absent,
        )

        assert result.status == Status.FAILURE
        assert "BtNodePreconditionError" in result.feedback_message
        assert "cannot read the EM state" in result.feedback_message
        assert absent in result.feedback_message

    def test_missing_datalayer_raises_rather_than_admitting(self) -> None:
        node = CaseEmbargoAlreadyInitializedNode()
        assert node.datalayer is None
        with pytest.raises(BtNodePreconditionError, match="DataLayer"):
            node.update()

    def test_unreadable_em_state_raises_and_creates_nothing(
        self,
        bt_scenario: BTTestScenario,
        case_obj: VulnerabilityCase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``ReadEmStateNode`` only returns FAILURE; the guard must turn that
        into a raise, or the Selector would run the creation arm."""

        class _UnreadableEmState:
            def __init__(
                self, case_id: str, result_out: dict[str, object]
            ) -> None:
                self._result_out = result_out
                self.datalayer: object = None
                self.feedback_message = "invalid em_state value"

            def update(self) -> Status:
                self._result_out["error"] = VultronValidationError(
                    self.feedback_message
                )
                return Status.FAILURE

        monkeypatch.setattr(
            em_state_module, "ReadEmStateNode", _UnreadableEmState
        )

        result = bt_scenario.run(
            InitializeDefaultEmbargoNode(), actor_id=ACTOR_ID, case_id=CASE_ID
        )

        assert result.status == Status.FAILURE
        assert "BtNodePreconditionError" in result.feedback_message
        assert "invalid em_state value" in result.feedback_message
        assert list(bt_scenario.dl.list_objects("EmbargoEvent")) == []
        assert _em_state(bt_scenario) == EM.NONE
