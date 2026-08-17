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
"""Architecture ratchet: post-construction mutation safety for core models.

Pydantic v2 validates a model at **construction** only.  Because
``VultronBase.model_config`` does not set ``validate_assignment``, the same value
that is correctly rejected by the constructor is silently accepted by both
attribute assignment and in-place list mutation::

    case = VulnerabilityCase(case_participants=[wire_obj])  # ValidationError
    case.case_participants = [wire_obj]                     # accepted
    case.case_participants.append(wire_obj)                 # accepted

A wire-shaped object sitting in a core-shaped field does not raise when read — it
reads as absent, and the reader substitutes an initial state, silently resetting
the participant's ladder.  That is the #2232 / #2264 failure mode.

This module ratchets the three-step remediation planned in issue #2261 (steps:
#2293, #2294, #2295) and
decided in ADR-0064.  Each step owns one **backlog**: an exact set, asserted with
``==`` so it fails in *both* directions.

- The backlog **grows** → a new violation was introduced; triage it.
- An entry is **fixed but not removed** → the enumeration is stale; tick it off.

Neither direction can drift unnoticed, and each backlog has a companion
``xfail(strict=True)`` goal test.  ``strict=True`` is deliberate: when the last
entry is removed the goal test XPASSes, which **fails** the build and forces the
marker to be deleted.  The pre-existing ``strict=False`` markers for #1991/#1992
are what this pattern is correcting — a non-strict xfail keeps passing forever
after the work is done, so nobody is ever told to clean it up.

Spec: `specs/architecture.yaml` ARCH-21-001 through ARCH-21-005;
`specs/case-management.yaml` CM-27-001 through CM-27-003;
`specs/participant-role-management.yaml` PRM-03-003.
Reference: `docs/adr/0064-core-branch-validate-assignment.md`,
`notes/domain-validation.md`.

Related: issue #2261 (this ratchet), issue #2232 (the shape duality it protects
against), ADR-0062 (normalisation at ingress and persistence).
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import pytest
from pydantic import BaseModel

import vultron.core.models

_CORE_ROOT = Path("vultron/core")
_MODELS_PACKAGE = "vultron.core.models"

# ---------------------------------------------------------------------------
# Backlog 1 — ``mode="after"`` validators that assign to ``self`` (issue #2293,
# step 1 of #2261).  ``validate_assignment`` re-runs every ``mode="after"`` validator on
# each assignment, so a validator that writes to ``self`` re-enters itself.  A
# guarded one terminates at depth 2; an unguarded one recurses forever.  Turning
# the flag on before these are fixed aborts 400+ tests with ``RecursionError``
# and nothing else — the recursion masks every real type failure.
#
# The remedy (ADR-0064) is to derive in ``mode="before"``, where the derived
# value is still validated normally, rather than to reach for an escape hatch
# that writes the field unvalidated.
#
# Scope is ``vultron/core/`` only.  The wire branch has twelve validators of the
# same shape, and they are deliberately exempt: the wire branch never gets
# ``validate_assignment`` (ARCH-12-002), so they cannot recurse.
#
# This set may only SHRINK.
# ---------------------------------------------------------------------------
_SELF_ASSIGNING_AFTER_VALIDATORS: frozenset[str] = frozenset(
    {
        "vultron/core/models/base.py::CoreObject._set_type_from_class_name",
        "vultron/core/models/case.py::VulnerabilityCase._compute_genesis_hash_if_missing",
        "vultron/core/models/case.py::VulnerabilityCase._init_case_statuses",
        "vultron/core/models/case_ledger.py::HashChainLedgerRecord._compute_entry_hash",
        "vultron/core/models/case_ledger_entry.py::CaseLedgerEntry._set_id_from_case",
        "vultron/core/models/case_participant.py::CaseActorParticipant._set_role",
        "vultron/core/models/case_participant.py::CaseParticipant._init_participant_status_if_empty",
        "vultron/core/models/case_participant.py::CaseParticipant._set_name_if_empty",
        "vultron/core/models/case_participant.py::CoordinatorParticipant._set_role",
        "vultron/core/models/case_participant.py::DeployerParticipant._set_role",
        "vultron/core/models/case_participant.py::FinderParticipant._set_role",
        "vultron/core/models/case_participant.py::FinderReporterParticipant._set_accepted_status",
        "vultron/core/models/case_participant.py::FinderReporterParticipant._set_roles",
        "vultron/core/models/case_participant.py::OtherParticipant._set_role",
        "vultron/core/models/case_participant.py::ReporterParticipant._set_accepted_status",
        "vultron/core/models/case_participant.py::ReporterParticipant._set_role",
        "vultron/core/models/case_participant.py::VendorParticipant._set_role",
        "vultron/core/models/offer_record.py::VultronOfferRecord._set_id",
        "vultron/core/models/ownership_transfer_offer_record.py::VultronOwnershipTransferOfferRecord._set_id",
        "vultron/core/models/pending_case_inbox.py::VultronPendingCaseInbox._set_id",
        "vultron/core/models/pending_create_case_activity.py::PendingCreateCaseActivity._set_id",
        "vultron/core/models/replication_state.py::VultronReplicationState._set_id",
        "vultron/core/models/report_case_link.py::VultronReportCaseLink._set_id",
    }
)

# ---------------------------------------------------------------------------
# Backlog 2 — the classes that must carry ``validate_assignment`` directly
# (issue #2294, step 2 of #2261).  Every other core model inherits it from one of these,
# so the enumeration stays at ten entries rather than listing all 103 classes.
#
# ``VultronBase`` is **permanently excluded**, not a backlog item: it is the
# shared base of both branches (ARCH-12-001) and ARCH-12-002 requires it to stay
# lenient for the wire branch, since ``as_Base`` inherits it.  Setting the flag
# there is the one-line fix that looks right and is not — it produced the worst
# measured blast radius (747 failed + 423 errors) and breaks the wire contract.
#
# This set is a PLAN, verified against the live hierarchy by
# ``test_mixin_targets_cover_every_core_model``: adding a core model outside all
# ten subtrees fails that test rather than silently escaping coverage.
# ---------------------------------------------------------------------------
_VALIDATE_ASSIGNMENT_TARGETS: frozenset[str] = frozenset(
    {
        "DeadLetterRecord",
        "EmDimension",
        "HashChainLedgerRecord",
        "PecDimension",
        "PxaDimension",
        "RmDimension",
        "VfdDimension",
        "VultronEvent",
        "VultronObject",
        "VultronOutbox",
    }
)

# The ARCH-12-002 boundary: shared base, must stay lenient. Never a target.
_LENIENT_SHARED_BASE = "VultronBase"

# ---------------------------------------------------------------------------
# Backlog 3 — modules that mutate a shape-dual collection in place (issue #2295,
# step 3 of #2261).  ``validate_assignment`` does **not** close this door: ``.append()``
# is not an assignment, so Pydantic never sees it.  The remedy is the pattern
# PRM-03-001/PRM-05-004 already used for ``case_roles``, which drove direct
# ``case_roles`` mutation in ``vultron/`` to zero: a MUST-NOT spec entry,
# canonical mutators, and this scan.
#
# This set may only SHRINK.
# ---------------------------------------------------------------------------
_COLLECTION_MUTATION_BACKLOG: frozenset[str] = frozenset()

# Canonical mutator homes — permanently permitted, exactly as PRM-03-001 permits
# ``vultron/core/models/participant.py`` to mutate ``case_roles``.  The mutators
# themselves have to write the field; that is their job.
_CANONICAL_MUTATOR_MODULES: frozenset[str] = frozenset(
    {
        "vultron/core/models/case.py",
        "vultron/core/models/case_participant.py",
    }
)

# Collections whose items exist in incompatible wire and core shapes, so a
# wrong-shaped item is silently misread rather than loudly rejected (ADR-0036,
# SDO-03-002).
_SHAPE_DUAL_COLLECTIONS = (
    "case_participants",
    "case_statuses",
    "participant_statuses",
)

_MUTATION_RE = {
    field: re.compile(
        # Direct attribute access:  obj.field.append(...)  or  obj.field = ...
        rf"(?:\.{field}\s*(?:=(?!=)|\.\s*(?:append|extend|insert|remove|pop|clear))"
        # Aliased local variable named after the field:  field.append(...)
        rf"|\b{field}\s*\.\s*(?:append|extend|insert|remove|pop|clear))"
    )
    for field in _SHAPE_DUAL_COLLECTIONS
}


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------
def _is_after_validator(fn: ast.FunctionDef) -> bool:
    for decorator in fn.decorator_list:
        text = ast.unparse(decorator).replace("'", '"')
        if "model_validator" in text and '"after"' in text:
            return True
    return False


def _assigns_to_self(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                return True
    return False


def _find_self_assigning_after_validators() -> set[str]:
    """Return ``path::Class.method`` for each core after-validator writing to self."""
    found: set[str] = set()
    for path in sorted(_CORE_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (
            SyntaxError
        ):  # pragma: no cover - unparseable file is a build error
            continue
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
                if _is_after_validator(fn) and _assigns_to_self(fn):
                    found.add(f"{path.as_posix()}::{cls.name}.{fn.name}")
    return found


def _find_collection_mutation_modules() -> set[str]:
    """Return modules under ``vultron/core/`` that mutate a shape-dual collection."""
    found: set[str] = set()
    for path in sorted(_CORE_ROOT.rglob("*.py")):
        posix = path.as_posix()
        if posix in _CANONICAL_MUTATOR_MODULES:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("#"):
                continue
            if any(pattern.search(line) for pattern in _MUTATION_RE.values()):
                found.add(posix)
                break
    return found


def _core_model_classes() -> dict[str, type[BaseModel]]:
    """Every ``BaseModel`` subclass defined in ``vultron.core.models``.

    Walks the package so a newly added module is covered without registration.
    """
    classes: dict[str, type[BaseModel]] = {}
    for info in pkgutil.walk_packages(
        vultron.core.models.__path__, prefix=f"{_MODELS_PACKAGE}."
    ):
        module = importlib.import_module(info.name)
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj is not BaseModel
                and obj.__module__.startswith(_MODELS_PACKAGE)
            ):
                classes[obj.__qualname__] = obj
    return classes


def _lacks_validate_assignment(cls: type[BaseModel]) -> bool:
    return not cls.model_config.get("validate_assignment", False)


# ---------------------------------------------------------------------------
# Guard the guards — a detector that finds nothing makes every assertion vacuous
# ---------------------------------------------------------------------------
def test_detectors_are_not_vacuous():
    assert len(list(_CORE_ROOT.rglob("*.py"))) > 100, "core tree not found"
    assert len(_core_model_classes()) > 50, "core models did not import"


# ---------------------------------------------------------------------------
# Backlog 1 — after-validator self-assignment
# ---------------------------------------------------------------------------
def test_self_assigning_after_validator_backlog_is_exact():
    """The enumerated set must match reality, in both directions."""
    found = _find_self_assigning_after_validators()
    assert found == set(_SELF_ASSIGNING_AFTER_VALIDATORS), (
        'the set of core `mode="after"` validators that assign to `self` changed.\n'
        f"  newly violating: {sorted(found - _SELF_ASSIGNING_AFTER_VALIDATORS)}\n"
        f"  fixed but still listed: {sorted(_SELF_ASSIGNING_AFTER_VALIDATORS - found)}\n"
        "A validator that writes to `self` re-enters itself once"
        ' `validate_assignment` is on. Derive in `mode="before"` instead'
        " (ADR-0064, issue #2293)."
    )


@pytest.mark.xfail(
    strict=True,
    reason='Goal state for issue #2293 (#2261 step 1): no core `mode="after"` validator'
    " assigns to `self`. 23 known sites remain, enumerated in"
    " _SELF_ASSIGNING_AFTER_VALIDATORS. When the last one is fixed this test"
    " XPASSes and fails the build — delete the marker and the backlog then.",
)
def test_no_core_after_validator_assigns_to_self():
    found = _find_self_assigning_after_validators()
    assert not found, (
        f'{len(found)} core `mode="after"` validators still assign to `self`:'
        f" {sorted(found)}"
    )


# ---------------------------------------------------------------------------
# Backlog 2 — validate_assignment coverage on the core branch
# ---------------------------------------------------------------------------
def test_mixin_targets_cover_every_core_model():
    """Every core model must inherit from one of the ten enumerated targets.

    This is what keeps the plan honest as the hierarchy evolves: a new core
    model added outside all ten subtrees fails here rather than silently
    escaping ``validate_assignment`` coverage once step 2 lands.
    """
    classes = _core_model_classes()
    uncovered = sorted(
        name
        for name, cls in classes.items()
        if name != _LENIENT_SHARED_BASE
        and name not in _VALIDATE_ASSIGNMENT_TARGETS
        and not any(
            ancestor.__qualname__ in _VALIDATE_ASSIGNMENT_TARGETS
            for ancestor in cls.__mro__[1:]
        )
    )
    assert not uncovered, (
        f"core models outside every _VALIDATE_ASSIGNMENT_TARGETS subtree: {uncovered}.\n"
        "Either give them a target ancestor or add them to the target set —"
        " otherwise they escape validate_assignment coverage (issue #2261)."
    )


def test_shared_base_is_never_a_target():
    """ARCH-12-002: ``VultronBase`` must stay lenient for the wire branch."""
    assert _LENIENT_SHARED_BASE not in _VALIDATE_ASSIGNMENT_TARGETS, (
        f"{_LENIENT_SHARED_BASE} is the shared base of both branches"
        " (ARCH-12-001); `as_Base` inherits it. Setting validate_assignment"
        " there violates ARCH-12-002 and breaks inbound wire parsing."
    )


def test_wire_branch_does_not_enable_validate_assignment():
    """ARCH-12-002: the wire branch stays lenient. Must hold now and after step 2."""
    from vultron.wire.as2.vocab.base.registry import VOCABULARY

    offenders = sorted(
        name
        for name, cls in VOCABULARY.items()
        if isinstance(cls, type)
        and issubclass(cls, BaseModel)
        and cls.__module__.startswith("vultron.wire")
        and cls.model_config.get("validate_assignment", False)
    )
    assert not offenders, (
        f"wire classes with validate_assignment enabled: {offenders}."
        " Inbound wire data is legitimately loose (ARCH-12-002); strictness"
        " belongs at the wire→core projection, not on the wire types."
    )


@pytest.mark.xfail(
    strict=True,
    reason="Goal state for issue #2294 (#2261 step 2): every core model carries"
    " validate_assignment. Blocked on step 1 — flipping the flag first aborts"
    " 400+ tests with RecursionError. When step 2 lands this test XPASSes and"
    " fails the build — delete the marker then.",
)
def test_every_core_model_has_validate_assignment():
    lacking = sorted(
        name
        for name, cls in _core_model_classes().items()
        if name != _LENIENT_SHARED_BASE and _lacks_validate_assignment(cls)
    )
    assert not lacking, (
        f"{len(lacking)} core models accept unvalidated attribute assignment:"
        f" {lacking}"
    )


# ---------------------------------------------------------------------------
# Backlog 3 — in-place mutation of shape-dual collections
# ---------------------------------------------------------------------------
def test_collection_mutation_backlog_is_exact():
    """The enumerated set must match reality, in both directions."""
    found = _find_collection_mutation_modules()
    assert found == set(_COLLECTION_MUTATION_BACKLOG), (
        "the set of core modules mutating a shape-dual collection changed.\n"
        f"  newly violating: {sorted(found - _COLLECTION_MUTATION_BACKLOG)}\n"
        f"  fixed but still listed: {sorted(_COLLECTION_MUTATION_BACKLOG - found)}\n"
        f"Collections covered: {', '.join(_SHAPE_DUAL_COLLECTIONS)}. Route writes"
        " through the canonical mutators on VulnerabilityCase / CaseParticipant"
        " (issue #2295, ADR-0064)."
    )


def test_no_direct_shape_dual_collection_mutation_in_core():
    found = _find_collection_mutation_modules()
    assert not found, (
        f"{len(found)} core modules mutate a shape-dual collection directly:"
        f" {sorted(found)}"
    )


def test_canonical_mutator_modules_still_exist():
    """A stale allowlist entry silently widens the exemption."""
    missing = sorted(
        m for m in _CANONICAL_MUTATOR_MODULES if not Path(m).is_file()
    )
    assert not missing, (
        f"_CANONICAL_MUTATOR_MODULES names files that no longer exist: {missing}."
        " Remove them so the exemption does not outlive its reason."
    )
