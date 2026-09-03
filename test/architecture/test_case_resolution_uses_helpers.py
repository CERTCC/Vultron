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
"""Architecture ratchet: case resolution goes through the unified helpers.

ADR-0087 unifies the "what to do when a case cannot be resolved" decision into
two canonical helpers in ``vultron/core/behaviors/helpers.py``:

- :func:`require_case` (``_require_case`` on the four DataLayer base classes) —
  **Regime 1**, authoritative coordination: an unresolvable case is an anomaly,
  reported as a single canonical ``Status.FAILURE`` at ``error`` level.
- :func:`resolve_case_replica` (``_resolve_case_replica``) — **Regime 2**,
  replica-apply of a remote ledger entry against a partial local store: an
  absent case is a routine skip (``Status.SUCCESS``, ``debug`` level).

Every other BT node that coordinates an existing case MUST use one of these
helpers instead of hand-rolling ``read_case(...) -> None -> Status.*``, which is
the per-site drift (#3101, silent / ``debug`` / ``warning`` / ``SUCCESS`` /
``FAILURE`` at random) that ADR-0087 eliminates.

This ratchet flags every direct ``.read_case(`` call under
``vultron/core/behaviors/`` (except ``helpers.py``, which *is* the unified
implementation), keyed by ``(relative_path, class-qualified function name)``.
The ``KNOWN_ALLOWLIST`` enumerates the sites that deliberately do NOT route
through the helpers, each falling into one of four examined categories:

- **Regime 2 / optional / best-effort seed** — absence is a legitimate skip
  (partial replica, optional enrichment). Cannot use ``require_case`` (which
  fails); ``resolve_case_replica`` is used where the node has ``self`` typed as
  a DataLayer node, but a few sites read directly for a bespoke skip verdict.
- **Regime 3 / case-under-construction** — the case may legitimately not exist
  yet (creation flows, idempotency probes, optional addressing enrichment).
- **Lenient guard / diagnostic** — the node returns ``FAILURE`` only to *signal*
  that an action is required; an unresolvable case means "nothing to do" →
  ``SUCCESS``, and the node never fails the tree on absence.
- **Module-level resolver** — a bare ``def`` taking ``datalayer``/``dl`` rather
  than a node, so it cannot call ``self._require_case``; it fails via ``None``
  return and the calling node returns ``FAILURE``.

The set is **exact**: a new direct ``read_case`` site fails the test (route it
through the helpers, or add it to ``KNOWN_ALLOWLIST`` with a category comment);
an allowlist entry that no longer appears also fails (remove it).

Spec: ADR-0087 (``docs/adr/0087-case-resolution-disposition-policy.md``).
Related: #3101, #2701, SYNC-02-002, ADR-0073.
"""

import ast

from test.architecture import _corpus

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"
_HELPERS = _BEHAVIORS_ROOT / "helpers.py"


class _ReadCaseScopeVisitor(ast.NodeVisitor):
    """Collect class-qualified scopes containing a ``.read_case(`` call."""

    def __init__(self) -> None:
        self._stack: list[str] = []
        self.scopes: set[str] = set()

    def _enter(self, node: ast.AST) -> None:
        self._stack.append(node.name)  # type: ignore[attr-defined]
        self.generic_visit(node)
        self._stack.pop()

    visit_ClassDef = _enter
    visit_FunctionDef = _enter
    visit_AsyncFunctionDef = _enter

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "read_case":
            self.scopes.add(".".join(self._stack) or "<module>")
        self.generic_visit(node)


def _read_case_scopes(tree: ast.AST) -> set[str]:
    """Return the class-qualified scope names holding a direct read_case call."""
    visitor = _ReadCaseScopeVisitor()
    visitor.visit(tree)
    return visitor.scopes


def _collect_sites() -> frozenset[tuple[str, str]]:
    """Return ``(relpath, scope)`` for every direct read_case under behaviors/."""
    sites: set[tuple[str, str]] = set()
    for py_file, tree in _corpus.files_mentioning(
        ".read_case(", under=_BEHAVIORS_ROOT
    ):
        if py_file == _HELPERS:
            continue
        rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
        for scope in _read_case_scopes(tree):
            sites.add((rel, scope))
    return frozenset(sites)


# ---------------------------------------------------------------------------
# Sanctioned direct-read_case sites (ADR-0087). Each entry is examined and
# carries an inline comment at the call site naming its regime. Categories:
#   R2  = Regime 2 / optional / best-effort seed (absence is a legitimate skip)
#   R3  = Regime 3 / case-under-construction / idempotency probe / optional
#         addressing enrichment
#   LEN = lenient guard / diagnostic (never fails the tree on absence)
#   MOD = module-level resolver (bare `dl`, fails via None -> caller FAILURE)
# ---------------------------------------------------------------------------
_CPR = "vultron/core/behaviors/case/case_proposal_received_tree.py"
_NODES = "vultron/core/behaviors/case/nodes"

KNOWN_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        # R3 — idempotency probes / audit-best-effort / seeds during the
        # CaseActor's proposal-received construction flow.
        (_CPR, "_AddCaseActorParticipantNode.update"),
        (_CPR, "_AddVendorOwnerParticipantNode.update"),
        (_CPR, "_AddReporterParticipantNode._already_has_participant"),
        (_CPR, "_CommitNativeLedgerEntriesNode.update"),
        (_CPR, "_SeedVendorOwnerSignatoryNode.update"),
        (_CPR, "_SeedReporterSignatoryNode._resolve_participant"),
        # R3 — optional addressing / stub enrichment; factory tolerates None.
        (f"{_NODES}/actor.py", "EmitInviteActorToCaseNode._emit"),
        (
            f"{_NODES}/communication.py",
            "CollectCaseAddresseesNode.update",
        ),
        (
            f"{_NODES}/ownership_transfer.py",
            "EmitOfferCaseOwnershipTransferNode._call_factory",
        ),
        (
            f"{_NODES}/ownership_transfer.py",
            "EmitAcceptCaseOwnershipTransferNode._call_factory",
        ),
        # R3 — condition testing "already a participant"; absent => FAILURE.
        (
            f"{_NODES}/suggest_actor/conditions.py",
            "ActorAlreadyParticipantNode.update",
        ),
        # R2 — defer-to-downstream / optional lookup / best-effort index write.
        (
            f"{_NODES}/participant/trigger_validation.py",
            "ValidateTriggerTransitionsNode.update",
        ),
        (
            f"{_NODES}/suggest_actor/emit.py",
            "RecordRecommendationRecommenderNode.update",
        ),
        (
            "vultron/core/behaviors/embargo/nodes/conditions.py",
            "OptionalLookupParticipantNode.update",
        ),
        # R3 — teardown addressing enrichment; upstream nodes fail on absence.
        (
            "vultron/core/behaviors/embargo/nodes/terminate.py",
            "SendTerminateEmbargoActivityNode._recipients",
        ),
        # LEN — lenient guards / diagnostics; never fail the tree on absence.
        (
            "vultron/core/behaviors/status/nodes/cs_invariant_diagnostic.py",
            "PxaEmInvariantDiagnosticNode.update",
        ),
        (
            "vultron/core/behaviors/status/nodes/lifecycle.py",
            "_PublicDisclosureSkipConditionNode.update",
        ),
        (
            "vultron/core/behaviors/status/nodes/threat_termination.py",
            "_ThreatTerminationSkipConditionNode._case_status_from_datalayer",
        ),
        (
            "vultron/core/behaviors/status/nodes/threat_termination.py",
            "_ThreatTerminationSkipConditionNode.update",
        ),
        # MOD — module-level resolvers (bare `dl`); fail via None -> caller.
        (f"{_NODES}/participant/common.py", "_create_and_attach_participant"),
        (f"{_NODES}/suggest_actor/emit.py", "_resolve_owner_recipient"),
        (f"{_NODES}/vfd_role_guards.py", "_resolve_actor_roles"),
    }
)


def test_case_resolution_routes_through_helpers():
    """Direct read_case sites in behaviors/ must be helper-based or allowlisted.

    See the module docstring for the ADR-0087 regime policy and the four
    allowlist categories.
    """
    actual = _collect_sites()
    new_sites = actual - KNOWN_ALLOWLIST
    resolved = KNOWN_ALLOWLIST - actual

    diff_lines: list[str] = []
    if new_sites:
        diff_lines.append(
            "NEW direct read_case sites (route case resolution through"
            " require_case/_require_case (Regime 1) or resolve_case_replica"
            " (Regime 2) per ADR-0087; if the site is a deliberate Regime 2/3/"
            "lenient/module-resolver exception, add it to KNOWN_ALLOWLIST with"
            " a category comment):"
        )
        diff_lines.extend(f"  + {p}::{s}" for p, s in sorted(new_sites))
    if resolved:
        diff_lines.append(
            "RESOLVED sites (remove these from KNOWN_ALLOWLIST — the direct"
            " read_case no longer appears, e.g. it was migrated to a helper):"
        )
        diff_lines.extend(f"  - {p}::{s}" for p, s in sorted(resolved))

    assert actual == KNOWN_ALLOWLIST, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests
# ---------------------------------------------------------------------------


def test_detector_flags_method_read_case() -> None:
    """The scanner reports the class-qualified scope of a read_case call."""
    tree = _corpus.parse_inline(
        "class FooNode:\n"
        "    def update(self):\n"
        "        case = self.datalayer.read_case(self.case_id)\n"
        "        return case\n"
    )
    assert _read_case_scopes(tree) == {"FooNode.update"}


def test_detector_flags_module_level_read_case() -> None:
    """A module-level resolver's read_case is reported under its function name."""
    tree = _corpus.parse_inline(
        "def _resolve(dl, case_id):\n" "    return dl.read_case(case_id)\n"
    )
    assert _read_case_scopes(tree) == {"_resolve"}


def test_detector_ignores_other_reads() -> None:
    """Non-read_case DataLayer calls (read, list_objects) are not flagged."""
    tree = _corpus.parse_inline(
        "class FooNode:\n"
        "    def update(self):\n"
        "        obj = self.datalayer.read(self.obj_id)\n"
        "        items = self.datalayer.list_objects('X')\n"
    )
    assert _read_case_scopes(tree) == set()
