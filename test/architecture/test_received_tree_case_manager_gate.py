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

"""A received tree gets its CASE_MANAGER gate from the factory (BT-17-008).

``create_receive_activity_tree`` wraps ``manager_effects`` in the gate and
refuses an emit-capable node in ``replica_effects`` that no named exemption
covers.  These checks keep that the only way in:

1. **Ratchet** ``KNOWN_DIRECT_GATE_CALLERS``: no received-tree module (one
   that calls ``create_receive_activity_tree``) calls
   ``create_case_manager_gated_tree`` itself.  Terminal value: empty,
   reached by #4300, #4301 and #4302; kept so a new caller fails.
2. **Check** ``test_no_received_tree_passes_legacy_effect_nodes``: no
   received tree passes the legacy ``effect_nodes``.  #4307 moved every
   tree off it — the close-case tree's decline emit, its last caller, onto
   ``manager_effects`` (#3825) — and retired the parameter from
   ``create_receive_activity_tree``, so the former ratchet set is gone and
   this is now a plain "no caller passes ``effect_nodes``" assertion.
3. **Pinned exemption set** ``GATE_CALLERS_OUTSIDE_RECEIVED_TREES``: the
   modules that call the gate and build no received tree (trigger, expiry,
   relay-guard, admission-backfill and retry trees), so a new caller must
   be classified.
4. **Pinned exemption set** ``REPLICA_EMIT_EXEMPTION_USES``: which tree uses
   each registered ``ReplicaEmitExemption``, equal to the registry.
5. Every class that reaches the outbox seam carries the ``EmitCapable``
   marker, so the factory's refusal sees it.
6. **Pinned exemption set** ``LEDGER_REPLICATION_SENDERS``: the classes that
   send only through the ledger-replication seams, gated by ledger authority
   rather than the marker (ADR-0073), so a new one must be classified.
7. Only ``create_case_manager_gated_tree`` constructs a ``CaseManagerGate``,
   so a hand-built gate without the role check cannot hide an emit from the
   factory's walk.

Every set is held to equality in both directions (ARCH-18-001, ARCH-18-002):
a new entry fails, and so does a stale one.  Entries are
``(module, top-level function)`` so each carries its own owner.
"""

import ast
import importlib
import inspect
from collections.abc import Iterator
from pathlib import Path

import pytest

from test.architecture import _corpus
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.replica_emit_exemptions import (
    REPLICA_EMIT_EXEMPTIONS,
    ReplicaEmitExemption,
)

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"
_BEHAVIORS_ROOT = _VULTRON_ROOT / "core" / "behaviors"
_FACTORY_MODULE = "vultron/core/behaviors/case/receive_activity_tree.py"
_RECEIVE = "create_receive_activity_tree"
_GATE = "create_case_manager_gated_tree"
_LEGACY_KEYWORD = "effect_nodes"
_EXEMPTION_KEYWORD = "replica_emit_exemption"

#: Callables that put an activity id in an actor's outbox.  A class whose
#: methods call one of them is an emitter.
_OUTBOX_SEAMS = frozenset(
    {
        "outbox_append",
        "add_activity_to_outbox",
        "broadcast_case_update",
    }
)

#: Ledger-replication seams: ``SyncActivityPort`` sends and the helpers that
#: wrap them, plus the commit tree whose fan-out announces a minted entry.
#: Gated by ledger authority (``DeclineForeignLedgerCommitNode``, ADR-0073),
#: not by ``EmitCapable``; see ``vultron/core/behaviors/emit_capable.py``.
_LEDGER_REPLICATION_SEAMS = frozenset(
    {
        "send_announce_log_entry",
        "send_reject_log_entry",
        "send_ledger_suffix",
        "backfill_admitted_peers",
        "create_commit_log_entry_tree",
    }
)

_Site = tuple[str, str]

_C = "vultron/core/behaviors/case"
_E = "vultron/core/behaviors/embargo"
_N = "vultron/core/behaviors/note"
_R = "vultron/core/behaviors/report"
_S = "vultron/core/behaviors/status"

# ---------------------------------------------------------------------------
# 1. Received-tree functions that still call create_case_manager_gated_tree.
#    Terminal value reached: #4300, #4301 and #4302 moved every received tree
#    onto manager_effects.  The empty set stays so a new direct caller fails.
# ---------------------------------------------------------------------------
# owner: none (terminal value)
KNOWN_DIRECT_GATE_CALLERS: frozenset[_Site] = frozenset()

# ---------------------------------------------------------------------------
# 3. Modules that call the gate but build no received tree.  BT-17-008 binds
#    received trees only: a trigger, expiry or retry tree runs on the actor's
#    own initiative.  The four ``case_manager_admits_*_guard`` composites
#    are gate-wrapped read-only conditions passed as a received tree's
#    ``precondition_guards`` (the embargo Invite tree, the participant
#    removal and reinstatement trees, the two suggest-actor trees): they
#    hold no effect and no emit, which is all BT-17-008 governs (#4301
#    keeps their direct gate).  The admission backfill is a CM-10-006
#    follow-on that the embargo Accept use case runs on its own, given no
#    activity; the Add and Remove(EmbargoEvent) trees run the same nodes
#    (embargo_admission_backfill_nodes) in their manager_effects (#4323).
# ---------------------------------------------------------------------------
# permanent: BT-17-008 (binds received-side trees only; #4301 keeps these)
GATE_CALLERS_OUTSIDE_RECEIVED_TREES: frozenset[_Site] = frozenset(
    {
        (
            "vultron/adapters/driving/fastapi/pending_retry.py",
            "_relay_pending_revision",
        ),
        (
            f"{_E}/admission_backfill_tree.py",
            "embargo_admission_backfill_tree",
        ),
        (f"{_E}/expiry_tree.py", "create_honour_late_accept_tree"),
        (f"{_E}/expiry_tree.py", "create_invite_expiry_tree"),
        (f"{_E}/expiry_tree.py", "create_noop_ledger_entry_tree"),
        (f"{_E}/expiry_tree.py", "create_reinvite_stale_accepter_tree"),
        (f"{_E}/nodes/relay.py", "case_manager_admits_proposal_guard"),
        (
            f"{_C}/nodes/case_participant_received.py",
            "case_manager_admits_removal_guard",
        ),
        (
            f"{_C}/nodes/participant_reinstatement.py",
            "case_manager_admits_reinstatement_guard",
        ),
        (
            f"{_C}/nodes/suggest_actor/conditions.py",
            "case_manager_admits_accepted_invitee_guard",
        ),
        (
            f"{_C}/nodes/suggest_actor/conditions.py",
            "case_manager_admits_suggested_actor_guard",
        ),
        (f"{_E}/trigger_tree.py", "_by_role"),
    }
)

# ---------------------------------------------------------------------------
# 6. Classes that send only through the ledger-replication seams and so carry
#    no EmitCapable marker: each mints-and-fans-out or answers the ledger
#    holder, gated by ledger authority (ADR-0073, SYNC-03-001).
#    Entries are (dotted module, class).
# ---------------------------------------------------------------------------
# permanent: ADR-0073 (ledger replication is gated by ledger authority)
LEDGER_REPLICATION_SENDERS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "vultron.core.behaviors.case.nodes.invite_ledger_backfill",
            "BackfillCanonicalLedgerToInviteeNode",
        ),
        (
            "vultron.core.behaviors.case.nodes.leave.record",
            "CommitCaseActorRMClosedEntryNode",
        ),
        (
            "vultron.core.behaviors.case.nodes.lifecycle",
            "CommitCaseLedgerEntryNode",
        ),
        (
            "vultron.core.behaviors.case.nodes.proposal_ledger",
            "CommitNativeLedgerEntriesNode",
        ),
        (
            "vultron.core.behaviors.case_status_snapshot",
            "EmitCaseStatusUpdateNode",
        ),
        (
            "vultron.core.behaviors.sync.nodes.embargo_backfill",
            "BackfillAdmittedParticipantsNode",
        ),
        (
            "vultron.core.behaviors.sync.nodes.fanout",
            "SendLogEntryToEachNode",
        ),
        (
            "vultron.core.behaviors.sync.nodes.receive",
            "SendRejectLogEntryNode",
        ),
        (
            "vultron.core.behaviors.sync.nodes.replay",
            "SendMissingEntriesNode",
        ),
    }
)

# ---------------------------------------------------------------------------
# 4. Which received tree uses each named exemption (constant name → site).
#    Each entry is the decision recorded in replica_emit_exemptions.py.
# ---------------------------------------------------------------------------
# permanent: BT-17-008 (one recorded decision per entry; the reasons are in
# replica_emit_exemptions.py)
REPLICA_EMIT_EXEMPTION_USES: frozenset[tuple[str, str, str]] = frozenset(
    {
        (
            "ACK_ECHO",
            f"{_R}/received_report_trees.py",
            "create_ack_report_received_tree",
        ),
        (
            "CASE_PROPOSAL",
            f"{_C}/case_proposal_received_tree.py",
            "create_case_proposal_received_tree",
        ),
        (
            "CASE_STATUS",
            f"{_S}/add_case_status_tree.py",
            "add_case_status_tree",
        ),
        # The RM-declaration gap-note exemptions (engage, defer, the three
        # report verdicts) and RSH_STATUS were retired by #3814: once each
        # tree's state write moved under the CASE_MANAGER gate (RSH-08-003),
        # its whole ordered effect pipeline — gap note and, for
        # add_participant_status, the adoption emit and threat teardown —
        # moved with it, so those trees emit nothing outside the gate.
        # add_case_status keeps CASE_STATUS: it gates only the append, leaving
        # the CSB-18 diagnostic and the threat-ask ungated.
        (
            "EMBARGO_INVITE_ANSWER",
            f"{_E}/announce_teardown_tree.py",
            "invite_to_embargo_on_case_tree",
        ),
        (
            "EMBARGO_INVITE_REFUSAL",
            f"{_E}/refusal_tree.py",
            "embargo_invite_refusal_tree",
        ),
        (
            "OFFER_ROLE",
            f"{_C}/offer_case_participant_role_received_tree.py",
            "create_offer_case_participant_role_received_tree",
        ),
        (
            "REPORT_CASE_PROPOSAL",
            f"{_C}/receive_report_case_tree.py",
            "create_receive_report_case_tree",
        ),
    }
)


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _calls(node: ast.AST) -> Iterator[tuple[ast.Call, str]]:
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and (name := _call_name(sub.func)) is not None
        ):
            yield sub, name


def _top_level_scopes(
    tree: ast.AST,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    assert isinstance(tree, ast.Module)
    for node in tree.body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            yield node


def _rel(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


def _gate_callers() -> tuple[frozenset[_Site], frozenset[_Site]]:
    """(received-tree sites, other sites) that call the gate directly."""
    received: set[_Site] = set()
    other: set[_Site] = set()
    for path, tree in _corpus.files_mentioning(_GATE, under=_VULTRON_ROOT):
        rel = _rel(path)
        if rel == _FACTORY_MODULE:
            continue
        is_received = any(name == _RECEIVE for _, name in _calls(tree))
        for scope in _top_level_scopes(tree):
            if any(name == _GATE for _, name in _calls(scope)):
                (received if is_received else other).add((rel, scope.name))
    return frozenset(received), frozenset(other)


def _receive_calls() -> Iterator[tuple[str, str, ast.Call]]:
    for path, tree in _corpus.files_mentioning(
        _RECEIVE, under=_BEHAVIORS_ROOT
    ):
        rel = _rel(path)
        if rel == _FACTORY_MODULE:
            continue
        for scope in _top_level_scopes(tree):
            for call, name in _calls(scope):
                if name == _RECEIVE:
                    yield rel, scope.name, call


def _legacy_effect_nodes_sites() -> frozenset[_Site]:
    """Sites passing the retired ``effect_nodes`` keyword (#4307).

    ``effect_nodes`` was removed from ``create_receive_activity_tree``, so a
    caller passing it is a static guard against the keyword's reintroduction.
    Position is no longer matched: the fourth positional is now
    ``case_may_be_absent``.
    """
    return frozenset(
        (rel, scope)
        for rel, scope, call in _receive_calls()
        if any(kw.arg == _LEGACY_KEYWORD for kw in call.keywords)
    )


def _exemption_uses() -> frozenset[tuple[str, str, str]]:
    uses: set[tuple[str, str, str]] = set()
    for rel, scope, call in _receive_calls():
        for kw in call.keywords:
            if kw.arg == _EXEMPTION_KEYWORD:
                assert isinstance(kw.value, ast.Name), (
                    f"{rel}:{scope}: pass a named exemption constant from"
                    " replica_emit_exemptions, not an inline value"
                )
                uses.add((kw.value.id, rel, scope))
    return frozenset(uses)


def _pinned_diff(
    label: str, actual: frozenset, known: frozenset, fix: str
) -> str:
    """Empty when *actual* equals *known*; else the lines naming the drift."""
    lines: list[str] = []
    if new := actual - known:
        lines.append(f"NEW {label} — {fix}:")
        lines.extend(f"  + {entry}" for entry in sorted(new))
    if stale := known - actual:
        lines.append(
            f"STALE {label} — remove from the pinned set in the same"
            " commit (ARCH-18-002):"
        )
        lines.extend(f"  - {entry}" for entry in sorted(stale))
    return "\n".join(lines)


def _assert_pinned(
    label: str, actual: frozenset, known: frozenset, fix: str
) -> None:
    diff = _pinned_diff(label, actual, known, fix)
    assert actual == known, "\n" + diff


@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("ARCH-18-001")
def test_no_received_tree_calls_the_case_manager_gate_itself() -> None:
    received, _ = _gate_callers()
    _assert_pinned(
        "direct create_case_manager_gated_tree call in a received tree",
        received,
        KNOWN_DIRECT_GATE_CALLERS,
        "pass the gated work as manager_effects instead (BT-17-008)",
    )


@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("ARCH-18-005")
def test_gate_callers_outside_received_trees_are_pinned() -> None:
    _, other = _gate_callers()
    _assert_pinned(
        "create_case_manager_gated_tree caller outside a received tree",
        other,
        GATE_CALLERS_OUTSIDE_RECEIVED_TREES,
        "a received-tree helper takes manager_effects instead; a trigger"
        " or expiry tree is classified here with its reason",
    )


@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("ARCH-18-001")
def test_no_received_tree_passes_legacy_effect_nodes() -> None:
    """No received tree passes the retired ``effect_nodes`` keyword (#4307).

    ``effect_nodes`` was removed from ``create_receive_activity_tree`` once the
    close-case tree moved its decline emit onto ``manager_effects`` (#3825), so
    passing it now raises ``TypeError`` at runtime; this is the static guard.
    """
    offenders = sorted(_legacy_effect_nodes_sites())
    assert offenders == [], (
        "effect_nodes was retired in #4307; pass replica_effects and"
        f" manager_effects instead (BT-17-008): {offenders}"
    )


@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("ARCH-18-005")
def test_replica_emit_exemption_uses_are_pinned() -> None:
    _assert_pinned(
        "replica emit exemption use",
        _exemption_uses(),
        REPLICA_EMIT_EXEMPTION_USES,
        "record the decision here and in replica_emit_exemptions.py",
    )


@pytest.mark.spec("BT-17-008")
def test_every_registered_exemption_has_exactly_one_tree() -> None:
    import vultron.core.behaviors.replica_emit_exemptions as registry

    by_constant = {
        name: value
        for name, value in vars(registry).items()
        if isinstance(value, ReplicaEmitExemption)
    }
    assert sorted(e.name for e in by_constant.values()) == sorted(
        REPLICA_EMIT_EXEMPTIONS
    ), "every exemption constant is registered, and only those"
    used = [constant for constant, _, _ in REPLICA_EMIT_EXEMPTION_USES]

    assert sorted(used) == sorted(by_constant), (
        "each registered ReplicaEmitExemption is used by exactly one"
        f" received tree: registered {sorted(by_constant)}, used {used}"
    )


def _emitter_classes(
    seams: frozenset[str] = _OUTBOX_SEAMS,
) -> frozenset[tuple[str, str]]:
    """(module, class) for every behaviors class whose methods call a seam."""
    found: set[tuple[str, str]] = set()
    for path, tree in _corpus.files_mentioning(*seams, under=_BEHAVIORS_ROOT):
        module = _rel(path).removesuffix(".py").replace("/", ".")
        for scope in _top_level_scopes(tree):
            if not isinstance(scope, ast.ClassDef):
                continue
            if any(name in seams for _, name in _calls(scope)):
                found.add((module, scope.name))
    return frozenset(found)


def _is_marked(module: str, name: str) -> bool:
    cls = getattr(importlib.import_module(module), name)
    return inspect.isclass(cls) and issubclass(cls, EmitCapable)


@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("ARCH-18-001")
def test_ledger_replication_senders_are_pinned() -> None:
    unmarked = frozenset(
        site
        for site in _emitter_classes(_LEDGER_REPLICATION_SEAMS)
        if not _is_marked(*site)
    )
    _assert_pinned(
        "unmarked ledger-replication sender",
        unmarked,
        LEDGER_REPLICATION_SENDERS,
        "if it sends only a ledger entry gated by ledger authority, add it"
        " to LEDGER_REPLICATION_SENDERS with that reason; otherwise mix in"
        " EmitCapable",
    )


@pytest.mark.spec("BT-17-008")
def test_only_the_gate_helper_constructs_a_case_manager_gate() -> None:
    builders = sorted(
        _rel(path)
        for path, tree in _corpus.files_mentioning(
            "CaseManagerGate", under=_VULTRON_ROOT
        )
        if any(name == "CaseManagerGate" for _, name in _calls(tree))
    )
    assert builders == ["vultron/core/behaviors/case/nodes/role_gates.py"], (
        "a CaseManagerGate built outside create_case_manager_gated_tree may"
        " lack the CheckIsCaseManagerNode skip arm, yet the factory's walk"
        f" treats it as gated (BT-17-008): {builders}"
    )


@pytest.mark.spec("BT-17-008")
def test_every_outbox_writer_carries_the_emit_marker() -> None:
    classes = _emitter_classes()
    assert classes, "no outbox-writing class found — seam names drifted?"

    unmarked = sorted(
        f"{module}.{name}"
        for module, name in classes
        if not _is_marked(module, name)
    )
    assert unmarked == [], (
        "these classes enqueue an outbound activity but do not mix in"
        f" EmitCapable, so create_receive_activity_tree cannot refuse them"
        f" ungated (BT-17-008): {unmarked}"
    )


def test_the_marked_families_cover_the_named_emitters() -> None:
    from vultron.core.behaviors.case.nodes.update import (
        BroadcastCaseUpdateNode,
    )
    from vultron.core.behaviors.embargo.nodes.emit import (
        _SendEmbargoActivityBase,
    )
    from vultron.core.behaviors.embargo.nodes.relay import (
        RelayEmbargoInviteToEachNode,
    )
    from vultron.core.behaviors.helpers import (
        UpdateActorOutbox,
        _EmitSingleActivityBase,
    )
    from vultron.core.behaviors.sender.nodes.actions import QueueToOutboxNode

    for cls in (
        _EmitSingleActivityBase,
        _SendEmbargoActivityBase,
        RelayEmbargoInviteToEachNode,
        BroadcastCaseUpdateNode,
        QueueToOutboxNode,
        UpdateActorOutbox,
    ):
        assert inspect.isclass(cls) and issubclass(cls, EmitCapable), cls


class TestPinnedDiff:
    """The comparison every pinned set above uses fails in both directions."""

    _KNOWN = frozenset({("a.py", "f"), ("b.py", "g")})

    def test_equal_sets_pass(self) -> None:
        _assert_pinned("site", self._KNOWN, self._KNOWN, "fix")

    def test_a_new_entry_fails(self) -> None:
        with pytest.raises(AssertionError, match=r"NEW site"):
            _assert_pinned(
                "site", self._KNOWN | {("c.py", "h")}, self._KNOWN, "fix"
            )

    def test_a_stale_entry_fails(self) -> None:
        with pytest.raises(AssertionError, match=r"STALE site"):
            _assert_pinned(
                "site", frozenset({("a.py", "f")}), self._KNOWN, "fix"
            )
