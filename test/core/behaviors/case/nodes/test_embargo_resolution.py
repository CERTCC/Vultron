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
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from py_trees.common import Status

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.embargo_tree import (
    InitializeDefaultEmbargoNode,
)
from vultron.core.behaviors.case.nodes.embargo_resolution import (
    CaseNotEmbargoEligibleNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.errors import BtNodePreconditionError
from test.core.behaviors.bt_harness import BTTestScenario

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
    bt_scenario.dl.create(case)
    return case


def _publish_policy(
    bt_scenario: BTTestScenario,
    duration: timedelta,
    policy_id: str,
    actor_id: str = ACTOR_ID,
) -> None:
    bt_scenario.dl.create(
        EmbargoPolicy(
            id_=policy_id,
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
    actor_config: ActorConfig | None = None,
    **context: Any,
) -> tuple[Status, datetime, datetime]:
    extra: dict[str, Any] = dict(context)
    if sender_proposal is not None:
        extra["sender_proposed_embargo_duration"] = sender_proposal
    before = datetime.now(tz=timezone.utc)
    result = bt_scenario.run(
        InitializeDefaultEmbargoNode(
            actor_config=actor_config
            or ActorConfig(protocol_default_embargo_duration=PROTOCOL_DEFAULT)
        ),
        actor_id=ACTOR_ID,
        case_id=CASE_ID,
        **extra,
    )
    return result.status, before, datetime.now(tz=timezone.utc)


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
    _publish_policy(bt_scenario, ACTOR_DEFAULT, f"{ACTOR_ID}/policy")
    _publish_policy(bt_scenario, timedelta(days=5), f"{other}/policy", other)

    _, before, after = _run(bt_scenario)

    _assert_duration(
        _active_embargo(bt_scenario), ACTOR_DEFAULT, before, after
    )


@pytest.mark.spec("EP-04-010")
def test_foreign_policy_alone_falls_back_to_protocol_default(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    other = "https://example.org/actors/other"
    _publish_policy(bt_scenario, timedelta(days=5), f"{other}/policy", other)

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
    if has_actor_default:
        _publish_policy(bt_scenario, ACTOR_DEFAULT, f"{ACTOR_ID}/policy")
    if pxa_set:
        _set_pxa(bt_scenario)

    status, before, after = _run(
        bt_scenario,
        sender_proposal=SENDER_PROPOSAL if has_sender else None,
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
    _publish_policy(bt_scenario, timedelta(days=30), f"{ACTOR_ID}/policy")

    _, before, after = _run(bt_scenario)

    _assert_duration(
        _active_embargo(bt_scenario), timedelta(days=30), before, after
    )


@pytest.mark.spec("EP-04-007")
def test_protocol_default_is_not_a_minimum(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """A proposal shorter than the protocol default is honored as stated."""
    short = timedelta(hours=24)
    _publish_policy(bt_scenario, short, f"{ACTOR_ID}/policy")

    _, before, after = _run(bt_scenario)

    _assert_duration(_active_embargo(bt_scenario), short, before, after)


@pytest.mark.spec("EP-04-010")
def test_actor_default_selection_is_deterministic(
    bt_scenario: BTTestScenario, case_obj: VulnerabilityCase
) -> None:
    """Several published policies resolve to the shortest, whatever the order."""
    _publish_policy(bt_scenario, timedelta(days=45), f"{ACTOR_ID}/policy-a")
    _publish_policy(bt_scenario, timedelta(days=14), f"{ACTOR_ID}/policy-z")
    _publish_policy(bt_scenario, timedelta(days=60), f"{ACTOR_ID}/policy-m")

    _, before, after = _run(bt_scenario)

    _assert_duration(
        _active_embargo(bt_scenario), timedelta(days=14), before, after
    )


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
    _publish_policy(bt_scenario, ACTOR_DEFAULT, f"{ACTOR_ID}/policy")

    status, before, after = _run(bt_scenario, sender_proposal=ACTOR_DEFAULT)

    assert status == Status.SUCCESS
    _assert_duration(
        _active_embargo(bt_scenario), ACTOR_DEFAULT, before, after
    )
    assert _em_state(bt_scenario) == EM.ACTIVE
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    assert case.proposed_embargoes == []


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
            end_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
    )
    stated_end = datetime.now(tz=timezone.utc) + timedelta(days=5)

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
    stated_end = datetime.now(tz=timezone.utc).replace(
        microsecond=0
    ) + timedelta(days=5)
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
    _publish_policy(bt_scenario, ACTOR_DEFAULT, f"{ACTOR_ID}/policy")

    status, _, _ = _run(
        bt_scenario, sender_proposal=ACTOR_DEFAULT + timedelta(days=30)
    )

    assert status == Status.FAILURE
    case = bt_scenario.dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    assert case.proposed_embargoes == []
