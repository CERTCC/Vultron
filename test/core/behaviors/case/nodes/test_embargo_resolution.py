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
from vultron.core.models.vultron_types import (
    VulnerabilityCase,
    VultronCaseActor,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-resolution"

# Distinct from every default in play, so a pinned duration names its source.
SENDER_PROPOSAL = timedelta(days=20)
ACTOR_DEFAULT = timedelta(days=30)
PROTOCOL_DEFAULT = timedelta(hours=96)


@pytest.fixture
def case_obj(bt_scenario: BTTestScenario) -> VulnerabilityCase:
    bt_scenario.dl.create(VultronCaseActor(id_=ACTOR_ID, name="Vendor Co"))
    case = VulnerabilityCase(id_=CASE_ID, name="Case", attributed_to=ACTOR_ID)
    bt_scenario.dl.create(case)
    return case


def _publish_policy(
    bt_scenario: BTTestScenario, duration: timedelta, policy_id: str
) -> None:
    bt_scenario.dl.create(
        EmbargoPolicy(
            id_=policy_id,
            actor_id=ACTOR_ID,
            inbox=f"{ACTOR_ID}/inbox",
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
) -> tuple[Status, datetime, datetime]:
    extra: dict[str, Any] = {}
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
    assert before + expected <= embargo.end_time <= after + expected


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
        assert _em_state(bt_scenario) == EM.ACTIVE


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
