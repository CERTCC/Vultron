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

"""The joint models follow the state tables and composite invariants (#6067 AC-1)."""

import pytest

from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
    violation_pxa_em_entailment,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.baselines import (
    ONE_VENDOR_MODEL,
    TWO_VENDOR_MODEL,
    EmbargoEnd,
    Event,
    EventKind,
    JointModel,
    JointState,
    VendorPath,
)
from vultron.measure.baselines.walk import Step

K = EventKind


def _state(
    rm: RM = RM.START,
    vf: CS_vf = CS_vf.vf,
    d: CS_d = CS_d.d,
    pxa: CS_pxa = CS_pxa.pxa,
    em: EM = EM.NONE,
) -> JointState:
    return JointState((VendorPath(rm, vf, d),), pxa, em)


def _reachable(model: JointModel) -> set[JointState]:
    found = {model.initial}
    pending = [model.initial]
    while pending:
        for step in model.steps(pending.pop()):
            if step.state not in found:
                found.add(step.state)
                pending.append(step.state)
    return found


@pytest.mark.parametrize("rm", [RM.RECEIVED, RM.INVALID, RM.VALID])
def test_fix_readiness_before_acceptance_is_refused(rm):
    with pytest.raises(VultronInvalidStateTransitionError):
        ONE_VENDOR_MODEL.apply(_state(rm, CS_vf.Vf), Event(K.F, 1))


@pytest.mark.parametrize("rm", [RM.ACCEPTED, RM.DEFERRED, RM.CLOSED])
def test_fix_readiness_after_acceptance_is_allowed(rm):
    after = ONE_VENDOR_MODEL.apply(_state(rm, CS_vf.Vf), Event(K.F, 1))
    assert after.vendors[0].vf is CS_vf.VF


def test_vendor_awareness_is_report_receipt():
    after = ONE_VENDOR_MODEL.apply(ONE_VENDOR_MODEL.initial, Event(K.V, 1))
    assert after.vendors[0] == VendorPath(RM.RECEIVED, CS_vf.Vf, CS_d.d)


def test_a_report_is_never_closed_from_valid():
    with pytest.raises(VultronInvalidStateTransitionError):
        ONE_VENDOR_MODEL.apply(_state(RM.VALID, CS_vf.Vf), Event(K.CLOSED, 1))


def test_public_awareness_with_the_vendor_unaware_forces_awareness_next():
    after = ONE_VENDOR_MODEL.apply(ONE_VENDOR_MODEL.initial, Event(K.P))
    assert [s.event for s in ONE_VENDOR_MODEL.steps(after)] == [Event(K.V, 1)]


@pytest.mark.parametrize("signal", [K.P, K.A])
def test_a_threat_signal_ends_an_active_embargo_in_the_same_step(signal):
    before = _state(RM.RECEIVED, CS_vf.Vf, em=EM.ACTIVE)
    (step,) = [
        s for s in ONE_VENDOR_MODEL.steps(before) if s.event == Event(signal)
    ]
    assert step.state.em is EM.EXITED
    assert step.state.embargo_end is EmbargoEnd.THREAT_SIGNAL
    assert Event(K.EXIT_THREAT) in step.events


@pytest.mark.parametrize("signal", [K.P, K.A])
def test_a_threat_signal_cancels_a_pending_proposal(signal):
    pending = _state(RM.RECEIVED, CS_vf.Vf, em=EM.PROPOSED)
    (step,) = [
        s for s in ONE_VENDOR_MODEL.steps(pending) if s.event == Event(signal)
    ]
    assert step.state.em is EM.NONE
    assert step.state.embargo_end is None
    assert Event(K.EMBARGO_CANCELLED) in step.events


def test_no_embargo_starts_after_public_awareness():
    pending = _state(RM.RECEIVED, CS_vf.Vf, pxa=CS_pxa.Pxa, em=EM.PROPOSED)
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not allowed"
    ):
        ONE_VENDOR_MODEL.apply(pending, Event(K.EMBARGO_START))
    none = pending._replace(em=EM.NONE)
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not allowed"
    ):
        ONE_VENDOR_MODEL.apply(none, Event(K.EMBARGO_PROPOSED))
    # A proposal the model is handed in this state can still be rejected.
    assert (
        ONE_VENDOR_MODEL.apply(pending, Event(K.EMBARGO_REJECTED)).em
        is EM.NONE
    )


def test_an_embargo_exits_on_its_own_terms_or_otherwise_or_by_a_signal():
    active = _state(RM.RECEIVED, CS_vf.Vf, em=EM.ACTIVE)
    ends = {
        s.event: s.state.embargo_end
        for s in ONE_VENDOR_MODEL.steps(active)
        if s.state.em is EM.EXITED
    }
    assert ends == {
        Event(K.EXIT_OWN_TERMS): EmbargoEnd.OWN_TERMS,
        Event(K.EXIT_OTHER): EmbargoEnd.OTHER,
        Event(K.P): EmbargoEnd.THREAT_SIGNAL,
        Event(K.X): EmbargoEnd.THREAT_SIGNAL,
        Event(K.A): EmbargoEnd.THREAT_SIGNAL,
    }


@pytest.mark.parametrize(
    "model", [ONE_VENDOR_MODEL, TWO_VENDOR_MODEL], ids=["one", "two"]
)
def test_every_reachable_state_satisfies_the_composite_invariants(model):
    for state in _reachable(model):
        for vendor in state.vendors:
            assert not composite_state_violations(
                vendor.rm, vendor.vf, vendor.d
            )
            # Awareness and receipt are one step.
            assert (vendor.rm is RM.START) == (vendor.vf is CS_vf.vf)
        assert violation_pxa_em_entailment(state.pxa, state.em) is None
        assert (state.em is EM.EXITED) == (state.embargo_end is not None)


@pytest.mark.parametrize(
    "model", [ONE_VENDOR_MODEL, TWO_VENDOR_MODEL], ids=["one", "two"]
)
def test_every_walk_ends_with_every_event_done(model):
    ends = [s for s in _reachable(model) if not model.steps(s)]
    assert ends
    for state in ends:
        assert state.pxa is CS_pxa.PXA
        assert state.em in (EM.NONE, EM.EXITED)
        assert all(
            v == VendorPath(RM.CLOSED, CS_vf.VF, CS_d.D) for v in state.vendors
        )


def test_two_unaware_vendors_learn_of_publication_one_after_the_other():
    after = TWO_VENDOR_MODEL.apply(TWO_VENDOR_MODEL.initial, Event(K.P))
    assert {s.event for s in TWO_VENDOR_MODEL.steps(after)} == {
        Event(K.V, 1),
        Event(K.V, 2),
    }
    first = TWO_VENDOR_MODEL.apply(after, Event(K.V, 1))
    assert [s.event for s in TWO_VENDOR_MODEL.steps(first)] == [Event(K.V, 2)]


def test_one_vendors_fix_does_not_need_the_others_acceptance():
    state = JointState(
        (
            VendorPath(RM.ACCEPTED, CS_vf.Vf, CS_d.d),
            VendorPath(RM.RECEIVED, CS_vf.Vf, CS_d.d),
        ),
        CS_pxa.pxa,
        EM.NONE,
    )
    assert (
        TWO_VENDOR_MODEL.apply(state, Event(K.F, 1)).vendors[0].vf is CS_vf.VF
    )
    with pytest.raises(VultronInvalidStateTransitionError):
        TWO_VENDOR_MODEL.apply(state, Event(K.F, 2))


def test_a_model_needs_a_vendor():
    with pytest.raises(ValueError, match="at least one vendor"):
        JointModel(0)


def test_an_event_names_its_vendor():
    assert str(Event(K.ACCEPTED, 2)) == "Ac_2"
    assert str(Event(K.EXIT_OWN_TERMS)) == "ExOwn"


class _ConflictingModel(JointModel):
    """A model whose P step reaches a state another step reaches as another event."""

    def _pxa_steps(self, state):
        found = super()._pxa_steps(state)
        if state == self.initial:
            target = _state(RM.RECEIVED, CS_vf.Vf)
            found.append(Step(Event(K.P), target))
        return found


def test_two_steps_to_one_state_as_different_events_are_refused():
    model = _ConflictingModel(1)
    with pytest.raises(VultronInvalidStateTransitionError, match="different"):
        model.steps(model.initial)


@pytest.mark.parametrize(
    ("em", "event", "after"),
    [
        (EM.NONE, K.EMBARGO_PROPOSED, EM.PROPOSED),
        (EM.PROPOSED, K.EMBARGO_REJECTED, EM.NONE),
        (EM.ACTIVE, K.REVISION_PROPOSED, EM.REVISE),
        (EM.REVISE, K.REVISION_SETTLED, EM.ACTIVE),
    ],
)
def test_each_embargo_move_is_its_named_event(em, event, after):
    before = _state(RM.RECEIVED, CS_vf.Vf, em=em)
    assert ONE_VENDOR_MODEL.apply(before, Event(event)).em is after


def test_accepting_one_of_several_proposals_starts_the_embargo():
    # EM_TRANSITIONS lets ACCEPT move PROPOSED to REVISE: one proposal is
    # accepted while another stays pending, so the embargo starts.
    before = _state(RM.RECEIVED, CS_vf.Vf, em=EM.PROPOSED)
    starts = {
        s.state.em
        for s in ONE_VENDOR_MODEL.steps(before)
        if s.event == Event(K.EMBARGO_START)
    }
    assert starts == {EM.ACTIVE, EM.REVISE}
    with pytest.raises(VultronInvalidStateTransitionError, match="ambiguous"):
        ONE_VENDOR_MODEL.apply(before, Event(K.EMBARGO_START))
