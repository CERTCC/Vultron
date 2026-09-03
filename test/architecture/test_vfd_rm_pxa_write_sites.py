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

"""AC-7 architecture ratchet: audit VFD/RM/PXA dimension write sites.

AST-scans ``vultron/core/behaviors/`` for every ``VfdDimension``,
``RmDimension``, and ``PxaDimension`` constructor call and asserts the result
matches the audited set below.

A new unclassified constructor call fails this test immediately, which forces
an explicit audit decision:

- If the site is already protected (trigger guard, received-path filter, or a
  classified bootstrap/predicate use), add it to ``AUDITED_SITES`` with a
  comment stating why.
- If it is a new user-driven write outside the protected paths, add transition
  validation before merging.

Per specs/behavior-tree-node-design.yaml BTND-10-001.
Closes #2081 AC-7, #1903.
"""

import ast
from collections import Counter

from test.architecture import _corpus

# ---------------------------------------------------------------------------
# Audited sites — (path_relative_to_behaviors_root, constructor_name)
# One entry per call-site occurrence (multiplicity matters).
#
# Classification key:
#   PROTECTED  — write covered by transition validation.  For the trigger path
#                ValidateTriggerTransitionsNode runs first, and for the received
#                path FilterParticipantStatusDimensionsNode does — but neither
#                is what makes the write-node sites safe, because five call
#                sites reach CreateParticipantStatusNode through *neither*
#                (develop_fix.py, deploy_fix.py, close_case_effect.py and two
#                in leave.py).  What protects them is that the write node
#                validates its own writes against the shared evaluator
#                (BTND-10-001, BTND-10-003, ADR-0086); the upstream guard is
#                defence in depth, not the guarantee.  Three of those five
#                sites force RM.CLOSED and carry a documented `force_rm_state`
#                exemption (#3106) pinned by test_participant_status_validation.py.
#   BOOTSTRAP  — initial / authoritative seeding write; no prior state to
#                violate; outside the scope of transition validation
#   PREDICATE  — read-only dimension instantiation (guard / is_*() checks),
#                no DataLayer write
#   RM-TRACKED — RM transition nodes documented in rm_transitions.py;
#                tracked separately per BTND-10-001 / issue #2081
#   FILTER     — carry-forward writes inside FilterParticipantStatusDimensions-
#                Node (received path); the filter adjudicates before writing
#   REPLICATE  — authoritative ledger-replication write with monotonic ratchet
# ---------------------------------------------------------------------------
AUDITED_SITES: list[tuple[str, str]] = sorted(
    [
        # PROTECTED — CreateParticipantStatusNode validates its own writes.
        # One site per dimension, each constructed from the single
        # `_EffectiveStates` derivation that validation also read, so the node
        # cannot validate one value and persist another.  Was 3 VfDimension and
        # 2 DDimension before #3050 removed the dead vf half of
        # `_build_dimensions` and folded `_build_d_dimension` into the effective
        # states (ARCH-15-004).
        ("case/nodes/participant/status.py", "PxaDimension"),
        ("case/nodes/participant/status.py", "RmDimension"),
        ("case/nodes/participant/status.py", "VfDimension"),
        ("case/nodes/participant/status.py", "DDimension"),
        # BOOTSTRAP — case_proposal_received_tree: seeds RM.RECEIVED/VALID/ACCEPTED
        ("case/case_proposal_received_tree.py", "RmDimension"),
        ("case/case_proposal_received_tree.py", "RmDimension"),
        ("case/case_proposal_received_tree.py", "RmDimension"),
        # BOOTSTRAP — participant/common.py: initial accepted-status builder
        # (two entries removed: _ensure_reporter_participant and
        #  _upgrade_participant_to_accepted deleted in #2808)
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "RmDimension"),
        ("case/nodes/participant/common.py", "VfDimension"),
        ("case/nodes/participant/common.py", "DDimension"),
        # BOOTSTRAP — owner.py: initial owner RM state seeding
        ("case/nodes/participant/owner.py", "RmDimension"),
        ("case/nodes/participant/owner.py", "RmDimension"),
        # PREDICATE — deploy_fix.py: DDimension.is_fix_deployed()
        ("report/nodes/deploy_fix.py", "DDimension"),
        ("report/nodes/deploy_fix.py", "DDimension"),
        # PREDICATE — develop_fix_conditions.py: VfDimension.is_fix_ready()
        ("report/nodes/develop_fix_conditions.py", "VfDimension"),
        # RM-TRACKED — rm_transitions.py: the single report-phase RM write.
        # Was three near-identical sites (RM.VALID / RM.INVALID / RM.CLOSED);
        # collapsed to one `_ReportPhaseRMTransition._write_latch` in ISSUE-2548
        # so the latch has exactly one construction site (ARCH-15-004).
        ("report/nodes/rm_transitions.py", "RmDimension"),
        # FILTER — _adjudicate_dimensions carry-forward (extracted from dimension_filter.py)
        # One site per dimension: every refusal reason — role guard, omitted
        # assertion, non-monotone move, cross-machine entailment — carries the
        # participant's current value forward and so is spelled once, in
        # `_vf_carry` / `_d_carry` (ARCH-15-004, #2906).  Was 3 VfDimension and
        # 4 DDimension sites before those helpers were extracted.
        ("status/nodes/_adjudication.py", "PxaDimension"),
        ("status/nodes/_adjudication.py", "RmDimension"),
        ("status/nodes/_adjudication.py", "VfDimension"),
        ("status/nodes/_adjudication.py", "DDimension"),
        # FILTER — CaseStatus per-dimension carry-forward (ISSUE-2256)
        ("status/nodes/cs_dimension_filter.py", "PxaDimension"),
        # SNAPSHOT — EmitCaseStatusUpdateNode: post-mutation CaseStatus snapshot (ISSUE-2175)
        # Second PxaDimension: AC-1 _promote_pxa() result applied in AppendCaseStatusToCaseNode
        ("status/nodes/case_status.py", "PxaDimension"),
        ("status/nodes/case_status.py", "PxaDimension"),
        # REPLICATE — participant_status_effect.py: monotonic RM ratchet
        ("sync/nodes/participant_status_effect.py", "RmDimension"),
    ]
)

_TARGET_NAMES = {"VfDimension", "DDimension", "RmDimension", "PxaDimension"}
_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"


def _collect_sites() -> list[tuple[str, str]]:
    """Return sorted (rel_path, constructor_name) pairs from an AST scan."""
    found: list[tuple[str, str]] = []
    for path, tree in _corpus.files_mentioning(
        *_TARGET_NAMES, under=_BEHAVIORS_ROOT
    ):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name: str | None = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in _TARGET_NAMES:
                rel = str(path.relative_to(_BEHAVIORS_ROOT)).replace("\\", "/")
                found.append((rel, name))
    return sorted(found)


def test_audited_write_sites_unchanged() -> None:
    """All VfdDimension/RmDimension/PxaDimension sites match the audited set.

    A NEW site (file or extra call in an existing file) causes this test to
    fail with a clear diff so the reviewer can decide which classification
    label applies.  A REMOVED site also fails — the audited list must stay
    current.
    """
    actual = _collect_sites()
    actual_counts = Counter(actual)
    expected_counts = Counter(AUDITED_SITES)

    new_sites = actual_counts - expected_counts
    removed_sites = expected_counts - actual_counts

    messages: list[str] = []
    if new_sites:
        messages.append(
            "NEW unaudited dimension write sites found — classify and add to"
            " AUDITED_SITES:\n"
            + "\n".join(
                f"  + {path!r}  {ctor}" for path, ctor in sorted(new_sites)
            )
        )
    if removed_sites:
        messages.append(
            "Sites in AUDITED_SITES no longer present — remove from list:\n"
            + "\n".join(
                f"  - {path!r}  {ctor}" for path, ctor in sorted(removed_sites)
            )
        )
    assert not messages, "\n\n".join(messages)
