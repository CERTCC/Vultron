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

"""What paths the case, participant, report and status trees declare.

Every received tree in those areas declares the paths it handles once, to the
factory (HP-01-038), and a receiver on a path the declaration omits is
refused at the path stage with the composed reason (HP-01-039).  Two things
follow that a reader needs pinned, and this module pins both:

1. **The declaration itself**, in :data:`DECLARED_PATHS`, keyed on the tree
   factory that makes it rather than on the tree's name: several factories
   name their tree from a parameter, and a key on the name would lose its
   subject when a caller renames one (``notes/architecture-ratchet-corpus.md``
   § "Key a Ratchet on the Act, Not on the Name of What Performs It").  The
   set is held to equality in both directions, so a tree that stops
   declaring, starts declaring, or changes which paths it names fails here.
2. **The disposition at a non-manager receiver**, which is what the
   declaration decides (AC-3 of #5043): a tree that names the
   participant-replica path admits such a receiver, and one that does not
   refuses it, with the reason the composer gives that path.  One test per
   declared tree, driven from the same table.

How each declaration is read: the baseline is the non-empty sides of the use
case's declared sender rule, because an empty side already admits no sender
(HP-01-008) and HP-01-036 maps the sides onto the paths.  A side is narrowed
away only where the type is addressed to one role and the tree does no
protocol work on the other — a participant sends only to the CASE_MANAGER
(PCR-08-001), so an ``in_case`` rule whose kinds exclude ``CASE_MANAGER``
names a participant side no sender may legitimately use.  The no-case path
is added where the type precedes its case (HP-01-041).
"""

import ast
from pathlib import Path

import pytest
from py_trees.common import Status

from test.architecture import _corpus
from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    undeclared_path_reason,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

_FACTORY = "create_receive_activity_tree"

#: The areas #5043 migrated: the case, participant, report and status trees.
_ROOTS = (
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "case",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "report",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "status",
)

CM = ReceivedPath.CASE_MANAGER
PR = ReceivedPath.PARTICIPANT_REPLICA
NC = ReceivedPath.NO_CASE

#: ``(module, factory function, call index in it)`` — the call site that
#: makes the declaration.
Site = tuple[str, str, int]

_C = "vultron/core/behaviors/case"
_R = "vultron/core/behaviors/report"
_S = "vultron/core/behaviors/status"

#: Every declaration in these areas.  A conditional declaration records the
#: paths of its declaring branch; see :data:`CONDITIONAL`.
DECLARED_PATHS: dict[Site, frozenset[ReceivedPath]] = {
    # --- case: joining, invites and their replies -----------------------
    (
        f"{_C}/invite_actor_to_case_received_tree.py",
        "create_invite_actor_to_case_received_tree",
        0,
    ): frozenset({CM, PR, NC}),
    (
        f"{_C}/invite_actor_to_case_received_tree.py",
        "create_reject_invite_actor_to_case_received_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/accept_invite_tree.py",
        "create_accept_invite_actor_to_case_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/full_case_invite_trees.py",
        "create_invite_actor_to_full_case_received_tree",
        0,
    ): frozenset({CM, PR, NC}),
    (
        f"{_C}/full_case_invite_trees.py",
        "create_full_case_invite_reply_received_tree",
        0,
    ): frozenset({CM}),
    # --- case: participants and roles -----------------------------------
    (
        f"{_C}/case_participant_received_tree.py",
        "create_add_case_participant_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/case_participant_received_tree.py",
        "create_remove_case_participant_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/offer_case_participant_role_received_tree.py",
        "create_offer_case_participant_role_received_tree",
        1,
    ): frozenset({CM, PR}),
    (
        f"{_C}/offer_case_participant_role_received_tree.py",
        "create_offer_case_participant_role_received_tree",
        2,
    ): frozenset({CM, PR}),
    (
        f"{_C}/role_offer_answer_tree.py",
        "create_accept_case_participant_role_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/role_offer_answer_tree.py",
        "create_reject_case_participant_role_tree",
        0,
    ): frozenset({CM}),
    # --- case: actor offers already migrated by #5041 -------------------
    (
        f"{_C}/suggest_actor_tree.py",
        "create_receive_offer_case_participant_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/suggest_actor_tree.py",
        "create_accept_actor_recommendation_received_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/suggest_actor_tree.py",
        "create_reject_actor_recommendation_received_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/suggest_actor_tree.py",
        "create_recommendation_answer_received_tree",
        0,
    ): frozenset({PR}),
    # --- case: ownership transfer ---------------------------------------
    (
        f"{_C}/ownership_transfer_tree.py",
        "create_propose_ownership_transfer_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/ownership_transfer_tree.py",
        "create_offer_ownership_transfer_tree",
        0,
    ): frozenset({PR}),
    (
        f"{_C}/ownership_transfer_tree.py",
        "create_accept_ownership_transfer_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/ownership_transfer_tree.py",
        "create_reject_ownership_transfer_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/ownership_transfer_tree.py",
        "create_undo_ownership_transfer_tree",
        0,
    ): frozenset({CM, PR}),
    # --- case: lifecycle ------------------------------------------------
    (
        f"{_C}/announce_case_received_tree.py",
        "create_announce_vulnerability_case_received_tree",
        0,
    ): frozenset({CM, PR, NC}),
    (
        f"{_C}/create_case_received_tree.py",
        "create_create_case_received_tree",
        0,
    ): frozenset({PR, NC}),
    (
        f"{_C}/case_proposal_received_tree.py",
        "create_case_proposal_received_tree",
        0,
    ): frozenset({NC, CM}),
    (
        f"{_C}/accept_case_proposal_received_tree.py",
        "create_accept_case_proposal_received_tree",
        0,
    ): frozenset({NC}),
    (
        f"{_C}/reject_case_proposal_received_tree.py",
        "create_reject_case_proposal_received_tree",
        0,
    ): frozenset({NC}),
    (
        f"{_C}/add_report_received_tree.py",
        "create_add_report_to_case_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/receive_close_case_tree.py",
        "create_close_case_received_tree",
        2,
    ): frozenset({CM, PR}),
    (
        f"{_C}/refusal_notice_received_tree.py",
        "refusal_notice_received_tree",
        0,
    ): frozenset({PR}),
    # --- report ---------------------------------------------------------
    (f"{_R}/prioritize_tree.py", "create_engage_case_tree", 0): frozenset(
        {CM, PR}
    ),
    (f"{_R}/prioritize_tree.py", "create_defer_case_tree", 0): frozenset(
        {CM, PR}
    ),
    (
        f"{_R}/received_report_trees.py",
        "create_validate_report_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_R}/received_report_trees.py",
        "create_invalidate_report_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_R}/received_report_trees.py",
        "create_report_received_tree",
        0,
    ): frozenset({NC}),
    (
        f"{_R}/received_report_trees.py",
        "create_ack_report_received_tree",
        0,
    ): frozenset({NC}),
    (
        f"{_R}/received_report_trees.py",
        "create_close_report_received_tree",
        0,
    ): frozenset({NC}),
    # --- status ---------------------------------------------------------
    (f"{_S}/add_case_status_tree.py", "add_case_status_tree", 0): frozenset(
        {PR}
    ),
    (
        f"{_S}/add_participant_status_tree.py",
        "add_participant_status_tree",
        0,
    ): frozenset({CM, PR}),
}

#: Sites whose declaration is conditional on the tree naming a case at build
#: time.  The path stage runs before ``case_resolution`` (HP-01-040), so a
#: tree whose case only that stage resolves declares no paths; the factory
#: refuses the combination outright.
CONDITIONAL: frozenset[Site] = frozenset(
    {
        (
            f"{_R}/received_report_trees.py",
            "create_invalidate_report_received_tree",
            0,
        ),
    }
)

#: Sites that declare no paths, each with the reason.  A received *delivery*
#: always runs a tree that declares its paths; these are not that.
UNDECLARED: dict[Site, str] = {
    # The intake-only tree archives an activity it cannot act on and refuses
    # it for its own stated reason (CLP-10-018).  It names no case and does
    # no path-dependent work, so a path stage could only refuse it a second
    # time, with a reason about a role rather than the malformed activity.
    (
        f"{_C}/intake_only_received_tree.py",
        "create_incomplete_activity_received_tree",
        0,
    ): "intake-only refusal of an incomplete activity",
    (
        f"{_C}/intake_only_received_tree.py",
        "create_intake_only_received_tree",
        0,
    ): "intake-only archive of an activity with nothing to apply",
    # Same shape, inline in the tree factory: the activity names no case, so
    # the tree is the archive and the refusal.
    (
        f"{_C}/offer_case_participant_role_received_tree.py",
        "create_offer_case_participant_role_received_tree",
        0,
    ): "the Offer names no case, so the tree archives and refuses it",
    (
        f"{_C}/receive_close_case_tree.py",
        "create_close_case_received_tree",
        0,
    ): "the Leave names no sender, so the tree archives and refuses it",
    # The close arm runs inside the enclosing tree's CASE_MANAGER gate, so
    # the delivery's own tree already asked the role question once; a second
    # stage here would ask it again (HP-01-037).
    (
        f"{_C}/receive_close_case_tree.py",
        "create_close_case_received_tree",
        1,
    ): "a subtree of CloseCaseBT, inside its manager gate",
    # Offer(VulnerabilityReport) stores what it carried before it checks the
    # addressee, so its path declaration waits for that rework (#5046).
    (
        f"{_C}/receive_report_case_tree.py",
        "create_receive_report_case_tree",
        0,
    ): "owner: #5046",
    (
        f"{_C}/receive_report_case_tree.py",
        "create_offer_received_without_report_tree",
        0,
    ): "owner: #5046",
    # The Offer(Actor) tree migrates with the rest of the actor-offer family
    # (#5044).
    (
        f"{_C}/suggest_actor_tree.py",
        "create_recommend_actor_to_case_received_tree",
        0,
    ): "owner: #5044",
}


def _rel(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


def _paths_of(expr: ast.expr) -> frozenset[ReceivedPath] | None:
    """The declaration *expr* names, or ``None`` when it is not a set.

    A conditional declaration is read from its declaring branch, which is
    the one the factory places a stage for.
    """
    if isinstance(expr, ast.IfExp):
        return _paths_of(expr.body)
    if not isinstance(expr, ast.Set):
        return None
    found: set[ReceivedPath] = set()
    for element in expr.elts:
        if not isinstance(element, ast.Attribute):
            return None
        member = getattr(ReceivedPath, element.attr, None)
        if member is None:
            return None
        found.add(member)
    return frozenset(found)


@_corpus.gc_paused()
def _call_sites() -> tuple[
    dict[Site, frozenset[ReceivedPath] | None], frozenset[Site]
]:
    """Every factory call site in these areas, and which ones are conditional.

    Maps the site onto the paths it declares, ``None`` for a site that
    declares none.
    """
    declared: dict[Site, frozenset[ReceivedPath] | None] = {}
    conditional: set[Site] = set()
    for root in _ROOTS:
        for path, tree in _corpus.files_mentioning(_FACTORY, under=root):
            module = _rel(path)
            functions = [
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            calls = sorted(
                (
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and _corpus.callee_name(node.func) == _FACTORY
                ),
                key=lambda node: node.lineno,
            )
            seen: dict[str, int] = {}
            for node in calls:
                enclosing = max(
                    (
                        function
                        for function in functions
                        if function.lineno
                        <= node.lineno
                        <= (function.end_lineno or node.lineno)
                    ),
                    key=lambda function: function.lineno,
                    default=None,
                )
                name = enclosing.name if enclosing is not None else "<module>"
                index = seen.get(name, 0)
                seen[name] = index + 1
                site = (module, name, index)
                keyword = next(
                    (k for k in node.keywords if k.arg == "paths"), None
                )
                if keyword is None:
                    declared[site] = None
                    continue
                if isinstance(keyword.value, ast.IfExp):
                    conditional.add(site)
                declared[site] = _paths_of(keyword.value)
    return declared, frozenset(conditional)


def _diff(label: str, actual: frozenset, expected: frozenset) -> str:
    lines = [label]
    if new := actual - expected:
        lines.extend(["unlisted:", *(f"  + {entry}" for entry in sorted(new))])
    if gone := expected - actual:
        lines.extend(["stale:", *(f"  - {entry}" for entry in sorted(gone))])
    return "\n".join(lines)


@pytest.mark.spec("HP-01-038")
def test_every_factory_call_site_in_these_areas_is_accounted_for() -> None:
    """Each call site either declares its paths or is listed with its reason.

    The scan is the inventory, so a tree added to these areas without a
    declaration fails here instead of silently keeping the role gates
    (ARCH-18-001).
    """
    sites, _ = _call_sites()
    assert sites, (
        "no call site of"
        f" {_FACTORY} was found under {[_rel(root) for root in _ROOTS]} —"
        " the scan has gone blind"
    )
    undeclared = frozenset(
        site for site, paths in sites.items() if paths is None
    )
    assert undeclared == frozenset(UNDECLARED), _diff(
        "The set of call sites that declare no paths changed (HP-01-038):"
        " declare the tree's paths, or list the site here with its reason.",
        undeclared,
        frozenset(UNDECLARED),
    )


@pytest.mark.spec("HP-01-038")
def test_the_declared_paths_are_pinned() -> None:
    """Which paths each tree declares, held to equality in both directions."""
    sites, _ = _call_sites()
    actual = {
        site: paths for site, paths in sites.items() if paths is not None
    }
    assert actual == DECLARED_PATHS, _diff(
        "A tree's path declaration changed (HP-01-038). Update the table"
        " with the reason the receiver on that path is, or is not, addressed.",
        frozenset(actual.items()),
        frozenset(DECLARED_PATHS.items()),
    )


@pytest.mark.spec("HP-01-040")
def test_a_conditional_declaration_is_listed_with_its_reason() -> None:
    """Only the listed sites make their declaration conditional.

    A declaration conditional on anything but the tree naming a case at
    build time is a message type deciding its paths per delivery, which
    HP-01-038's "once" forbids.
    """
    _, conditional = _call_sites()
    assert conditional == CONDITIONAL, _diff(
        "The set of conditional path declarations changed (HP-01-038).",
        conditional,
        CONDITIONAL,
    )


CASE_ID = "https://example.org/cases/declared-paths"
MANAGER_ID = "https://example.org/actors/coordinator"
VENDOR_ID = "https://example.org/actors/vendor"
OWNER_ID = "https://example.org/actors/owner"


def _participant(suffix: str, actor_id: str, *roles: CVDRole):
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{suffix}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
    )


def _stage_at(actor_id: str, declared: frozenset[ReceivedPath]):
    """The path stage of a tree declaring *declared*, run in *actor_id*'s store."""
    manager = _participant("manager", MANAGER_ID, CVDRole.CASE_MANAGER)
    vendor = _participant("vendor", VENDOR_ID, CVDRole.VENDOR)
    scenario = BTTestScenario(actor_id=actor_id)
    scenario.seed(
        manager,
        vendor,
        VulnerabilityCase(
            id_=CASE_ID,
            name="DECLARED-PATHS",
            attributed_to=OWNER_ID,
            case_participants=[manager.id_, vendor.id_],
            actor_participant_index={
                MANAGER_ID: manager.id_,
                VENDOR_ID: vendor.id_,
            },
        ),
    )
    stage = ReceivedPathNode(
        declared=declared, case_id=CASE_ID, label="DeclaredPathsBT"
    )
    scenario.run(stage, actor_id=actor_id)
    return stage


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-039")
@pytest.mark.parametrize(
    "site", sorted(DECLARED_PATHS), ids=lambda site: f"{site[1]}#{site[2]}"
)
def test_the_disposition_at_a_non_manager_receiver(site: Site) -> None:
    """One test per declared tree: what a participant replica gets.

    The delivery is admitted when the type names the participant-replica
    path, and refused with the composed reason when it does not — never
    admitted-and-silently-inert, which is the disposition HP-01-005 forbids
    and ADR-0153 closes by construction.
    """
    declared = DECLARED_PATHS[site]
    stage = _stage_at(VENDOR_ID, declared)

    assert stage.resolved_path is ReceivedPath.PARTICIPANT_REPLICA
    if ReceivedPath.PARTICIPANT_REPLICA in declared:
        assert stage.status is Status.SUCCESS
        assert not stage.feedback_message
        return
    assert stage.status is Status.FAILURE
    assert stage.feedback_message == undeclared_path_reason(
        ReceivedPath.PARTICIPANT_REPLICA, declared, CASE_ID
    )
    assert f"not the CASE_MANAGER of case '{CASE_ID}'" in (
        stage.feedback_message
    )


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-039")
@pytest.mark.parametrize(
    "site",
    sorted(
        site
        for site, paths in DECLARED_PATHS.items()
        if ReceivedPath.CASE_MANAGER not in paths
    ),
    ids=lambda site: f"{site[1]}#{site[2]}",
)
def test_a_replica_only_declaration_refuses_the_case_manager(
    site: Site,
) -> None:
    """A type whose work is nobody's but a replica's refuses the manager.

    The refusal reason is true of the receiver: the case's own CASE_MANAGER
    is told that it is the CASE_MANAGER and that the type does not address
    that path, rather than being told it is not one (HP-01-039).
    """
    declared = DECLARED_PATHS[site]
    stage = _stage_at(MANAGER_ID, declared)

    assert stage.resolved_path is ReceivedPath.CASE_MANAGER
    assert stage.status is Status.FAILURE
    assert stage.feedback_message == (
        f"the CASE_MANAGER of case '{CASE_ID}',"
        " which this message type does not address"
    )
