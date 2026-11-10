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
"""Tests for the call-out seam (BT-18-011, ADR-0080, ADR-0183).

Covers:

- The answer type and the capability declaration (AC-1 of #6076): exactly one
  verdict with its own data; a declaration names *yes* and *no* ports, a
  reason at minimum.
- :class:`SynchronousCallOut` turns an answer into tree behaviour: *yes* writes
  the outputs and succeeds, *no* writes the refusal payload and fails, *error*
  raises :class:`CallOutBackendError` naming the node (AC-2).
- The seam rejects ``RUNNING``, a non-answer, a verdict outside the three, data
  the declaration does not name, a backend that is not a ``CallOutBackend``,
  and a backend ticked outside the seam, all with :class:`CallOutContractError`.
- Both errors surface through :class:`BTBridge` as ``internal_error=True``.
- :func:`guard_call_out_factory` is idempotent (no double-wrap).
- Every core DETERMINISTIC bundle hands out guard-wrapped nodes.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
from typing import Any

import py_trees
import pytest
from py_trees.common import Access, Status
from pydantic import ValidationError

from test.support.call_out import (
    FixedAnswerBackend,
    answering,
    tick_call_out,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out import bundles as core_bundles
from vultron.core.behaviors.call_out.answer import (
    REFUSAL_REASON_KEY,
    CallOutAnswer,
    CallOutContract,
    CallOutVerdict,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.guard import (
    CallOutBackendError,
    CallOutContractError,
    SynchronousCallOut,
    guard_call_out_factory,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.errors import VultronError

ACTOR_ID = "https://example.org/actors/test-actor"

_CONTRACT = CallOutContract(
    outputs={"probe_verdict": str, "probe_score": int},
    refusal_reason_key="probe_refusal_reason",
    refusal_fields={"probe_refusal_code": str},
)


class _RunningBackend(CallOutBackend):
    """A mis-wired call-out backend that returns RUNNING (forbidden)."""

    def update(self) -> Status:
        return Status.RUNNING


class _SilentBackend(CallOutBackend):
    """A backend that overrides update() and so gives the seam no answer."""

    def update(self) -> Status:
        return Status.SUCCESS


def _seam(fixed: CallOutAnswer, contract: CallOutContract = _CONTRACT):
    return SynchronousCallOut(
        FixedAnswerBackend("Probe", fixed=fixed, contract=contract)
    )


def _read(*keys: str) -> dict[str, object]:
    reader = py_trees.blackboard.Client(name="probe_reader")
    for key in keys:
        reader.register_key(key, Access.READ)
    return {key: getattr(reader, key) for key in keys if reader.exists(key)}


@pytest.fixture(autouse=True)
def _clean_blackboard():
    py_trees.blackboard.Blackboard.clear()
    yield
    py_trees.blackboard.Blackboard.clear()


@pytest.fixture
def bridge() -> BTBridge:
    return BTBridge(
        datalayer=SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    )


# ---------------------------------------------------------------------------
# AC-1: the answer type and the declaration
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-031")
def test_verdict_vocabulary_is_exactly_yes_no_error() -> None:
    assert {v.value for v in CallOutVerdict} == {"yes", "no", "error"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"verdict": "yes", "reason": "r"},
        {"verdict": "yes", "diagnostics": "d"},
        {"verdict": "no"},
        {"verdict": "no", "reason": "r", "outputs": {"k": "v"}},
        {"verdict": "no", "reason": "   "},
        {"verdict": "error"},
        {"verdict": "error", "diagnostics": "d", "refusal": {"k": "v"}},
        {"verdict": "maybe"},
    ],
)
@pytest.mark.spec("BT-18-031")
def test_answer_carries_only_its_own_verdicts_data(kwargs) -> None:
    """An answer has exactly one verdict and only that verdict's data."""
    with pytest.raises(ValidationError):
        CallOutAnswer(**kwargs)


@pytest.mark.spec("BT-18-001")
@pytest.mark.spec("BT-18-035")
def test_declaration_names_a_reason_port_at_minimum() -> None:
    assert dict(CallOutContract().refusal_ports) == {REFUSAL_REASON_KEY: str}
    assert dict(_CONTRACT.refusal_ports) == {
        "probe_refusal_reason": str,
        "probe_refusal_code": str,
    }
    assert dict(_CONTRACT.outputs) == {
        "probe_verdict": str,
        "probe_score": int,
    }


@pytest.mark.spec("BT-18-010")
def test_binary_declaration_names_no_outputs() -> None:
    """A binary-result capability declares an empty output-port set."""
    from vultron.core.behaviors.call_out.answer import BINARY_CONTRACT

    assert dict(BINARY_CONTRACT.outputs) == {}
    assert dict(AlwaysSucceed.contract.outputs) == {}


def test_declaration_refuses_a_blank_or_repeated_reason_key() -> None:
    with pytest.raises(ValueError):
        CallOutContract(refusal_reason_key=" ")
    with pytest.raises(ValueError):
        CallOutContract(refusal_reason_key="r", refusal_fields={"r": str})
    with pytest.raises(ValueError):
        CallOutContract(outputs={"k": str}, refusal_fields={"k": str})


# ---------------------------------------------------------------------------
# AC-2: the seam turns the answer into tree behaviour
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-002")
@pytest.mark.spec("BT-18-032")
def test_yes_writes_the_declared_outputs_and_succeeds() -> None:
    seam = _seam(CallOutAnswer.yes({"probe_verdict": "ok", "probe_score": 3}))
    seam.tick_once()
    assert seam.status == Status.SUCCESS
    assert _read("probe_verdict", "probe_score") == {
        "probe_verdict": "ok",
        "probe_score": 3,
    }
    assert _read("probe_refusal_reason") == {}


@pytest.mark.spec("BT-18-007")
@pytest.mark.spec("BT-18-032")
def test_no_writes_the_refusal_payload_and_fails() -> None:
    seam = _seam(
        CallOutAnswer.no("out of scope", {"probe_refusal_code": "SCOPE"})
    )
    seam.tick_once()
    assert seam.status == Status.FAILURE
    assert _read("probe_refusal_reason", "probe_refusal_code") == {
        "probe_refusal_reason": "out of scope",
        "probe_refusal_code": "SCOPE",
    }
    assert _read("probe_verdict") == {}


@pytest.mark.spec("BT-18-032")
def test_error_raises_naming_the_node_and_writes_nothing() -> None:
    seam = _seam(CallOutAnswer.error("policy service unreachable"))
    with pytest.raises(CallOutBackendError) as excinfo:
        seam.tick_once()
    assert excinfo.value.node_name == "Probe"
    assert "Probe" in str(excinfo.value)
    assert "policy service unreachable" in str(excinfo.value)
    # Diagnostics never reach the blackboard (ADR-0183).
    assert _read("probe_verdict", "probe_refusal_reason") == {}


def test_backend_error_is_not_a_vultron_error() -> None:
    assert not isinstance(CallOutBackendError("n", "d"), VultronError)
    assert isinstance(CallOutBackendError("n", "d"), RuntimeError)


@pytest.mark.spec("BT-18-032")
def test_error_answer_surfaces_as_internal_error(bridge: BTBridge) -> None:
    """Through the bridge, an error answer is an internal error, not FAILURE."""
    bt = bridge.setup_tree(
        tree=_seam(CallOutAnswer.error("unreachable")), actor_id=ACTOR_ID
    )
    result = bridge.execute_tree(bt)
    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "CallOutBackendError" in result.feedback_message
    assert "Probe" in result.feedback_message


def test_no_answer_is_a_protocol_failure_not_internal(
    bridge: BTBridge,
) -> None:
    bt = bridge.setup_tree(
        tree=_seam(CallOutAnswer.no("declined", {"probe_refusal_code": "X"})),
        actor_id=ACTOR_ID,
    )
    result = bridge.execute_tree(bt)
    assert result.status == Status.FAILURE
    assert result.internal_error is False


@pytest.mark.parametrize(
    "fixed",
    [
        pytest.param(
            CallOutAnswer.yes({"probe_verdict": "ok"}), id="yes-missing-port"
        ),
        pytest.param(
            CallOutAnswer.yes(
                {"probe_verdict": "ok", "probe_score": 1, "extra": "x"}
            ),
            id="yes-undeclared-port",
        ),
        pytest.param(
            CallOutAnswer.yes({"probe_verdict": "ok", "probe_score": "1"}),
            id="yes-wrong-type",
        ),
        pytest.param(
            CallOutAnswer.no("r", {"probe_refusal_code": "X", "other": 1}),
            id="no-undeclared-port",
        ),
        pytest.param(CallOutAnswer.no("r"), id="no-missing-field"),
        pytest.param(
            CallOutAnswer.no(
                "r",
                {"probe_refusal_code": "X", "probe_refusal_reason": ""},
            ),
            id="no-refusal-field-replaces-the-reason",
        ),
        pytest.param(
            CallOutAnswer.model_construct(verdict="maybe"),  # type: ignore[arg-type]
            id="verdict-outside-the-three",
        ),
    ],
)
@pytest.mark.spec("BT-18-002")
@pytest.mark.spec("BT-18-036")
def test_seam_rejects_data_its_declaration_does_not_name(fixed) -> None:
    seam = _seam(fixed)
    with pytest.raises(CallOutContractError) as excinfo:
        seam.tick_once()
    assert "Probe" in str(excinfo.value)


def test_an_object_typed_port_takes_any_value() -> None:
    """A port declared ``object`` is not type-checked."""
    contract = CallOutContract(outputs={"probe_any": object})
    seam = _seam(CallOutAnswer.yes({"probe_any": 3}), contract)
    seam.tick_once()
    assert seam.status == Status.SUCCESS
    assert _read("probe_any") == {"probe_any": 3}


def test_simulated_refusal_carries_zero_valued_refusal_fields() -> None:
    """A fuzzer *no* gives each declared refusal field a zero value."""
    from vultron.demo.fuzzer.base import AlwaysFail as FuzzAlwaysFail

    class _FuzzRefusal(FuzzAlwaysFail):
        contract = _CONTRACT

    answer = _FuzzRefusal("Fuzz").answer()
    assert answer.verdict is CallOutVerdict.NO
    assert answer.reason and "Fuzz" in answer.reason
    assert answer.refusal == {"probe_refusal_code": ""}
    assert tick_call_out(_FuzzRefusal("Fuzz")) == Status.FAILURE


@pytest.mark.spec("BT-18-036")
def test_seam_rejects_a_value_that_is_not_an_answer() -> None:
    class _NotAnAnswer(CallOutBackend):
        def answer(self):  # type: ignore[override]
            return Status.SUCCESS

    with pytest.raises(CallOutContractError):
        SynchronousCallOut(_NotAnAnswer("Bad")).tick_once()


def test_seam_rejects_a_backend_that_gives_no_answer() -> None:
    with pytest.raises(CallOutContractError):
        SynchronousCallOut(_SilentBackend("Silent")).tick_once()


@pytest.mark.spec("BT-18-033")
def test_seam_refuses_a_backend_that_is_not_a_call_out_backend() -> None:
    with pytest.raises(CallOutContractError) as excinfo:
        SynchronousCallOut(py_trees.behaviours.Success(name="Raw"))
    assert "Raw" in str(excinfo.value)


def test_guarded_factory_refuses_a_raw_behaviour_when_built() -> None:
    factory = guard_call_out_factory(
        lambda name: py_trees.behaviours.Failure(name=name)
    )
    with pytest.raises(CallOutContractError):
        factory("Raw")


@pytest.mark.spec("BT-18-037")
def test_backend_ticked_outside_the_seam_raises() -> None:
    """No tree reads an answer itself: a bare backend refuses to tick."""
    tree = py_trees.composites.Sequence(
        name="Tree", memory=False, children=[AlwaysSucceed("Bare")]
    )
    with pytest.raises(CallOutContractError) as excinfo:
        tree.tick_once()
    assert "Bare" in str(excinfo.value)


@pytest.mark.spec("BT-18-037")
def test_backend_unwrapped_from_its_seam_refuses_a_direct_tick() -> None:
    """A seam parent is not enough: only the seam's own tick is admitted."""
    seam = SynchronousCallOut(AlwaysSucceed("Unwrapped"))
    with pytest.raises(CallOutContractError) as excinfo:
        unwrap_call_out(seam).tick_once()
    assert "Unwrapped" in str(excinfo.value)
    seam.tick_once()
    assert seam.status == Status.SUCCESS


@pytest.mark.spec("BT-18-036")
@pytest.mark.parametrize(
    "port_type",
    [list[str], str | None, Any],
    ids=["generic-alias", "union", "any"],
)
def test_declaration_refuses_a_port_type_the_seam_cannot_check(
    port_type: Any,
) -> None:
    with pytest.raises(ValueError, match="plain class"):
        CallOutContract(outputs={"probe_open": port_type})
    with pytest.raises(ValueError, match="plain class"):
        CallOutContract(refusal_fields={"probe_open": port_type})


def test_answer_is_read_once_per_tick() -> None:
    """The seam takes the answer, so a stale one is never read again."""
    backend = FixedAnswerBackend("Once", fixed=CallOutAnswer.yes())
    assert tick_call_out(backend) == Status.SUCCESS
    assert backend.take_answer() is None


def test_answering_factory_is_guarded_by_a_bundle() -> None:
    from vultron.core.behaviors.call_out.bundles import (
        CaseProposalCallOutBundle,
    )

    bundle = CaseProposalCallOutBundle(
        evaluate_proposal_factory=answering(CallOutAnswer.no("closed")),  # type: ignore[arg-type]
    )
    node = bundle.evaluate_proposal_factory("EvaluateCaseProposal")
    node.tick_once()
    assert isinstance(node, SynchronousCallOut)
    assert node.status == Status.FAILURE
    assert _read(REFUSAL_REASON_KEY) == {REFUSAL_REASON_KEY: "closed"}


# ---------------------------------------------------------------------------
# RUNNING is still refused (BT-18-011)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-011")
def test_guard_raises_call_out_contract_error_on_running() -> None:
    """A child returning RUNNING raises CallOutContractError naming the node."""
    guarded = SynchronousCallOut(_RunningBackend("BadBackend"))
    with pytest.raises(CallOutContractError) as excinfo:
        guarded.tick_once()
    assert "BadBackend" in str(excinfo.value)


@pytest.mark.spec("BT-18-011")
def test_call_out_contract_error_is_not_a_vultron_error() -> None:
    """The error MUST be a plain RuntimeError, not a VultronError (bridge classifies it)."""
    err = CallOutContractError("x")
    assert isinstance(err, RuntimeError)
    assert not isinstance(err, VultronError)


@pytest.mark.spec("BT-18-011")
def test_guard_passes_yes_as_success() -> None:
    guarded = SynchronousCallOut(AlwaysSucceed("Ok"))
    guarded.tick_once()
    assert guarded.status == Status.SUCCESS


@pytest.mark.spec("BT-18-011")
def test_guard_passes_no_as_failure() -> None:
    guarded = SynchronousCallOut(AlwaysFail("No"))
    guarded.tick_once()
    assert guarded.status == Status.FAILURE


def test_guard_is_name_transparent() -> None:
    """The guard adopts the child name; the child is reachable via unwrap."""
    child = AlwaysSucceed("EvaluateReportCredibility")
    guarded = SynchronousCallOut(child)
    assert guarded.name == "EvaluateReportCredibility"
    assert unwrap_call_out(guarded) is child


def test_unwrap_returns_node_when_not_guarded() -> None:
    node = AlwaysSucceed("Plain")
    assert unwrap_call_out(node) is node


# ---------------------------------------------------------------------------
# Bridge integration: RUNNING surfaces as internal_error
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-18-011")
def test_running_backend_surfaces_as_internal_error(bridge: BTBridge) -> None:
    """Through the bridge, a guarded RUNNING backend is an internal error.

    Not a protocol FAILURE: a mis-wired backend is a wiring bug, so the
    non-VultronError CallOutContractError must land in the bridge's
    ``except Exception`` branch (internal_error=True).
    """
    tree = SynchronousCallOut(_RunningBackend("BadBackend"))
    bt = bridge.setup_tree(tree=tree, actor_id=ACTOR_ID)

    result = bridge.execute_tree(bt)

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "CallOutContractError" in result.feedback_message


def test_success_backend_is_not_internal_error(bridge: BTBridge) -> None:
    tree = SynchronousCallOut(AlwaysSucceed("Ok"))
    bt = bridge.setup_tree(tree=tree, actor_id=ACTOR_ID)

    result = bridge.execute_tree(bt)

    assert result.status == Status.SUCCESS
    assert result.internal_error is False


# ---------------------------------------------------------------------------
# guard_call_out_factory idempotence
# ---------------------------------------------------------------------------


def test_guard_factory_wraps_produced_node() -> None:
    guarded_factory = guard_call_out_factory(AlwaysSucceed)
    node = guarded_factory("Node")
    assert isinstance(node, SynchronousCallOut)
    assert isinstance(unwrap_call_out(node), AlwaysSucceed)


def test_guard_factory_is_idempotent_on_factory() -> None:
    """Wrapping an already-guarded factory returns it unchanged."""
    once = guard_call_out_factory(AlwaysFail)
    twice = guard_call_out_factory(once)
    assert twice is once


def test_guard_factory_does_not_double_wrap_node() -> None:
    """A node that is already a SynchronousCallOut is not wrapped again."""

    def factory(name: str) -> py_trees.behaviour.Behaviour:
        return SynchronousCallOut(AlwaysSucceed(name))

    node = guard_call_out_factory(factory)("Node")
    assert isinstance(node, SynchronousCallOut)
    # Not doubly wrapped: the decorated child is the leaf, not another guard.
    assert not isinstance(unwrap_call_out(node), SynchronousCallOut)


# ---------------------------------------------------------------------------
# Bundle boundary (AC-2): every core DETERMINISTIC bundle guards its factories
# ---------------------------------------------------------------------------


def _core_deterministic_singletons() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mod_info in pkgutil.iter_modules(core_bundles.__path__):
        module = importlib.import_module(
            f"{core_bundles.__name__}.{mod_info.name}"
        )
        for name in dir(module):
            if not name.endswith("_DETERMINISTIC"):
                continue
            obj = getattr(module, name)
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                out[name] = obj
    return out


@pytest.mark.spec("BT-18-011")
def test_every_core_bundle_factory_is_guarded() -> None:
    """Every factory on every core DETERMINISTIC bundle yields a guarded node."""
    singletons = _core_deterministic_singletons()
    assert singletons, "no DETERMINISTIC bundle singletons discovered"
    for singleton_name, singleton in singletons.items():
        for f in dataclasses.fields(singleton):
            node = getattr(singleton, f.name)(f.name)
            assert isinstance(node, SynchronousCallOut), (
                f"{singleton_name}.{f.name} did not hand out a guard-wrapped "
                "node"
            )
