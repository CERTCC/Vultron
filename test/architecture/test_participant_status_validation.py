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

"""Architecture ratchet: ParticipantStatus write validation is composed once.

BTND-10-002 requires the per-dimension transition rules, the role gates and the
cross-machine entailments applied to a ``ParticipantStatus`` write to be
composed into **one** evaluator that returns every violated rule, with every
validating node calling that evaluator rather than the individual predicates.

Sharing the individual predicates is not enough, which is the ISSUE-2906 lesson
this ratchet encodes: before ADR-0086 both nodes called
``is_valid_vf_transition()`` and friends directly, each enforced a subset the
other did not, and the overlap was duplicated with byte-identical message text
(ARCH-15-004).  Composing the *set* is what makes divergence impossible rather
than merely fixed — so the thing worth pinning is that no node reaches for a
member of the set on its own.

The population of validators is discovered structurally rather than from a
hand-maintained list, so a new one has to be classified before CI passes.  The
last section pins the ``force_rm_state`` quarantine so the enumerated exemption
list can only shrink.

Per specs/behavior-tree-node-design.yaml BTND-10-002, BTND-10-003;
specs/architecture.yaml ARCH-15-004.  ADR-0086.  Closes #3050 AC-9.
"""

import ast

from test.architecture import _corpus

# Modules whose classes validate a case-participant ParticipantStatus write.
_VALIDATING_NODE_MODULES: tuple[str, ...] = (
    "vultron/core/behaviors/case/nodes/participant/trigger_validation.py",
    "vultron/core/behaviors/case/nodes/participant/status.py",
)

# Modules that validate a transition and write a ParticipantStatus but are
# deliberately outside the shared evaluator's domain.  Each needs a reason, and
# `test_no_undeclared_participant_status_validator` fails when a module joins
# the population without appearing here or in _VALIDATING_NODE_MODULES.
#
# The divergence these exclusions record is tracked as type:Concern #3111.
_DECLARED_EXCLUSIONS: dict[str, str] = {
    # Report-phase RM latch: operates on a *report*, before a case exists, so
    # there is no case participant, no VF/D/PXA dimension and no role gate for
    # the shared evaluator to apply.  Its current state comes from
    # `_current_report_phase_rm_state` (report-scoped), not from
    # `resolve_participant_state_from_dl` (case-scoped).  Folding the two
    # lifecycles into one evaluator is a separate design question.
    "vultron/core/behaviors/report/nodes/rm_transitions.py": (
        "report-phase RM latch — pre-case lifecycle, RM only, report-scoped"
        " current state"
    ),
    # Receive path, not emit path.  It MUST NOT use the emit evaluator: it
    # adjudicates each dimension independently and carries the participant's
    # current value forward for refused ones (ADR-0061, RSH-05-001), which is
    # the opposite disposition by design — the two halves of Postel's maxim.
    # It already shares `composite_state_violations()`, which is the part both
    # paths genuinely have in common (#2906).
    "vultron/core/behaviors/status/nodes/_adjudication.py": (
        "receive path — per-dimension partial accept, deliberately the"
        " opposite disposition (ADR-0061, RSH-05-001)"
    ),
    # Replica-apply path (RSH-05-021), a third disposition distinct from both
    # emit and receive: the assertion was already made and validated by the
    # peer that emitted it, and this node decides whether the local replica can
    # *apply* the resulting ledger entry.  It MUST NOT use the emit evaluator.
    # The emit evaluator's role gates ask whether the *asserting* actor held
    # VENDOR/DEPLOYER, which this node neither knows nor is entitled to
    # re-adjudicate; it checks only the composite-state entailments, which are
    # actor-independent structural facts about the state itself.  Its refusal
    # is also different in kind — it emits Create(ProcessingFault) rather than
    # failing a caller's write (see EmitImpossibleStateFaultNode).
    "vultron/core/behaviors/sync/nodes/participant_status_effect.py": (
        "replica-apply path — applies a peer-validated ledger entry; no"
        " asserting-actor roles in hand, and refuses via ProcessingFault"
        " rather than by rejecting a local write (RSH-05-021)"
    ),
    # Shared evaluator infrastructure — constructs dimension objects to read
    # the participant's *current* state from a stored ParticipantStatus (the
    # carry-forward step in resolve_transition_context_or_report).  Not a
    # write site; it feeds *into* CreateParticipantStatusNode, which owns
    # the write.
    "vultron/core/behaviors/case/nodes/participant/common.py": (
        "evaluator infrastructure — reads current state into dimension objects"
        " for carry-forward; not a write site (ADR-0086)"
    ),
    # BOOTSTRAP write: seeds initial RM state for a brand-new case owner
    # participant.  No prior state exists so the transition adjacency rule
    # (BTND-10-001) has nothing to check; using the emit evaluator here would
    # falsely flag RM.RECEIVED as an invalid transition from a non-existent
    # previous state (ADR-0087).
    "vultron/core/behaviors/case/nodes/participant/owner.py": (
        "bootstrap write — seeds initial RmDimension(RM.RECEIVED) for a new"
        " owner participant; no prior state so transition validation is moot"
        " (ADR-0087)"
    ),
    # BOOTSTRAP write: seeds initial participant state (RECEIVED, VALID, or
    # ACCEPTED) during case-proposal receipt, before the case actor has any
    # prior RM history.  Same reasoning as owner.py: no prior state to compare
    # against, so the adjacency rule cannot apply.
    "vultron/core/behaviors/case/case_proposal_received_tree.py": (
        "bootstrap write — seeds initial RmDimension for new participants"
        " during case-proposal receipt; no prior state so transition rule"
        " is moot (ADR-0087)"
    ),
    # PREDICATE use only: constructs DDimension(state).is_fix_deployed() for
    # a guard condition.  The dimension object is never stored; this is not a
    # write site.
    "vultron/core/behaviors/report/nodes/deploy_fix.py": (
        "predicate use — DDimension(state).is_fix_deployed() for guards;"
        " not a ParticipantStatus write site"
    ),
    # PREDICATE use only: constructs VfDimension(state).is_fix_ready() for
    # a guard condition.  The dimension object is never stored.
    "vultron/core/behaviors/report/nodes/develop_fix_conditions.py": (
        "predicate use — VfDimension(state).is_fix_ready() for guards;"
        " not a ParticipantStatus write site"
    ),
    # Writes CaseStatus.pxa (the case-level PXA state), NOT ParticipantStatus.
    # This is a separate model type with its own lifecycle (ADR-0080); the
    # composed participant-status evaluator is scoped to ParticipantStatus
    # writes and does not apply here.
    "vultron/core/behaviors/status/nodes/case_status.py": (
        "writes CaseStatus.pxa, not ParticipantStatus — separate model type"
        " (ADR-0080); out of scope for the participant-status evaluator"
    ),
    # Receive-path PXA adjudication for CaseStatus (not ParticipantStatus).
    # Also receive-path in the same sense as _adjudication.py, but operates
    # on the case-level PXA dimension, not the participant dimensions.
    "vultron/core/behaviors/status/nodes/cs_dimension_filter.py": (
        "receive-path CaseStatus adjudication — PxaDimension for case-level"
        " PXA, not participant-level; different lifecycle (ADR-0080)"
    ),
}

# Dimension constructors that mark a module as writing participant state.
_DIMENSION_CONSTRUCTORS: frozenset[str] = frozenset(
    {"RmDimension", "VfDimension", "DDimension", "PxaDimension"}
)

# Individual rule predicates composed by participant_transition_violations().
# A validating node naming any of these has stopped composing and started
# picking, which is how the two paths diverged before ADR-0086.
_COMPOSED_PREDICATES: tuple[str, ...] = (
    "is_valid_rm_transition",
    "is_valid_vf_transition",
    "is_valid_d_transition",
    "is_valid_pxa_transition",
    "is_valid_cs_transition",
    "composite_state_violations",
    "violation_rm_vf_entailment",
    "violation_rm_d_entailment",
    "violation_vf_d_entailment",
)

# The shared entry point every validating node must go through.
_SHARED_ENTRY_POINT = "validate_participant_status_write"

# The evaluator the shared entry point must delegate to.
_SHARED_EVALUATOR = "participant_transition_violations"

# ---------------------------------------------------------------------------
# force_rm_state override — (path_relative_to_repo_root, occurrences)
#
# These sites advance a single departing actor to RM.CLOSED regardless of the
# rung its RM machine is on.  RM.CLOSED is reachable by adjacency only from
# ACCEPTED, INVALID or DEFERRED, so each is a non-adjacent RM write that the
# emit-side adjacency rule (BTND-10-001) would otherwise refuse.  This is a
# sanctioned self-declared-Leave override (CM-23-012, resolving #3106): a Leave
# is the departing actor's own authoritative closure act (ADR-0084), and the
# override never touches a non-leaving (bystander) participant.
#
# This list MUST only shrink.  Do not add entries: a new site would be forcing
# RM.CLOSED on some actor without a self-declared Leave to justify it.
# ---------------------------------------------------------------------------
_RM_FORCE_QUARANTINE: dict[str, int] = {
    "vultron/core/behaviors/sync/nodes/close_case_effect.py": 1,
    "vultron/core/behaviors/case/nodes/leave.py": 2,
}


def _module(rel_path: str) -> tuple[str, ast.AST]:
    """Return the cached ``(source, tree)`` for a repo-relative module.

    Goes through the shared corpus rather than reading and parsing directly
    (TB-13-003) — the module-level cache keeps every ratchet inside the
    per-test timeout budget.
    """
    target = _corpus.REPO_ROOT / rel_path
    for path, tree in _corpus.all_trees(target.parent):
        if path == target:
            source = dict(_corpus.all_sources(target.parent))[path]
            return source, tree
    raise AssertionError(f"{rel_path} is not in the architecture corpus")


def _module_source(rel_path: str) -> str:
    return _module(rel_path)[0]


def test_validating_nodes_do_not_call_individual_predicates() -> None:
    """No ParticipantStatus-write validator names a composed rule predicate.

    AC-9 / BTND-10-002.  The rules are reached only through the shared
    evaluator, so neither node can enforce a subset the other does not.
    """
    offenders: list[str] = []
    for rel_path in _VALIDATING_NODE_MODULES:
        _, tree = _module(rel_path)
        names = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        for predicate in _COMPOSED_PREDICATES:
            if predicate in names:
                offenders.append(f"{rel_path}: {predicate}")

    assert not offenders, (
        "These ParticipantStatus-write validators call an individual rule"
        " predicate directly instead of the shared evaluator"
        f" ({_SHARED_EVALUATOR}), re-introducing the subset divergence"
        " ADR-0086 removed (BTND-10-002, ARCH-15-004):\n"
        + "\n".join(f"  {o}" for o in offenders)
    )


def test_validating_nodes_call_the_shared_entry_point() -> None:
    """Both validators reach the evaluator, rather than skipping validation.

    The mirror of the test above: forbidding the predicates is only meaningful
    if the nodes are still validating.  BTND-10-003 additionally requires the
    write node to keep its own call rather than relying on the guard.
    """
    missing = [
        rel_path
        for rel_path in _VALIDATING_NODE_MODULES
        if _SHARED_ENTRY_POINT not in _module_source(rel_path)
    ]
    assert not missing, (
        f"These modules must validate via {_SHARED_ENTRY_POINT}()"
        " (BTND-10-002, BTND-10-003); the write node in particular MUST NOT"
        " assume the trigger guard ran, because five call sites bypass it:\n"
        + "\n".join(f"  {m}" for m in missing)
    )


def test_shared_entry_point_delegates_to_the_evaluator() -> None:
    """The shared entry point composes the rules rather than restating them."""
    source = _module_source(
        "vultron/core/behaviors/case/nodes/participant/common.py"
    )
    assert _SHARED_EVALUATOR in source, (
        f"{_SHARED_ENTRY_POINT}() must delegate to {_SHARED_EVALUATOR}()"
        " — it is the single composed rule set (BTND-10-002)"
    )
    for predicate in _COMPOSED_PREDICATES:
        assert predicate not in source, (
            f"{predicate} is composed by {_SHARED_EVALUATOR}(); calling it"
            " from the shared entry point re-implements part of the set"
        )


def _force_rm_state_sites() -> dict[str, int]:
    """Return {rel_path: count} for every ``force_rm_state`` keyword passed.

    Scans the whole of ``vultron/``, not just ``core/behaviors/``:
    ``CreateParticipantStatusNode`` is re-exported from
    ``vultron.core.behaviors.case.nodes.participant`` and constructible from any
    layer, so a narrower scan would let a new exemption in ``use_cases/``,
    ``adapters/`` or ``demo/`` through unnoticed.

    Counts any non-``False`` value rather than only a literal ``True``, so
    ``force_rm_state=some_flag`` cannot smuggle an exemption past the pin
    either.
    """
    found: dict[str, int] = {}
    for path, tree in _corpus.files_mentioning(
        "force_rm_state", under=_corpus.REPO_ROOT / "vultron"
    ):
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "force_rm_state":
                    continue
                literal_false = (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is False
                )
                if not literal_false:
                    count += 1
        if count:
            rel = str(path.relative_to(_corpus.REPO_ROOT)).replace("\\", "/")
            found[rel] = count
    return found


def test_no_undeclared_participant_status_validator() -> None:
    """Every module in vultron/core/behaviors/ that builds a participant dimension is declared.

    AC-8 (issue #3204): changed from "names a member predicate AND builds a
    dimension" to "**builds a participant dimension**" so the gate catches all
    dimension-constructing sites — including the three that were previously
    invisible because they never named a composed predicate.

    Discovers the population structurally from ``vultron/core/behaviors/``
    rather than trusting a hand-maintained list.  A new write site has to be
    classified before CI passes — either routed through the composed evaluator
    (in which case it joins ``_VALIDATING_NODE_MODULES``) or given a reason why
    the evaluator does not apply (in which case it joins
    ``_DECLARED_EXCLUSIONS``).
    """
    declared = set(_VALIDATING_NODE_MODULES) | set(_DECLARED_EXCLUSIONS)
    undeclared: list[str] = []
    behaviors_root = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"

    for path, tree in _corpus.files_mentioning(
        *_DIMENSION_CONSTRUCTORS, under=behaviors_root
    ):
        rel = str(path.relative_to(_corpus.REPO_ROOT)).replace("\\", "/")
        constructs_dimension = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DIMENSION_CONSTRUCTORS
            for node in ast.walk(tree)
        )
        if constructs_dimension and rel not in declared:
            undeclared.append(rel)

    assert not undeclared, (
        "These modules in vultron/core/behaviors/ construct a participant"
        " dimension object (RmDimension, VfDimension, DDimension, PxaDimension)"
        " and are neither in _VALIDATING_NODE_MODULES nor _DECLARED_EXCLUSIONS."
        " Add them with a reason (AC-8 / BTND-10-002):\n"
        + "\n".join(f"  {m}" for m in sorted(undeclared))
    )


def test_rm_force_quarantine_only_shrinks() -> None:
    """``force_rm_state=True`` appears at exactly the enumerated call sites.

    A new site fails this test, which is the point: forcing an RM state past
    the transition rule is a BTND-10-001 violation, and the protocol question
    behind the existing ones is still open (type:Concern).  Removing a site
    also fails, so the list stays honest — update ``_RM_FORCE_QUARANTINE``.
    """
    actual = _force_rm_state_sites()

    added = {
        path: count
        for path, count in actual.items()
        if count > _RM_FORCE_QUARANTINE.get(path, 0)
    }
    removed = {
        path: count
        for path, count in _RM_FORCE_QUARANTINE.items()
        if count > actual.get(path, 0)
    }

    messages: list[str] = []
    if added:
        messages.append(
            "NEW force_rm_state=True call site(s) — the RM transition rule may"
            " not be bypassed without settling the design question first"
            " (see type:Concern #3106, referenced on `force_rm_state`):\n"
            + "\n".join(
                f"  + {path} (now {count},"
                f" quarantined {_RM_FORCE_QUARANTINE.get(path, 0)})"
                for path, count in sorted(added.items())
            )
        )
    if removed:
        messages.append(
            "Quarantined force_rm_state=True site(s) are gone — good news;"
            " shrink _RM_FORCE_QUARANTINE to match:\n"
            + "\n".join(
                f"  - {path} (quarantined {count}, now {actual.get(path, 0)})"
                for path, count in sorted(removed.items())
            )
        )
    assert not messages, "\n\n".join(messages)
