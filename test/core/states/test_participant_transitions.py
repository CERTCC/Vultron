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

"""Unit tests for the shared ParticipantStatus write evaluator.

``participant_transition_violations()`` is the single composed rule set both
the trigger guard and the write node call (BTND-10-002).  These tests pin the
two properties ADR-0086 turns on:

* it reports **every** violated rule, not the first (EH-07-001) — the fix-one-
  resubmit loop ISSUE-2112 reported;
* it labels each violation root or derived by dimension overlap (EH-07-002), so
  thoroughness does not degrade into a wall of consequential errors.

Closes #3050 AC-1, AC-5, AC-10.
"""

from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.participant_transitions import (
    participant_transition_violations,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole


def _violations(**overrides):
    """Evaluate a write against a fully-initial participant unless overridden."""
    kwargs = {
        "current_rm": RM.START,
        "current_vf": None,
        "current_d": None,
        "current_pxa": CS_pxa.pxa,
    }
    kwargs.update(overrides)
    return participant_transition_violations(**kwargs)


class TestLegalWrites:
    """A legal write violates nothing."""

    def test_legal_rm_step_is_accepted(self):
        assert _violations(requested_rm=RM.RECEIVED) == []

    def test_same_state_write_is_a_confirmation_not_a_transition(self):
        """A snapshot records current state; re-asserting it is legitimate."""
        assert (
            _violations(current_rm=RM.VALID, requested_rm=RM.VALID) == []
        ), "re-confirming the current RM state is not a transition"

    def test_absent_dimension_is_unconstrained(self):
        """A None *current* vf is absence, not an initial state (ADR-0075).

        There is no baseline to measure a transition from, so no VF transition
        rule can fire — the role gate is what refuses the assertion.
        """
        assert (
            _violations(
                current_vf=None,
                requested_vf=CS_vf.VF,
                current_rm=RM.ACCEPTED,
                requested_rm=RM.ACCEPTED,
                actor_roles=[CVDRole.VENDOR],
            )
            == []
        )

    def test_unrequested_dimension_asserts_nothing(self):
        """None requested values are skipped rather than treated as initial."""
        assert _violations(current_rm=RM.CLOSED) == []


class TestReportsEveryViolation:
    """EH-07-001: rejecting as a unit does not license one reason."""

    def test_two_invalid_dimensions_report_both(self):
        """The gap ISSUE-2112 named: RM and PXA both illegal, both reported.

        Both are single-dimension rules over independent machines, so neither
        is a consequence of the other and a caller must be told about both to
        make the next submission succeed.
        """
        violations = _violations(
            requested_rm=RM.ACCEPTED,  # START → ACCEPTED skips the ladder
            requested_pxa=CS_pxa.PXA,  # pxa → PXA is not an adjacent step
        )

        assert [v.dimensions for v in violations] == [("rm",), ("pxa",)], (
            "both illegal dimensions must be reported, not just the first:"
            f" {[v.message for v in violations]}"
        )
        assert all(v.classification == "root" for v in violations)

    def test_role_gate_and_transition_on_one_dimension_both_report(self):
        """Two rules over the same dimension are still two violations."""
        violations = _violations(
            current_vf=CS_vf.vf,
            requested_vf=CS_vf.VF,  # skips Vf, and needs VENDOR
            current_rm=RM.ACCEPTED,
            actor_roles=[],  # no VENDOR
        )

        messages = " | ".join(v.message for v in violations)
        assert "CVDRole.VENDOR required" in messages
        assert "Invalid VF transition" in messages


class TestRootVsDerivedClassification:
    """EH-07-002: classify by dimension overlap, not a dependency graph."""

    def test_multi_dimension_rule_is_root_when_each_dimension_moved_legally(
        self,
    ):
        """The informative case: both legal alone, the *pair* impossible.

        ``Vf → VF`` is a legal vendor-path step and RM is not being moved at
        all, so neither dimension carries a fault of its own — but asserting a
        fix is ready while the report sits at RM.VALID is causally impossible
        (CSB-18-001).  That is a root finding, not a consequence.
        """
        (violation,) = _violations(
            current_rm=RM.VALID,
            current_vf=CS_vf.Vf,
            requested_vf=CS_vf.VF,
            actor_roles=[CVDRole.VENDOR],
        )

        assert violation.dimensions == ("rm", "vf")
        assert violation.classification == "root", (
            "no single-dimension violation exists, so the entailment is the"
            f" root cause: {violation.message}"
        )

    def test_same_rule_is_derived_when_a_dimension_independently_failed(self):
        """The identical entailment, now a consequence of the VF fault.

        ``vf → VF`` skips ``Vf``, so ``vf`` carries a single-dimension
        violation.  The RM↔VF entailment reads ``vf``, so it is a downstream
        effect of the same mistake and must be labelled derived — one fix
        clears both.
        """
        violations = _violations(
            current_rm=RM.VALID,
            current_vf=CS_vf.vf,
            requested_vf=CS_vf.VF,
            actor_roles=[CVDRole.VENDOR],
        )

        by_dimensions = {v.dimensions: v for v in violations}
        assert by_dimensions[("vf",)].classification == "root"

        entailment = by_dimensions[("rm", "vf")]
        assert entailment.classification == "derived", (
            "the entailment reads vf, which already carries a single-dimension"
            " violation, so it is a consequence rather than a new problem"
        )

    def test_never_combination_is_root_for_a_role_holder(self):
        """A fix cannot be deployed before it exists — always a root finding.

        ``VfD`` is a never-combination, not a consequence of anything else: the
        actor holds both VENDOR and DEPLOYER, so no role gate fires, and ``d →
        D`` is a legal step on the deployer path taken alone.  A VENDOR+DEPLOYER
        reaching ``VF,D`` must pass through ``VF`` first, then ``D``.
        """
        violations = _violations(
            current_rm=RM.ACCEPTED,
            current_vf=CS_vf.Vf,  # fix NOT ready
            current_d=CS_d.d,
            requested_d=CS_d.D,  # deploy anyway
            actor_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        )

        assert violations, "Vf + D must be refused"
        assert all(v.classification == "root" for v in violations), (
            "nothing else is wrong with this request, so the impossible pair is"
            f" the root finding: {[(v.classification, v.message) for v in violations]}"
        )

    def test_role_gate_derives_its_entailments(self):
        """A refused claim's entailments are consequences of making the claim.

        A participant without DEPLOYER has no deployer path at all, so ``d`` is
        absent rather than at an initial state (ADR-0075).  The remediation for a
        role-gate violation is to stop asserting the dimension — an actor cannot
        grant itself a role — and dropping the claim clears the entailment too,
        which is what makes the entailment genuinely derived here.
        """
        asserted = _violations(
            current_rm=RM.VALID,
            current_d=None,  # no deployer path
            requested_d=CS_d.D,
            actor_roles=[CVDRole.REPORTER],
        )

        assert [(v.classification, v.dimensions) for v in asserted] == [
            ("root", ("d",)),
            ("derived", ("rm", "d")),
        ], [v.message for v in asserted]

        # Dropping the claim the actor was never entitled to make clears both.
        assert (
            _violations(
                current_rm=RM.VALID,
                current_d=None,
                requested_d=None,
                actor_roles=[CVDRole.REPORTER],
            )
            == []
        )

    def test_single_dimension_rule_is_always_root(self):
        """A one-dimension rule can never be derived, whatever else failed."""
        violations = _violations(
            requested_rm=RM.ACCEPTED,
            requested_pxa=CS_pxa.PXA,
        )
        assert all(
            v.classification == "root"
            for v in violations
            if len(v.dimensions) == 1
        )

    def test_every_violation_names_the_dimensions_it_reads(self):
        """AC-1: dimension naming is what makes the AC-5 test possible."""
        violations = _violations(
            current_rm=RM.VALID,
            current_vf=CS_vf.vf,
            requested_vf=CS_vf.VF,
            requested_pxa=CS_pxa.PXA,
            actor_roles=[CVDRole.VENDOR],
        )

        assert violations
        for violation in violations:
            assert violation.dimensions, violation.message
            assert set(violation.dimensions) <= {"rm", "vf", "d", "pxa"}


class TestRoleGates:
    """CSB-15-001 / CSB-15-002 / ADR-0075 are part of the composed set."""

    def test_vendor_aware_vf_requires_vendor_role(self):
        (violation,) = _violations(
            requested_vf=CS_vf.Vf, actor_roles=[CVDRole.REPORTER]
        )
        assert violation.dimensions == ("vf",)
        assert "ADR-0075" in violation.message
        assert "CVDRole.VENDOR" in violation.message

    def test_fix_ready_vf_role_gate_cites_csb_15_001(self):
        violations = _violations(
            current_rm=RM.ACCEPTED,
            requested_vf=CS_vf.VF,
            actor_roles=[CVDRole.REPORTER],
        )
        assert any("CSB-15-001" in v.message for v in violations)

    def test_any_d_assertion_requires_deployer_role(self):
        """#2963: the gate covers ``d`` too, not only ``D``.

        A non-DEPLOYER actor asserting the not-deployed state is still claiming
        a dimension it does not have.
        """
        for requested_d in (CS_d.d, CS_d.D):
            violations = _violations(
                current_rm=RM.ACCEPTED,
                requested_d=requested_d,
                actor_roles=[CVDRole.VENDOR],
            )
            assert any(
                "CVDRole.DEPLOYER" in v.message and v.dimensions == ("d",)
                for v in violations
            ), f"d={requested_d!r} must be gated on DEPLOYER (CSB-15-002)"

    def test_vendor_role_satisfies_the_vf_gate(self):
        assert (
            _violations(requested_vf=CS_vf.Vf, actor_roles=[CVDRole.VENDOR])
            == []
        )


class TestRmRuleQuarantine:
    """``validate_rm_transition=False`` suppresses one rule and nothing else."""

    def test_rm_rule_applies_by_default(self):
        (violation,) = _violations(requested_rm=RM.CLOSED)
        assert violation.dimensions == ("rm",)
        assert "Invalid RM transition" in violation.message

    def test_quarantine_suppresses_the_rm_rule(self):
        """The case-closure exemption: RM.CLOSED from any rung.

        Tracked as type:Concern #3106 — see ``force_rm_state`` on
        ``CreateParticipantStatusNode``.
        """
        assert (
            _violations(requested_rm=RM.CLOSED, validate_rm_transition=False)
            == []
        )

    def test_quarantine_leaves_every_other_rule_in_force(self):
        """It is an RM-rule exemption, not a validation bypass."""
        violations = _violations(
            requested_rm=RM.CLOSED,
            requested_vf=CS_vf.Vf,
            actor_roles=[CVDRole.REPORTER],
            validate_rm_transition=False,
        )
        assert [v.dimensions for v in violations] == [("vf",)]
        assert "CVDRole.VENDOR" in violations[0].message
