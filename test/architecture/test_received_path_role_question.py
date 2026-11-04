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

"""One role question per received message asks whether this receiver manages
the case (ADR-0153).

The sanctioned ways to ask it are
:func:`~vultron.core.participants.role_predicate.has_role` and the path door
stage the received-tree factory places with it.  Everything else is a site
the migration retires, and this module keeps the exact inventory of those
sites:

1. **Ratchet** :data:`KNOWN_ROLE_QUESTION_SITES`: every received-side site
   that asks the question another way.  Terminal value: empty, driven there
   by the Epic's migration waves: #5042 for the embargo trees, #5043 for the
   case, participant, report and status trees, #5044 for the sync, ledger
   and actor-offer trees and the role-gate registries, #5046 for the
   `Offer(VulnerabilityReport)` trees.  The last two entries go with the
   waves rather than with a wave of their own: ``role_gates.py`` goes when
   the last tree stops building a gate for itself, and ``sender_guard``'s
   fallback read is taken only when a tree passes no path stage, so it goes
   when the last tree declares.  #5044's AC-3 is what holds the set at empty
   afterwards.
2. **Pinned exemption set** :data:`SANCTIONED_ROLE_QUESTION_SITES`: the
   factory's own stage builders, whose CASE_MANAGER gate ADR-0153 keeps
   (BT-17-001 still holds for the manager path), and the trigger-side trees
   ADR-0153 does not govern.

Both are held to equality in both directions (ARCH-18-001, ARCH-18-002): a
new site fails, and so does a stale entry.

Why the entries are keyed on ``(module, shape)`` and not on the function
that performs the act: the migration waves rename and move the functions
that hold these sites, and a baseline keyed on a function name loses its
subjects to a rename while its non-empty guard still passes (#5535,
``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the Act, Not on
the Name of What Performs It").  The *shape* is the act — a role-gate
composite, a receiver-role condition node, an inline
"is the resolved manager me" comparison — and the module is where it lives.
A module that moves is reported as a new site and a stale one, loudly, in
the same run.

The detector itself is keyed on the act the same way: every pattern it
matches is read from the live object's ``__name__``, so renaming
``CheckIsCaseManagerNode``, the gate factories or the resolver changes what
the scan looks for and the same sites are still found.
:func:`test_the_detector_finds_every_shape` is the positive control that
survives the ratchet reaching zero: it feeds the detector a synthetic module
holding one of each shape and asserts all three are reported, so a detector
that has stopped seeing anything fails instead of passing vacuously.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from test.architecture import _authority_question, _corpus
from vultron.core.behaviors.case.nodes.conditions import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.received_path import ReceivedPathNode
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
    create_participant_replica_gated_tree,
)

#: The act, in the three shapes the code still writes it in.  Each label
#: names what the code does, not what performs it, so it survives a rename.
GATE = "role-gate composite"
CONDITION = "receiver-role condition node"
INLINE = "inline manager-is-me comparison"

#: Every pattern is read from the live object, so a rename moves the
#: detector with the code instead of blinding it.
_GATE_NAMES = frozenset(
    {
        create_case_manager_gated_tree.__name__,
        create_participant_replica_gated_tree.__name__,
    }
)
_CONDITION_NAME = CheckIsCaseManagerNode.__name__
_PATH_STAGE_NAME = ReceivedPathNode.__name__

#: The resolver, the predicate and the executing actor's own id attribute,
#: as ``_authority_question`` reads them off the live objects: the inline
#: shape below is that module's detector, so both ratchets judge the same
#: act (CS-22-001).
_RESOLVER_NAME = _authority_question.RESOLVER_NAME
_PREDICATE_NAME = _authority_question.PREDICATE_NAME
_EXECUTING_ACTOR_ATTR = _authority_question.EXECUTING_ACTOR_ATTR

_ROOTS = (
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors",
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "received",
)

_Site = tuple[str, str]

_B = "vultron/core/behaviors"
_C = f"{_B}/case"
_E = f"{_B}/embargo"

# ---------------------------------------------------------------------------
# 1. Received-side sites that still ask the role question another way.
#    Terminal value: empty.  Each wave of Epic #5193 moves a family of trees
#    onto the declaration and drops its entries in the same commit.
# ---------------------------------------------------------------------------
# owner: #5193
KNOWN_ROLE_QUESTION_SITES: frozenset[_Site] = frozenset(
    {
        # The gate composites' own role read.  ADR-0153 turns both
        # composites into declared path branches (HP-01-038), so this module
        # goes when the last tree declares its paths.
        (f"{_C}/nodes/role_gates.py", CONDITION),
        # The sender guard's own role read, for a tree that has not declared
        # its paths: with a declaration the arms read the path stage's
        # answer instead (HP-01-036).
        (f"{_B}/sender_guard/compose.py", CONDITION),
        # Gate-wrapped precondition guards a received tree passes.
        (f"{_C}/nodes/suggest_actor/conditions.py", GATE),
        (f"{_E}/nodes/answer_record.py", GATE),
        (f"{_E}/nodes/answer_repeat.py", GATE),
        (f"{_E}/nodes/relay_guards.py", GATE),
        # Received trees that gate work themselves instead of declaring the
        # path it belongs to.
        (f"{_E}/announce_teardown_tree.py", GATE),
        (f"{_B}/sync/announce_tree.py", CONDITION),
    }
)

# ---------------------------------------------------------------------------
# 2. Sites ADR-0153 does not retire: the factory's own stages, whose
#    CASE_MANAGER gate the record keeps for the manager path (BT-17-001),
#    and trigger-side trees, which the record does not govern.
# ---------------------------------------------------------------------------
# permanent: ADR-0153 (the factory's own gate stays; trigger side is out of
# scope)
SANCTIONED_ROLE_QUESTION_SITES: frozenset[_Site] = frozenset(
    {
        (f"{_C}/receive_stages/effects.py", GATE),
        (f"{_C}/receive_stages/guards.py", GATE),
        (f"{_C}/receive_stages/guards.py", CONDITION),
        (f"{_C}/receive_stages/tree.py", GATE),
        (f"{_C}/nodes/clock_decision_stage.py", GATE),
        (f"{_B}/sync/ledger_position_stage.py", GATE),
        # The trigger tree's role fork: a trigger runs on the actor's own
        # initiative, so no received path chooses it.
        (f"{_E}/trigger_tree.py", GATE),
    }
)


def _rel(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


def _calls(node: ast.AST) -> Iterator[str]:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and (
            name := _corpus.callee_name(sub.func)
        ):
            yield name


def shapes_in(tree: ast.AST) -> frozenset[str]:
    """The shapes of the role question *tree*'s module writes."""
    called = frozenset(_calls(tree))
    found: set[str] = set()
    if called & _GATE_NAMES:
        found.add(GATE)
    if _CONDITION_NAME in called:
        found.add(CONDITION)
    if _authority_question.compares_resolved_manager_with_the_receiver(tree):
        found.add(INLINE)
    return frozenset(found)


def _fragments() -> tuple[str, ...]:
    return (*_GATE_NAMES, _CONDITION_NAME, _RESOLVER_NAME)


@_corpus.gc_paused()
def _role_question_sites() -> frozenset[_Site]:
    """Every ``(module, shape)`` site in the received-side scan scope."""
    sites: set[_Site] = set()
    for root in _ROOTS:
        for path, tree in _corpus.files_mentioning(*_fragments(), under=root):
            rel = _rel(path)
            sites.update((rel, shape) for shape in shapes_in(tree))
    return frozenset(sites)


def _pinned_diff(
    label: str, actual: frozenset, known: frozenset, fix: str
) -> str:
    lines: list[str] = []
    if new := actual - known:
        lines.append(f"NEW {label} — {fix}:")
        lines.extend(f"  + {entry}" for entry in sorted(new))
    if stale := known - actual:
        lines.append(
            f"STALE {label} — remove the entry in the same commit"
            " (ARCH-18-002):"
        )
        lines.extend(f"  - {entry}" for entry in sorted(stale))
    return "\n".join(lines)


def _assert_pinned(
    label: str, actual: frozenset, known: frozenset, fix: str
) -> None:
    assert actual == known, "\n" + _pinned_diff(label, actual, known, fix)


@pytest.mark.spec("ARCH-18-001")
@pytest.mark.spec("HP-01-005")
def test_the_scan_finds_at_least_one_site() -> None:
    """The scan is never empty, so neither ratchet can pass vacuously.

    The factory's own stages and the path stage are permanent, so a scan
    that reports nothing means the detector stopped seeing the act — a
    renamed gate factory, a moved stage module, a reshaped corpus — and that
    is a failure, not a clean bill of health (#5535).
    """
    assert _role_question_sites(), (
        "the receiver-role question is asked nowhere under"
        f" {[_rel(root) for root in _ROOTS]} — the detector has gone blind;"
        " its patterns come from"
        f" {sorted(_GATE_NAMES | {_CONDITION_NAME, _RESOLVER_NAME})}"
    )


@pytest.mark.spec("ARCH-18-001")
@pytest.mark.spec("HP-01-005")
def test_received_side_role_question_sites_are_ratcheted() -> None:
    """Only the listed received-side sites ask the question another way."""
    sites = _role_question_sites() - SANCTIONED_ROLE_QUESTION_SITES
    _assert_pinned(
        "received-side receiver-role question site",
        sites,
        KNOWN_ROLE_QUESTION_SITES,
        "declare the tree's paths and read the path stage's answer, or ask"
        f" {_PREDICATE_NAME}() directly (ADR-0153)",
    )


@pytest.mark.spec("ARCH-18-005")
def test_sanctioned_role_question_sites_are_pinned() -> None:
    """The factory's own stages and the trigger side stay classified."""
    sites = _role_question_sites() & SANCTIONED_ROLE_QUESTION_SITES
    _assert_pinned(
        "sanctioned receiver-role question site",
        sites,
        SANCTIONED_ROLE_QUESTION_SITES,
        "a received tree declares its paths instead; a factory stage or a"
        " trigger tree is classified here with its reason",
    )


@pytest.mark.spec("ARCH-18-002")
def test_the_ratchet_has_entries_left_to_retire() -> None:
    """The ratchet is not yet at its terminal value.

    When the last entry goes, invert this assertion rather than deleting the
    module: the scan keeps covering every shape, so a site written again is
    reported instead of silently exempt
    (``notes/architecture-ratchet-corpus.md``).
    """
    assert KNOWN_ROLE_QUESTION_SITES, (
        "the migration is complete: replace this with an assertion that the"
        " scan reports no received-side site, and keep"
        " test_the_detector_finds_every_shape as the positive control"
    )


@pytest.mark.spec("ARCH-18-001")
def test_the_detector_finds_every_shape() -> None:
    """Each shape is still detectable, from a synthetic module holding it.

    The control that outlives the ratchet: it uses the live names, so a
    rename keeps it passing and a detector that no longer matches the act
    fails here even once no real site is left.
    """
    gate = sorted(_GATE_NAMES)[0]
    source = (
        f"def gated(children):\n"
        f"    return {gate}(name='n', case_id='c', children=children)\n"
        f"\n"
        f"def condition():\n"
        f"    return {_CONDITION_NAME}(case_id='c')\n"
        f"\n"
        f"class Node:\n"
        f"    def update(self):\n"
        f"        return {_RESOLVER_NAME}(case, self.datalayer)"
        f" == self.{_EXECUTING_ACTOR_ATTR}\n"
    )
    tree = _corpus.parse_inline(source, filename="<synthetic>")
    assert shapes_in(tree) == frozenset({GATE, CONDITION, INLINE})


@pytest.mark.spec("ARCH-18-001")
def test_the_detector_finds_the_comparison_a_statement_later() -> None:
    """Assigning the resolved manager first does not hide the comparison.

    The spelling both real sites use.  The detector matched only the
    one-liner at first, so two live sites were silently exempt and
    ARCH-18-001's "a new site fails" guarantee was void (#5041 review).
    """
    source = (
        f"class Node:\n"
        f"    def update(self):\n"
        f"        held = {_RESOLVER_NAME}(case, self.datalayer)\n"
        f"        if held == self.{_EXECUTING_ACTOR_ATTR}:\n"
        f"            return True\n"
        f"        return False\n"
    )
    tree = _corpus.parse_inline(source, filename="<synthetic>")
    assert INLINE in shapes_in(tree)


@pytest.mark.spec("ARCH-18-001")
def test_the_detector_ignores_a_comparison_about_another_actor() -> None:
    """A manager comparison against a local is not the receiver's question.

    ``sent_by_case_manager`` compares the resolved manager with the *ledger
    entry's* author, held in a local called ``actor_id``.  That is the
    sender's role, which ADR-0153 leaves legal, so the detector must not
    report it.
    """
    source = (
        f"def sent_by_case_manager(snapshot, case, dl):\n"
        f"    actor_id = snapshot['actor']\n"
        f"    return {_RESOLVER_NAME}(case, dl) == actor_id\n"
    )
    tree = _corpus.parse_inline(source, filename="<synthetic>")
    assert shapes_in(tree) == frozenset()


@pytest.mark.spec("HP-01-007")
def test_the_path_stage_asks_through_the_shared_predicate() -> None:
    """The path stage is the one place the question is asked for a path.

    The sanctioned home, checked by the act: the path stage's module calls
    the shared predicate, and does so without building a role gate or a
    receiver-role condition node of its own.  A rename of either name moves
    this check with the code; a path stage that started reading the roster
    itself would fail it.
    """
    path_stage_module = (
        _corpus.REPO_ROOT
        / "vultron"
        / "core"
        / "behaviors"
        / "case"
        / "nodes"
        / "received_path.py"
    )
    tree = _corpus.tree_of(path_stage_module)
    assert _PREDICATE_NAME in frozenset(_calls(tree)), (
        f"{_PATH_STAGE_NAME} must ask {_PREDICATE_NAME}() (HP-01-037)"
    )
    assert shapes_in(tree) == frozenset(), (
        "the path stage asks the role question through the shared predicate"
        f" alone, but it also writes {sorted(shapes_in(tree))}"
    )
