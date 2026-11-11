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
"""An Actuator acts on one target per call and is safe to repeat (ADR-0183).

An Actuator is found in three places, and each is checked: the fuzzer node
(an ``ActuatorCallOutPoint`` subclass), the core call-out bundle field whose
STOCHASTIC backend is one, and the core tree that places that field.  The
re-run test drives the publication tree, the one tree that acts on several
targets, through the bridge twice with one received activity, as a re-run
from holding processes it.
"""

from __future__ import annotations

import dataclasses
import functools
import importlib
import pkgutil
import re
from datetime import timedelta
from pathlib import Path

import py_trees
import pytest
from py_trees.common import Access, Status

import vultron.demo.fuzzer.bundles as stochastic_pkg
from test.support.act_runner import run_tree
from test.support.call_out import (
    FixedAnswerActuator,
    acts,
    refused_class,
    tick_call_out,
    yes,
    yes_with,
)
from test.support.fuzzer_nodes import capability_subclasses
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge.bt_bridge import BTBridge
from vultron.core.behaviors.call_out.actuator import (
    ActuationRequest,
    ActuatorBackend,
    ActuatorContract,
    actuation_id,
    actuator_call,
)
from vultron.core.behaviors.call_out.answer import (
    REFUSAL_REASON_KEY,
    CallOutAnswer,
    CallOutContract,
    CallOutVerdict,
)
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.bundles.publication import (
    PublicationCallOutBundle,
)
from vultron.core.behaviors.call_out.errors import (
    CallOutBackendError,
    CallOutContractError,
)
from vultron.core.behaviors.call_out.guard import (
    CallOutBudgetExceededError,
    SynchronousCallOut,
    TimeBoundedCallOut,
    guard_call_out_factory,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.nodes import AlwaysSucceed, NoOpActuator
from vultron.core.behaviors.case.leave_case_trigger_tree import (
    create_leave_case_trigger_tree,
)
from vultron.core.behaviors.embargo.terminate_active_embargo_tree import (
    create_terminate_active_embargo_tree,
)
from vultron.core.behaviors.report.deploy_fix_tree import (
    create_deploy_fix_tree,
)
from vultron.core.behaviors.report.deploy_mitigation_tree import (
    create_deploy_mitigation_tree,
)
from vultron.core.behaviors.report.deploy_tree import create_deploy_tree
from vultron.core.behaviors.report.prioritize_tree import (
    create_prioritize_subtree,
)
from vultron.core.behaviors.report.publication_intent import (
    INTENT_DECISION_KEY,
    PublicationIntentDecision,
)
from vultron.core.behaviors.report.publication_tree import (
    create_publication_tree,
)
from vultron.core.behaviors.report.publish_artifact_tree import (
    advisory_target,
    create_publish_artifact_tree,
)
from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.demo.fuzzer.call_out_point import ActuatorCallOutPoint

CASE_ID = "https://example.org/cases/actuation"
ACTOR_ID = "https://example.org/actors/publisher"
SENDER_ID = "https://example.org/actors/sender"

_VULTRON = Path(__file__).resolve().parents[4] / "vultron"
_CORE_BEHAVIORS = _VULTRON / "core" / "behaviors"
#: Where a tree may place an Actuator: core trees, use cases and the fuzzer.
_PLACEMENT_ROOTS = (_VULTRON / "core", _VULTRON / "demo" / "fuzzer")


# ---------------------------------------------------------------------------
# Discovery: every Actuator, in every place it is declared
# ---------------------------------------------------------------------------


def _fuzzer_actuators() -> list[type]:
    return list(capability_subclasses(ActuatorCallOutPoint))


def _bundle_actuator_fields() -> list[tuple[CallOutBundle, str]]:
    """Each STOCHASTIC bundle field whose backend is a fuzzer Actuator."""
    fields: dict[tuple[type, str], tuple[CallOutBundle, str]] = {}
    for module in pkgutil.iter_modules(stochastic_pkg.__path__):
        loaded = importlib.import_module(
            f"{stochastic_pkg.__name__}.{module.name}"
        )
        for name, bundle in vars(loaded).items():
            if not (
                name.endswith("_STOCHASTIC")
                and isinstance(bundle, CallOutBundle)
            ):
                continue
            for field in dataclasses.fields(bundle):  # type: ignore[arg-type]
                if not field.name.endswith("_factory"):
                    continue
                node = unwrap_call_out(getattr(bundle, field.name)(field.name))
                if isinstance(node, ActuatorCallOutPoint):
                    fields[(type(bundle), field.name)] = (bundle, field.name)
    return [fields[k] for k in sorted(fields, key=lambda k: f"{k[0]}{k[1]}")]


_ACTUATORS = _fuzzer_actuators()
_ACTUATOR_FIELDS = _bundle_actuator_fields()


def _actuators_in(
    tree: py_trees.behaviour.Behaviour,
) -> list[ActuatorBackend]:
    return [
        node.decorated
        for node in tree.iterate()
        if isinstance(node, SynchronousCallOut)
        and isinstance(node.decorated, ActuatorBackend)
    ]


#: Every core tree builder that places an Actuator, with its default bundle.
_TREES: dict[str, functools.partial[py_trees.behaviour.Behaviour]] = {
    "prioritize": functools.partial(
        create_prioritize_subtree, case_id=CASE_ID, actor_id=ACTOR_ID
    ),
    "deploy": functools.partial(
        create_deploy_tree, case_id=CASE_ID, actor_id=ACTOR_ID
    ),
    "deploy_fix": functools.partial(
        create_deploy_fix_tree, case_id=CASE_ID, actor_id=ACTOR_ID
    ),
    "deploy_mitigation": functools.partial(
        create_deploy_mitigation_tree, case_id=CASE_ID, actor_id=ACTOR_ID
    ),
    "leave_case": functools.partial(
        create_leave_case_trigger_tree,
        actor_id=ACTOR_ID,
        case_id=CASE_ID,
        activity_builder=lambda case_manager_id: [],
        result_out={},
    ),
    "terminate_active_embargo": functools.partial(
        create_terminate_active_embargo_tree, case_id=CASE_ID, result_out={}
    ),
    "publication": functools.partial(create_publication_tree, case_id=CASE_ID),
    "publish_artifact": functools.partial(
        create_publish_artifact_tree, case_id=CASE_ID
    ),
}


def test_actuators_are_found():
    assert len(_ACTUATORS) > 1
    assert len(_ACTUATOR_FIELDS) > 1


# ---------------------------------------------------------------------------
# BT-18-041: one target per call
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-041")
@pytest.mark.parametrize("actuator", _ACTUATORS, ids=lambda c: c.__qualname__)
def test_every_fuzzer_actuator_is_an_actuator_backend(actuator):
    assert issubclass(actuator, ActuatorBackend)
    assert isinstance(actuator.contract, ActuatorContract)


@pytest.mark.spec("BT-18-041")
@pytest.mark.parametrize(
    ("bundle", "field_name"),
    _ACTUATOR_FIELDS,
    ids=[f"{type(b).__qualname__}.{f}" for b, f in _ACTUATOR_FIELDS],
)
def test_every_bundle_actuator_field_places_an_actuator_backend(
    bundle, field_name
):
    """Both the STOCHASTIC and the DETERMINISTIC default take a target."""
    for source in (bundle, type(bundle)()):
        node = actuator_call(
            getattr(source, field_name), field_name, target=CASE_ID
        )
        backend = unwrap_call_out(node)
        assert isinstance(backend, ActuatorBackend)
        assert isinstance(backend.contract, ActuatorContract)
        assert backend.target == CASE_ID


def test_every_deterministic_actuator_default_is_the_no_op_actuator():
    """The default acts on nothing, so a repeat repeats nothing (BT-18-044)."""
    for bundle, field_name in _ACTUATOR_FIELDS:
        backend = unwrap_call_out(getattr(type(bundle)(), field_name)("x"))
        # A NoOpActuator bound to the field's capability (BT-23-013).
        assert isinstance(backend, NoOpActuator), field_name
        assert type(backend).act is NoOpActuator.act, field_name
        # The ceiling default of a p > 0.5 call-out point (BT-23-002).
        assert isinstance(backend, AlwaysSucceed)


@pytest.mark.spec("BT-18-041")
@pytest.mark.parametrize("tree_name", sorted(_TREES))
def test_every_tree_binds_each_actuator_to_one_target(tree_name):
    actuators = _actuators_in(_TREES[tree_name]())
    assert actuators, f"{tree_name} places no Actuator"
    for backend in actuators:
        assert backend.target, f"{tree_name}: {backend.name} has no target"


@pytest.mark.spec("BT-18-042")
@pytest.mark.spec("BT-18-043")
@pytest.mark.parametrize("tree_name", sorted(_TREES))
def test_no_two_actuators_in_a_tree_share_an_idempotency_id(tree_name):
    """One act runs the whole tree, so each call needs its own name or target."""
    calls = [
        (backend.name, backend.target)
        for backend in _actuators_in(_TREES[tree_name]())
    ]
    assert len(calls) == len(set(calls)), calls


@pytest.mark.spec("BT-18-041")
def test_core_trees_place_actuators_only_through_actuator_call():
    """No core tree calls an Actuator field's factory itself.

    A direct call would place the Actuator with no target; ``actuator_call``
    is the one way that binds it.  Every module under ``vultron/core`` and
    ``vultron/demo/fuzzer`` is scanned, not a list of trees.  A factory
    called under another name is not found here, and the tick-time refusal
    (``test_actuator_ticked_without_a_target_raises``) catches it.
    """
    names = sorted({field_name for _, field_name in _ACTUATOR_FIELDS})
    pattern = re.compile(rf"\b({'|'.join(names)})\s*\(")
    offenders = [
        f"{path.relative_to(_VULTRON)}:{n}"
        for root in _PLACEMENT_ROOTS
        for path in sorted(root.rglob("*.py"))
        if "call_out" not in path.parts
        for n, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]
    assert not offenders, offenders


@pytest.mark.spec("BT-18-041")
def test_every_module_that_places_an_actuator_has_a_tree_checked():
    """A new tree that places an Actuator joins ``_TREES``."""
    placing = {
        path.stem
        for path in _CORE_BEHAVIORS.rglob("*.py")
        if "call_out" not in path.parts
        and "actuator_call(" in path.read_text()
    }
    checked = {
        Path(importlib.import_module(tree.func.__module__).__file__ or "").stem
        for tree in _TREES.values()
    }
    assert placing <= checked, sorted(placing - checked)


@pytest.mark.spec("BT-18-041")
def test_actuator_ticked_without_a_target_raises():
    seam = guard_call_out_factory(NoOpActuator)("Unbound")
    with pytest.raises(CallOutContractError, match="no target"):
        seam.tick_once()


@pytest.mark.spec("BT-18-041")
def test_a_non_actuator_backend_is_refused_as_an_actuator():
    with pytest.raises(CallOutContractError, match="not an ActuatorBackend"):
        actuator_call(AlwaysSucceed, "NotAnActuator", target=CASE_ID)


@pytest.mark.spec("BT-18-041")
def test_an_actuator_call_is_bound_to_one_target():
    backend = unwrap_call_out(actuator_call(acts, "Once", target="urn:a"))
    assert isinstance(backend, ActuatorBackend)
    for again in ("urn:a", "urn:b"):
        with pytest.raises(CallOutContractError, match="one call per target"):
            backend.bind_target(again)


def test_actuator_contract_refuses_outputs():
    with pytest.raises(ValueError, match="BT-18-028"):
        ActuatorContract(outputs={"artifact": str})


def test_actuator_that_overrides_answer_is_refused():
    with refused_class("act\\(request\\)"):

        class _Answers(ActuatorBackend):
            def answer(self) -> CallOutAnswer:
                return CallOutAnswer.yes()


def test_actuator_that_inherits_another_answer_is_refused():
    """A base listed before ActuatorBackend cannot supply answer() either."""
    with refused_class("act\\(request\\)"):

        class _ConstantFirst(AlwaysSucceed, ActuatorBackend):
            pass


def test_a_refused_class_does_not_corrupt_a_bound_default():
    """A refused class is collected, so it cannot poison ABC caches (#6303).

    Left in ``ActuatorBackend.__subclasses__()`` with ``AlwaysSucceed``'s
    ABC cache, ``_ConstantFirst`` made ``isinstance(node, ActuatorBackend)``
    record a bound ``AlwaysSucceed`` default as not an ``AlwaysSucceed``.
    """
    from vultron.core.behaviors.call_out.capabilities.report_management.deploy_fix import (
        PrioritizeDeploymentCapability,
    )
    from vultron.core.behaviors.call_out.nodes import always_succeed_as

    with refused_class("act\\(request\\)"):

        class _ConstantFirst(AlwaysSucceed, ActuatorBackend):
            pass

    assert "_ConstantFirst" not in {
        cls.__name__ for cls in ActuatorBackend.__subclasses__()
    }
    node = always_succeed_as(PrioritizeDeploymentCapability)("probe")
    assert not isinstance(node, ActuatorBackend)
    assert isinstance(node, AlwaysSucceed)


def test_actuator_that_declares_another_contract_is_refused():
    with refused_class("ActuatorContract"):

        class _Binary(ActuatorBackend):
            contract = CallOutContract()


def test_actuator_with_no_act_names_act():
    class _Bare(ActuatorBackend):
        pass

    backend = _Bare("Bare")
    backend.bind_target(CASE_ID)
    with pytest.raises(NotImplementedError, match="act\\(\\)"):
        tick_call_out(backend)


# ---------------------------------------------------------------------------
# BT-18-042: one call per target
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-042")
def test_publication_tree_makes_one_actuator_call_per_artifact():
    targets = [
        b.target for b in _actuators_in(create_publication_tree(CASE_ID))
    ]
    assert targets == [
        advisory_target(CASE_ID, label)
        for label in ("Exploit", "Fix", "Report")
    ]
    assert len(set(targets)) == len(targets)


# ---------------------------------------------------------------------------
# BT-18-043: an idempotency id derived from the act and the target
# ---------------------------------------------------------------------------


def _received(activity_id: str) -> VultronEvent:
    return VultronEvent(
        semantic_type=MessageSemantics.UNKNOWN,
        activity_id=activity_id,
        actor_id=SENDER_ID,
    )


def _request_in_run(
    target: str,
    activity: VultronEvent | None,
    name: str = "Act",
    *,
    ticks: int = 1,
) -> list[ActuationRequest]:
    """The requests one call gets in *ticks* ticks of a run carrying *activity*."""
    run = py_trees.blackboard.Client(name="actuation-test-run")
    run.register_key("actor_id", Access.WRITE)
    run.actor_id = ACTOR_ID
    if activity is not None:
        run.register_key("activity", Access.WRITE)
        run.activity = activity
    backend = unwrap_call_out(actuator_call(acts, name, target=target))
    assert isinstance(backend, FixedAnswerActuator)
    for _ in range(ticks):
        assert tick_call_out(backend) == Status.SUCCESS
    return backend.requests


@pytest.mark.spec("BT-18-043")
def test_idempotency_id_is_derived_from_the_act_and_the_target():
    first = _request_in_run("urn:a", _received("urn:act:1"))[0]
    assert first.target == "urn:a"
    assert first.idempotency_id == actuation_id(
        capability="Act", actor_id=ACTOR_ID, act_id="urn:act:1", target="urn:a"
    )
    # A re-run of the act, with a newly built tree, gets the same id.
    assert _request_in_run("urn:a", _received("urn:act:1")) == [first]
    others = {
        _request_in_run("urn:b", _received("urn:act:1"))[0].idempotency_id,
        _request_in_run("urn:a", _received("urn:act:2"))[0].idempotency_id,
        _request_in_run("urn:a", _received("urn:act:1"), "Other")[
            0
        ].idempotency_id,
    }
    assert first.idempotency_id not in others
    assert len(others) == 3


@pytest.mark.spec("BT-18-043")
def test_a_trigger_act_mints_its_own_id_once():
    """No received activity: each call mints its act's id once.

    Both calls run as one actor, on one target, under one name, so only the
    minted act id can tell their idempotency ids apart.
    """
    first_call = _request_in_run("urn:a", None, ticks=2)
    assert first_call[0] == first_call[1]
    (second_call,) = _request_in_run("urn:a", None)
    assert second_call.target == first_call[0].target
    assert second_call.idempotency_id != first_call[0].idempotency_id


@pytest.mark.spec("BT-18-043")
def test_a_received_act_with_no_actor_is_refused():
    """A received act's id is shared by every receiver, so the actor is required."""
    run = py_trees.blackboard.Client(name="actuation-test-run")
    run.register_key("activity", Access.WRITE)
    run.activity = _received("urn:act:1")
    backend = unwrap_call_out(actuator_call(acts, "Act", target="urn:a"))
    assert isinstance(backend, FixedAnswerActuator)
    with pytest.raises(CallOutContractError, match="no /actor_id"):
        tick_call_out(backend)


# ---------------------------------------------------------------------------
# AC-3: a re-run from holding after an error repeats no side effect
# ---------------------------------------------------------------------------


class _AdvisoryPlatform:
    """A fake external advisory platform that records each submission."""

    def __init__(self) -> None:
        self.submitted: list[str] = []
        self.acted_on: set[str] = set()
        self.unreachable: set[str] = set()
        self.unconfirmed: set[str] = set()
        self.credential_rejected = False


class _SubmitToPlatform(ActuatorBackend):
    """A reference Actuator that follows BT-18-040 and BT-18-044."""

    def __init__(self, name: str, platform: _AdvisoryPlatform) -> None:
        super().__init__(name)
        self._platform = platform

    def act(self, request: ActuationRequest) -> CallOutAnswer:
        platform = self._platform
        if request.idempotency_id in platform.acted_on:
            # Already done under this id: confirm it, do not repeat it.
            return CallOutAnswer.yes()
        if platform.credential_rejected:
            return CallOutAnswer.error(
                "advisory platform: credential rejected"
            )
        if request.target in platform.unreachable:
            return CallOutAnswer.error("advisory platform: unreachable")
        platform.submitted.append(request.target)
        if request.target in platform.unconfirmed:
            return CallOutAnswer.error("advisory platform: no confirmation")
        platform.acted_on.add(request.idempotency_id)
        return CallOutAnswer.yes()


def _publication_tree(platform: _AdvisoryPlatform):
    every_artifact = PublicationIntentDecision(
        publish_exploit=True, publish_fix=True, publish_report=True
    )
    return create_publication_tree(
        CASE_ID,
        call_out=PublicationCallOutBundle(
            prioritize_publication_intents_factory=yes_with(
                {INTENT_DECISION_KEY: every_artifact}
            ),
            prepare_exploit_factory=yes,
            prepare_fix_factory=yes,
            prepare_report_factory=yes,
            draft_advisory_artifact_factory=yes,
            review_advisory_draft_factory=yes,
            revise_advisory_draft_factory=yes,
            submit_advisory_artifact_factory=lambda name: _SubmitToPlatform(
                name, platform
            ),
        ),
    )


def _deliver(platform: _AdvisoryPlatform, activity: VultronEvent):
    """Process *activity* once: a delivery, or its re-run from holding."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    return run_tree(
        BTBridge(datalayer=dl),
        _publication_tree(platform),
        actor_id=ACTOR_ID,
        activity=activity,
    )


@pytest.mark.spec("BT-18-043")
@pytest.mark.spec("BT-18-044")
def test_rerun_from_holding_after_an_error_on_the_second_target_repeats_no_side_effect():
    exploit, fix, report = (
        advisory_target(CASE_ID, label)
        for label in ("Exploit", "Fix", "Report")
    )
    platform = _AdvisoryPlatform()
    platform.unreachable.add(fix)
    activity = _received("urn:act:held")

    held = _deliver(platform, activity)

    # The error on the second target leaves the act unjudged (BT-18-034).
    assert held.internal_error
    assert platform.submitted == [exploit]

    platform.unreachable.clear()
    rerun = _deliver(platform, activity)

    assert rerun.status == Status.SUCCESS
    # The first target's side effect is not repeated.
    assert platform.submitted == [exploit, fix, report]

    # A different act is another set of side effects, not a repeat.
    _deliver(platform, _received("urn:act:other"))
    assert platform.submitted == [exploit, fix, report] * 2


# ---------------------------------------------------------------------------
# The time budget (BT-18-027) holds an Actuator as it holds any backend
# ---------------------------------------------------------------------------


class _FakeStopwatch:
    def __init__(self) -> None:
        self.now = 1000.0

    def seconds(self) -> float:
        return self.now


class _TimedActuator(ActuatorBackend):
    """Records each request and advances the stopwatch by *took* per call."""

    def __init__(
        self, name: str, stopwatch: _FakeStopwatch, took: timedelta
    ) -> None:
        super().__init__(name)
        self._stopwatch = stopwatch
        self._took = took
        self.requests: list[ActuationRequest] = []

    def act(self, request: ActuationRequest) -> CallOutAnswer:
        self.requests.append(request)
        self._stopwatch.now += self._took.total_seconds()
        return CallOutAnswer.yes()


def _timed_call(
    took: timedelta,
) -> tuple[py_trees.behaviour.Behaviour, _TimedActuator]:
    stopwatch = _FakeStopwatch()
    node = actuator_call(
        lambda name: TimeBoundedCallOut(
            _TimedActuator(name, stopwatch, took),
            budget=timedelta(milliseconds=100),
            stopwatch=stopwatch,
        ),
        "Timed",
        target="urn:a",
    )
    backend = unwrap_call_out(node)
    assert isinstance(backend, _TimedActuator)
    return node, backend


@pytest.mark.spec("BT-18-027")
@pytest.mark.spec("BT-18-041")
def test_a_time_bounded_actuator_acts_once_per_tick_within_its_budget():
    node, backend = _timed_call(took=timedelta(milliseconds=10))
    assert isinstance(node, TimeBoundedCallOut)
    node.tick_once()
    assert node.status == Status.SUCCESS
    assert [r.target for r in backend.requests] == ["urn:a"]


@pytest.mark.spec("BT-18-027")
def test_an_actuator_past_its_budget_acts_once_and_raises():
    node, backend = _timed_call(took=timedelta(milliseconds=250))
    with pytest.raises(CallOutBudgetExceededError):
        node.tick_once()
    assert len(backend.requests) == 1


# ---------------------------------------------------------------------------
# BT-18-040: a side effect it cannot confirm, or a rejected credential, is error
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-040")
def test_unconfirmed_side_effect_answers_error_and_leaves_the_act_unjudged():
    fix = advisory_target(CASE_ID, "Fix")
    platform = _AdvisoryPlatform()
    platform.unconfirmed.add(fix)

    result = _deliver(platform, _received("urn:act:unconfirmed"))

    assert result.internal_error
    assert "advisory platform: no confirmation" in (result.feedback_message)
    # An error writes nothing: no refusal reason reaches the blackboard.
    assert (
        f"/{REFUSAL_REASON_KEY}" not in py_trees.blackboard.Blackboard.storage
    )
    # The run stopped at the unconfirmed target: the report was not tried.
    assert platform.submitted == [advisory_target(CASE_ID, "Exploit"), fix]


@pytest.mark.spec("BT-18-040")
def test_rejected_credential_answers_error_not_no():
    platform = _AdvisoryPlatform()
    platform.credential_rejected = True
    backend = _SubmitToPlatform("SubmitAdvisoryArtifact", platform)
    backend.bind_target(CASE_ID)

    assert backend.act(backend.request()).verdict is CallOutVerdict.ERROR
    with pytest.raises(CallOutBackendError, match="credential rejected"):
        tick_call_out(backend)
    assert platform.submitted == []
    assert (
        f"/{REFUSAL_REASON_KEY}" not in py_trees.blackboard.Blackboard.storage
    )

    # In a received act, the run is an internal error and nothing is sent.
    result = _deliver(platform, _received("urn:act:credential"))
    assert result.internal_error
    assert "credential rejected" in result.feedback_message
    assert platform.submitted == []
