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

"""What paths the migrated received trees declare, area by area.

The areas are the ones :data:`_ROOTS` names, and a wave adds its own as it
migrates it.  Every received tree in these areas declares the paths it handles
once, to the factory (HP-01-038), and a receiver on a path the declaration
omits is refused at the path stage with the composed reason (HP-01-039).  Two things
follow that a reader needs pinned, and this module pins both:

1. **The declaration itself**, in :data:`DECLARED_PATHS`, keyed on the tree
   factory that makes it rather than on the tree's name: several factories
   name their tree from a parameter, and a key on the name would lose its
   subject when a caller renames one (``notes/architecture-ratchet-corpus.md``
   § "Key a Ratchet on the Act, Not on the Name of What Performs It").  The
   set is held to equality in both directions, so a tree that stops
   declaring, starts declaring, or changes which paths it names fails here.
   A site that declares nothing is in one of two inventories, never both:
   :data:`KNOWN_UNDECLARED_PATH_SITES`, the ratchet of sites an Epic #5193
   wave still owes a declaration, whose terminal value is empty; and
   :data:`UNDECLARED_PATH_EXEMPTIONS`, the pinned set of call sites no
   delivery's path stage would answer for.
   :data:`CONDITIONAL_DECLARATION_EXEMPTIONS` is pinned the same way.
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
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

_FACTORY = "create_receive_activity_tree"

#: The migrated areas: the case, participant, report and status trees
#: (#5043), the embargo trees (#5042), the note and dead-letter trees
#: (#5785) and the sync trees (#5044).  One inventory for all of them, so
#: several waves cannot keep several tables of the same fact (CS-22-001).
_ROOTS = (
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "case",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "report",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "status",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "embargo",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "note",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "dead_letter",
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "sync",
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
_E = "vultron/core/behaviors/embargo"
_N = "vultron/core/behaviors/note"
_D = "vultron/core/behaviors/dead_letter"
_SY = "vultron/core/behaviors/sync"

#: Every declaration in these areas.  A conditional declaration records the
#: paths of its declaring branch; see :data:`CONDITIONAL_DECLARATION_EXEMPTIONS`.
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
        f"{_C}/suggest_actor_tree/owner_offer.py",
        "create_receive_offer_case_participant_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/suggest_actor_tree/owner_offer.py",
        "create_accept_actor_recommendation_received_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/suggest_actor_tree/owner_offer.py",
        "create_reject_actor_recommendation_received_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/suggest_actor_tree/answer.py",
        "create_recommendation_answer_received_tree",
        0,
    ): frozenset({PR}),
    # Offer(Actor)[target=VulnerabilityCase] reaches two stores: the
    # recommending participant addresses it to the case's CASE_MANAGER
    # (PCR-08-001), which admits, commits and forwards an
    # Offer(CaseParticipant) to the Case Owner, and the CASE_MANAGER's copy
    # reaches a participant replica, which takes it from the CASE_MANAGER
    # alone and acts on nothing (PCR-03-001, #4646).  The replica path is
    # not derivable from the one emit site, and dropping it broke
    # test_replica_sender_rule.py.
    (
        f"{_C}/suggest_actor_tree/recommend.py",
        "create_recommend_actor_to_case_received_tree",
        0,
    ): frozenset({CM, PR}),
    # --- case: ownership transfer ---------------------------------------
    (
        f"{_C}/ownership_transfer_tree/proposal.py",
        "create_propose_ownership_transfer_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_C}/ownership_transfer_tree/proposal.py",
        "create_offer_ownership_transfer_tree",
        0,
    ): frozenset({PR}),
    (
        f"{_C}/ownership_transfer_tree/replies.py",
        "create_accept_ownership_transfer_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/ownership_transfer_tree/replies.py",
        "create_reject_ownership_transfer_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_C}/ownership_transfer_tree/replies.py",
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
        f"{_C}/case_proposal_received_tree/factory.py",
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
        f"{_C}/receive_close_case_tree/factory.py",
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
        f"{_R}/received_report_trees/validate.py",
        "create_validate_report_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_R}/received_report_trees/verdicts.py",
        "create_invalidate_report_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_R}/received_report_trees/receipt.py",
        "create_report_received_tree",
        0,
    ): frozenset({NC}),
    (
        f"{_R}/received_report_trees/receipt.py",
        "create_ack_report_received_tree",
        0,
    ): frozenset({NC}),
    (
        f"{_R}/received_report_trees/verdicts.py",
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
    # --- embargo: the proposal, its answers and the teardown (#5042) -----
    # Each of these four is a directed type with one production emit site,
    # addressed to the CASE_MANAGER alone (PCR-08-001), and every step of
    # its tree is the CASE_MANAGER's: the narrowing is provable from the
    # emit site rather than from a roster.
    (
        f"{_E}/answer_trees.py",
        "accept_invite_to_embargo_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_E}/owner_decision_tree.py",
        "activate_embargo_on_case_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_E}/owner_decision_tree.py",
        "reject_embargo_proposal_on_case_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_E}/withdrawal_tree.py",
        "withdraw_from_embargo_on_case_tree",
        0,
    ): frozenset({CM}),
    # The same wire message means two things depending on who receives it
    # (ADR-0113): the CASE_MANAGER adjudicates and relays, the addressee's
    # replica answers.
    (
        f"{_E}/announce_teardown_tree/invite.py",
        "invite_to_embargo_on_case_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_E}/announce_teardown_tree/teardown.py",
        "remove_embargo_from_case_tree",
        0,
    ): frozenset({CM, PR}),
    # A Reject(Invite(EmbargoEvent)) is also what the CASE_MANAGER sends the
    # participant whose proposal or Accept it refuses (EMB-02-004,
    # EP-09-017).  That delivery records nothing, but it must pass the door
    # for the handler to close the participant's pending ask (EP-09-019), so
    # the guards that are the CASE_MANAGER's are declared on its path alone
    # rather than run at both.
    (
        f"{_E}/answer_trees.py",
        "reject_invite_to_embargo_tree",
        0,
    ): frozenset({CM, PR}),
    # The ending notice goes to every bound signatory, and an owner that is
    # its own case's CASE_MANAGER is one of them, so the manager path is
    # declared beside the replica path.  A replica-only declaration refused
    # that owner, which the demo suite caught and no unit test could
    # (CM-31-010).
    (
        f"{_E}/announce_received_tree.py",
        "announce_embargo_received_tree",
        0,
    ): frozenset({CM, PR}),
    # --- note (#5785) ----------------------------------------------------
    # Both are directed types: the trigger side resolves the CASE_MANAGER and
    # addresses the one activity to it (PCR-08-001), and no roster-derived
    # selection sends either.  Neither is narrowed below its sender rule —
    # each declares exactly the two non-empty sides of ``to_case_manager`` —
    # so neither declaration refuses a delivery the guard would admit.  The
    # replica path carries no effect: RSH-08-003 keeps every write at the
    # CASE_MANAGER, so a note reaches a replica as the entry's Announce
    # fan-out (SYNC-02-001, SYNC-02-003) and a direct Add(Note) there is
    # refused (HP-01-005).  It is declared because the act is the
    # CASE_MANAGER's to relay (PCR-03-001), the same reading the
    # Add(VulnerabilityReport) twin above takes from the same rule shape
    # (CM-30-003, CM-30-005).
    (
        f"{_N}/add_note_received_tree.py",
        "create_add_note_to_case_received_tree",
        0,
    ): frozenset({CM, PR}),
    (
        f"{_N}/remove_note_received_tree.py",
        "create_remove_note_from_case_received_tree",
        0,
    ): frozenset({CM, PR}),
    # --- sync: the ledger replication envelopes (#5044) ------------------
    # Announce(CaseLedgerEntry) is the one replication message every
    # receiver takes: the CASE_MANAGER gets its own announcement echoed
    # back, a replica applies the entry to its chain, and a receiver that
    # holds no replica yet is in the pre-genesis window, where the entry is
    # held until the genesis anchor arrives (SYNC-15-004).  Its sender guard
    # is a ledger-activity guard with no side split, so the no-case path
    # costs nothing there (HP-01-024).
    (
        f"{_SY}/announce_tree/factory.py",
        "create_announce_log_entry_tree",
        0,
    ): frozenset({CM, PR, NC}),
    # The remaining four are directed at the holder of the canonical ledger
    # and reach it alone: a Reject and a Read ask it for a redelivery or
    # state a position to it (SYNC-03-005, SYNC-17-003), and the two ledger
    # faults answer an Announce this store sent, as replication signalling
    # that is never ledgered and never relayed (SYNC-16-002).  Every effect
    # of all four is the CASE_MANAGER's, so no receiver off that path does
    # anything with them.
    (f"{_SY}/reject_tree.py", "create_reject_log_entry_tree", 0): frozenset(
        {CM}
    ),
    (f"{_SY}/read_tree.py", "create_read_log_entry_tree", 0): frozenset({CM}),
    (
        f"{_SY}/divergence_tree.py",
        "create_case_diverged_fault_tree",
        0,
    ): frozenset({CM}),
    (
        f"{_SY}/hash_mismatch_tree.py",
        "create_hash_mismatch_fault_tree",
        0,
    ): frozenset({CM}),
}

#: Sites whose declaration is conditional on the tree naming a case at build
#: time.  The path stage runs before ``case_resolution``, so the factory
#: refuses a declaration from a tree whose case only that stage resolves: it
#: would read the no-case path for every delivery (``received_path_stage``,
#: HP-01-025, ADR-0153).  Such a tree declares its paths when it names a case
#: and none when it does not, which is still one declaration per message
#: type (HP-01-038).
# permanent: HP-01-025 (the factory refuses a declaration the stage cannot
# answer; a tree in this set is not waiting for a migration)
CONDITIONAL_DECLARATION_EXEMPTIONS: frozenset[Site] = frozenset(
    {
        (
            f"{_R}/received_report_trees/verdicts.py",
            "create_invalidate_report_received_tree",
            0,
        ),
    }
)

#: Sites in these areas still waiting for a declaration, each owned by the
#: Epic #5193 wave that migrates its family.  Terminal value: empty.
# owner: #5046
KNOWN_UNDECLARED_PATH_SITES: dict[Site, str] = {
    # Offer(VulnerabilityReport) stores what it carried before it checks the
    # addressee, so its path declaration waits for that rework.
    (
        f"{_C}/receive_report_case_tree.py",
        "create_receive_report_case_tree",
        0,
    ): "#5046",
    (
        f"{_C}/receive_report_case_tree.py",
        "create_offer_received_without_report_tree",
        0,
    ): "#5046",
}

#: Sites that declare no paths by decision, each with the reason.  The
#: discriminator is not whether a delivery runs the tree — several of these run
#: on real deliveries — but whether any branch of it would use the answer a
#: path stage resolved.  None of these has one, so none is waiting for a
#: migration.
# permanent: HP-01-038 (no branch of these trees would use a resolved path)
UNDECLARED_PATH_EXEMPTIONS: dict[Site, str] = {
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
        f"{_C}/receive_close_case_tree/factory.py",
        "create_close_case_received_tree",
        0,
    ): "the Leave names no sender, so the tree archives and refuses it",
    # The close arm runs inside the enclosing tree's CASE_MANAGER gate, so
    # the delivery's own tree already asked the role question once; a second
    # stage here would ask it again (HP-01-037).
    (
        f"{_C}/receive_close_case_tree/factory.py",
        "create_close_case_received_tree",
        1,
    ): "a subtree of CloseCaseBT, inside its manager gate",
    # The malformed-Invite fault: the Create(ProcessingFault) is the
    # receiver's own answer wherever the Invite landed (MSM-05-001), and a
    # misrouted Invite may land on a store holding no replica of the case it
    # names.  Declaring the no-case path is not open either, because an
    # Invite(EmbargoEvent) is case-scoped and waits at the inbox's defer
    # check instead (HP-01-041).
    (
        f"{_E}/invite_received_tree.py",
        "embargo_invite_fault_tree",
        0,
    ): "the fault answers its sender on every path, scoped to none",
    # The dead-letter tree is not a message type's: it runs for any activity
    # whose object_ URI did not resolve, so no type's paths are its to
    # declare (HP-01-038).  What it does is the receiver's own diagnostic —
    # a DeadLetterRecord naming no case — with no branch of it keyed on the
    # path, so a stage would read a role (HP-01-037) in a case the activity
    # only happens to mention, and nothing would use the answer (HP-01-038).
    (
        f"{_D}/dead_letter_tree.py",
        "create_store_dead_letter_tree",
        0,
    ): "the receiver's own diagnostic record, scoped to no case",
}

#: Every site that declares no paths, for whichever reason.
UNDECLARED: dict[Site, str] = {
    **KNOWN_UNDECLARED_PATH_SITES,
    **UNDECLARED_PATH_EXEMPTIONS,
}


def _rel(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


class UnreadableDeclaration(AssertionError):
    """A ``paths=`` expression the scan cannot read statically.

    Raised rather than folded into "declares no paths": a tree that does
    declare, in a form this scan does not parse, would otherwise be reported
    as undeclared with a false reason, and the inventory would misstate the
    migration while still passing.  Spell the declaration as a set literal
    of ``ReceivedPath`` members, or teach :func:`_paths_of` the new form.
    """


def _paths_of(expr: ast.expr, where: str) -> frozenset[ReceivedPath]:
    """The declaration *expr* names, read statically.

    A conditional declaration is read from its declaring branch, which is
    the one the factory places a stage for.

    Raises:
        UnreadableDeclaration: *expr* is not a set literal of
            ``ReceivedPath`` members.
    """
    if isinstance(expr, ast.IfExp):
        return _paths_of(expr.body, where)
    if not isinstance(expr, ast.Set):
        raise UnreadableDeclaration(
            f"declaration is not statically readable at {where}:"
            f" {ast.unparse(expr)}"
        )
    found: set[ReceivedPath] = set()
    for element in expr.elts:
        member = (
            getattr(ReceivedPath, element.attr, None)
            if isinstance(element, ast.Attribute)
            else None
        )
        if member is None:
            raise UnreadableDeclaration(
                f"declaration names something other than a ReceivedPath"
                f" member at {where}: {ast.unparse(element)}"
            )
        found.add(member)
    return frozenset(found)


def _names_a_case_at_build_time(node: ast.Call) -> bool:
    """Whether the factory can hand the stage a case, read as HP-01-040 does.

    The same three places
    :func:`~vultron.core.behaviors.case.receive_stages.doors.path_stage_case_id`
    looks: the commit case, the case whose CASE_MANAGER gates the effects,
    and the case the sender context names.  Read off the call site rather
    than pinned, so a tree that starts or stops naming a case moves the
    disposition test with it.
    """
    for keyword in node.keywords:
        if keyword.arg in ("case_id", "manager_case_id") and not (
            isinstance(keyword.value, ast.Constant)
            and keyword.value.value is None
        ):
            return True
        if (
            keyword.arg == "sender_context"
            and isinstance(keyword.value, ast.Call)
            and any(k.arg == "case_id" for k in keyword.value.keywords)
        ):
            return True
    return False


@_corpus.gc_paused()
def _call_sites() -> tuple[
    dict[Site, frozenset[ReceivedPath] | None],
    frozenset[Site],
    frozenset[Site],
]:
    """Every factory call site in these areas, in three readings.

    Maps the site onto the paths it declares (``None`` for a site that
    declares none), the sites whose declaration is conditional, and the
    sites whose tree names a case the stage can read at build time.
    """
    declared: dict[Site, frozenset[ReceivedPath] | None] = {}
    conditional: set[Site] = set()
    with_a_case: set[Site] = set()
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
                if _names_a_case_at_build_time(node):
                    with_a_case.add(site)
                keyword = next(
                    (k for k in node.keywords if k.arg == "paths"), None
                )
                if keyword is None:
                    declared[site] = None
                    continue
                if isinstance(keyword.value, ast.IfExp):
                    conditional.add(site)
                declared[site] = _paths_of(
                    keyword.value, f"{module}:{name}#{index}"
                )
    return declared, frozenset(conditional), frozenset(with_a_case)


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
    sites, _, _ = _call_sites()
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
        " declare the tree's paths, add the site to"
        " KNOWN_UNDECLARED_PATH_SITES with the wave that owes it, or add it"
        " to UNDECLARED_PATH_EXEMPTIONS with the reason no delivery's path"
        " stage answers for it.",
        undeclared,
        frozenset(UNDECLARED),
    )
    assert not (
        frozenset(KNOWN_UNDECLARED_PATH_SITES)
        & frozenset(UNDECLARED_PATH_EXEMPTIONS)
    ), (
        "a site is both owed a declaration and exempt from one; it is one or"
        " the other (ARCH-18-007, ARCH-18-011)"
    )


@pytest.mark.spec("HP-01-038")
def test_the_declared_paths_are_pinned() -> None:
    """Which paths each tree declares, held to equality in both directions."""
    sites, _, _ = _call_sites()
    actual = {
        site: paths for site, paths in sites.items() if paths is not None
    }
    assert actual == DECLARED_PATHS, _diff(
        "A tree's path declaration changed (HP-01-038). Update the table"
        " with the reason the receiver on that path is, or is not, addressed.",
        frozenset(actual.items()),
        frozenset(DECLARED_PATHS.items()),
    )


@pytest.mark.spec("HP-01-038")
@pytest.mark.parametrize(
    ("expression", "because"),
    [
        ("DECLARED_ELSEWHERE", "a module constant the scan cannot resolve"),
        ("frozenset({ReceivedPath.NO_CASE})", "a call, not a set literal"),
        ("{ReceivedPath.NO_CASE, SOMETHING_ELSE}", "a non-member element"),
        ("{'manager'}", "a bare string rather than a member"),
    ],
    ids=["constant", "frozenset-call", "non-member", "string"],
)
def test_an_unreadable_declaration_raises_rather_than_reading_as_none(
    expression: str, because: str
) -> None:
    """A declaration the scan cannot parse is loud, never "declares none".

    Folding it into the undeclared inventory would report a tree that *does*
    declare as undeclared, with a false reason, and the whole inventory would
    misstate the migration while still passing.
    """
    expr = ast.parse(expression, mode="eval").body

    with pytest.raises(UnreadableDeclaration):
        _paths_of(expr, f"test ({because})")


@pytest.mark.spec("HP-01-038")
def test_a_readable_declaration_is_read_rather_than_raising() -> None:
    """The guard above is not vacuous: the supported form still parses."""
    expr = ast.parse(
        "{ReceivedPath.NO_CASE, ReceivedPath.CASE_MANAGER}", mode="eval"
    ).body

    assert _paths_of(expr, "test") == frozenset({NC, CM})


@pytest.mark.spec("HP-01-025")
@pytest.mark.spec("HP-01-038")
def test_a_conditional_declaration_is_listed_with_its_reason() -> None:
    """Only the listed sites make their declaration conditional.

    A declaration conditional on anything but the tree naming a case at
    build time is a message type deciding its paths per delivery, which
    HP-01-038's "once" forbids.  The one admitted condition is the factory's
    own wiring rule: a tree whose case only ``case_resolution`` resolves is
    refused a declaration, because the stage runs first and would read the
    no-case path for every delivery (``received_path_stage``, HP-01-025).
    """
    _, conditional, _ = _call_sites()
    assert conditional == CONDITIONAL_DECLARATION_EXEMPTIONS, _diff(
        "The set of conditional path declarations changed (HP-01-038).",
        conditional,
        CONDITIONAL_DECLARATION_EXEMPTIONS,
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


def _stage_at(
    actor_id: str,
    declared: frozenset[ReceivedPath],
    case_id: str | None = CASE_ID,
):
    """The path stage of a tree declaring *declared*, run in *actor_id*'s store.

    *case_id* is what the factory hands the stage: the tree's case, or
    ``None`` for a tree that names none at build time, which makes the stage
    resolve one at run time and read an unresolvable case as the no-case
    path (HP-01-040).
    """
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
    stage = ReceivedPathNode(declared=declared, label="DeclaredPathsBT")
    scenario.run(with_case_id(stage, case_id), actor_id=actor_id)
    return stage


def _non_manager_sites() -> list[tuple[Site, bool]]:
    """Every declared site, paired with whether its tree names a case.

    The pairing decides which non-manager receivers the tree can be reached
    by, which :func:`_non_manager_probes` turns into the dispositions pinned
    for it.  Derived from the call site, so a tree that starts or stops
    naming a case changes what is pinned.
    """
    _, _, with_a_case = _call_sites()
    return sorted((site, site in with_a_case) for site in DECLARED_PATHS)


def _non_manager_probes(
    names_a_case: bool,
) -> list[tuple[ReceivedPath, str | None]]:
    """The non-manager paths a tree can reach, as (path, the stage's case).

    A tree that names its case at build time hands the stage that case, so
    its non-manager receiver is a participant replica.

    A tree that names none is **not** thereby a tree whose receiver holds no
    case: ``ReceivedPathNode.update`` falls back to the execution's
    ``/case_id`` and then to the activity, so it resolves a case at run time
    and a receiver holding a replica of that case is on the replica path
    (HP-01-040).  Both dispositions are reachable, so both are pinned —
    previously the replica one went unprobed for these trees, leaving the
    refusal their declaration implies unasserted.
    """
    replica = (ReceivedPath.PARTICIPANT_REPLICA, CASE_ID)
    if names_a_case:
        return [replica]
    return [(ReceivedPath.NO_CASE, None), replica]


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-01-039")
@pytest.mark.spec("HP-01-040")
@pytest.mark.parametrize(
    ("site", "names_a_case"),
    _non_manager_sites(),
    ids=lambda value: (
        f"{value[1]}#{value[2]}" if isinstance(value, tuple) else str(value)
    ),
)
def test_the_disposition_at_a_non_manager_receiver(
    site: Site, names_a_case: bool
) -> None:
    """One test per declared tree: what a receiver that is not the manager gets.

    The delivery is admitted when the type names that receiver's path, and
    refused with the composed reason when it does not — never
    admitted-and-silently-inert, which is the disposition HP-01-005 forbids
    and ADR-0153 closes by construction.

    Which non-manager receivers the tree can be reached by follows from the
    case it names, and :func:`_non_manager_probes` says which dispositions
    that makes reachable.  A tree naming no case reaches both the no-case and
    the replica path, because the stage resolves a case at run time when the
    factory named none (HP-01-040), so both are pinned here.

    **What this test cannot tell you.** It reads the declaration out of the
    call site and asserts the stage's verdict *for that declaration*, so it
    agrees with whatever the tree declares.  A declaration that narrows away
    a path a real receiver is on still passes here — the refusal just becomes
    the pinned expectation.  A narrowing is a claim about who receives a
    message type, and only a delivery to a real roster can falsify it: run
    the ``test/demo/`` scenarios for the type, with ``-m ""``, and above all
    one where a single actor holds two roles, which is where a replica-only
    declaration meets a receiver that is also the CASE_MANAGER.
    """
    declared = DECLARED_PATHS[site]
    for expected, case_id in _non_manager_probes(names_a_case):
        # One store per probe: an actor id *is* a store name (DL-07-004), so
        # two probes sharing one would re-seed the same case.
        receiver = f"{VENDOR_ID}-{expected.name.lower()}"
        stage = _stage_at(receiver, declared, case_id)

        assert stage.resolved_path is expected
        if expected in declared:
            assert stage.status is Status.SUCCESS
            assert not stage.feedback_message
            continue
        assert stage.status is Status.FAILURE
        assert stage.feedback_message == undeclared_path_reason(
            expected, declared, case_id
        )
        if expected is ReceivedPath.PARTICIPANT_REPLICA:
            assert f"not the CASE_MANAGER of case '{CASE_ID}'" in (
                stage.feedback_message
            )
        else:
            assert "holds no replica of" in stage.feedback_message


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
    stage = _stage_at(MANAGER_ID, declared, CASE_ID)

    assert stage.resolved_path is ReceivedPath.CASE_MANAGER
    assert stage.status is Status.FAILURE
    assert stage.feedback_message == (
        f"the CASE_MANAGER of case '{CASE_ID}',"
        " which this message type does not address"
    )
