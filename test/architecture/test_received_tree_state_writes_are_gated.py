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

"""Received-side state writes run only at the CASE_MANAGER (RSH-08-003).

The state-write analogue of ``test_received_tree_case_manager_gate.py``'s emit
checks.  A received-side tree that writes participant or case state must do
it inside a CASE_MANAGER gate; every other replica takes that state from the
ledger (PCR-03-001).  Gating before the replay slot exists blinds replicas
(RSH-08-004), so the trees that still write ungated are held here and leave
as the #3814 gating work lands.

The checks:

1. Every received-side tree — each function under ``vultron/core/behaviors/``
   that calls ``create_receive_activity_tree``, the sites
   ``test_received_tree_case_manager_gate`` enumerates — is *built*
   (``_received_tree_builds``) and walked with the factory's own
   ``ungated_nodes``: a
   :class:`~vultron.core.behaviors.state_write_capable.StateWriteCapable`
   node outside every ``CaseManagerGate`` is an ungated write.  The walk
   sees nodes a factory reaches through helpers, locals and nested factories,
   and descends into the participant-replica gate, which runs everywhere but
   the CASE_MANAGER.
2. **Pinned exemption set** :data:`REPLICA_STATE_WRITES` — trees whose
   ungated writes are the design: the ledger replay itself, the bootstrap
   trees that mint a case or seed a replica before any CASE_MANAGER gate could
   pass, the Engage carried-snapshot seed, and the paused-signatory embargo
   teardown the CASE_MANAGER's direct notice carries (CM-31-010).  Every other
   received-side state write is now CASE_MANAGER-gated (#3814): the
   ``KNOWN_UNGATED_STATE_WRITES`` ratchet drove to empty and was deleted with
   its strict-``xfail`` goal test, per #3815's design.
3. Every behaviors class that reaches a state-write seam carries the marker,
   or is in the **pinned exemption set** :data:`WRITES_NO_CASE_STATE` with
   its reason — so the marker, not a name list, decides what the walk finds.

Every set is held to equality in both directions (TB-10-002, ARCH-18-001):
a new ungated write fails, and so does a row the code no longer needs.
Entries are ``(module, factory, node class)`` so a second ungated writer in
an already-listed tree fails too.
"""

import ast
import functools
import importlib
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest
from py_trees.behaviour import Behaviour
from py_trees.composites import Composite
from py_trees.decorators import Decorator

from test.architecture import _corpus
from test.architecture._received_tree_builds import built_received_trees
from test.architecture.test_received_tree_case_manager_gate import (
    _assert_pinned,
    _calls,
    _rel,
    _top_level_scopes,
)
from vultron.core.behaviors.case.receive_activity_tree import ungated_nodes
from vultron.core.behaviors.state_write_capable import StateWriteCapable

_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"
_BEHAVIORS_ROOT = _CORE_ROOT / "behaviors"

_Write = tuple[str, str, str]

_C = "vultron/core/behaviors/case"
_E = "vultron/core/behaviors/embargo"
_N = "vultron/core/behaviors/note"
_R = "vultron/core/behaviors/report"
_S = "vultron/core/behaviors/status"
_Y = "vultron/core/behaviors/sync"

#: DataLayer write methods, matched as an attribute call on any receiver.
_DATALAYER_WRITES = frozenset(
    {"save", "create", "save_many", "save_if_unchanged", "delete"}
)
#: State writes the text fixed point cannot reach, because it follows only
#: top-level functions: the consent-row model methods (CM-18-005) and the
#: EM-state service (EMB-18-001).  A helper *function* that writes is
#: derived (:func:`_state_write_helpers`), never listed here.
_STATE_WRITE_METHODS = frozenset(
    {
        "EmbargoLifecycle",
        "apply_pec_transition",
        "apply_pec_transition_if_legal",
    }
)

# ---------------------------------------------------------------------------
# 2. Received trees whose ungated writes are the design, with the reason.
#    A replica must write the state the ledger carries, and a tree that mints
#    a case or seeds a replica runs before a CASE_MANAGER exists to gate on.
# ---------------------------------------------------------------------------
_REPLAY = (
    "the ledger replay is how a replica takes case state from the"
    " CASE_MANAGER (PCR-03-001, RSH-08-003, SYNC-02-002)"
)
_SEED = (
    "seeds a replica from the CASE_MANAGER's own case snapshot before the"
    " replica holds the case, so no role gate can pass yet (CM-14-011,"
    " SYNC-15-002)"
)
_MINT = (
    "the receiver mints the case and becomes its first manager, so no"
    " CASE_MANAGER exists to gate on yet (CP-04, CM-02-008)"
)
_ENDING_NOTICE = (
    "a signatory the ledger no longer reaches applies the CASE_MANAGER's"
    " direct embargo-ending notice, its only channel; the sender guard admits"
    " only the CASE_MANAGER (CM-31-010, PCR-03-001)"
)
_CARRIED_SNAPSHOT = (
    "stores the embargo and inline participants an Engage carried, before the"
    " sender guard can find a sender whose participant is only in that"
    " snapshot; idempotent and non-regressing, the same neutral seeding the"
    " announce-case path uses, not a replica adopting adjudicated state from a"
    " peer (CBT-05-005, EMB-18-003, BT-22-005)"
)
# permanent: RSH-08-003 (replay and bootstrap writes; see each reason)
REPLICA_STATE_WRITES: dict[_Write, str] = {
    (
        f"{_E}/announce_received_tree.py",
        "announce_embargo_received_tree",
        "ApplyAnnouncedEmbargoRevisionNode",
    ): _ENDING_NOTICE,
    # The participant-replica arm's teardown now runs only for a paused
    # signatory, gated by AwaitsEmbargoEndingNoticeNode (#3814): the direct
    # Remove(EmbargoEvent) is that signatory's only channel (CM-31-010).
    (
        f"{_E}/announce_teardown_tree.py",
        "remove_embargo_from_case_tree",
        "ClearActiveEmbargoNode",
    ): _ENDING_NOTICE,
    **{
        (
            f"{_R}/prioritize_tree.py",
            "create_engage_case_tree",
            cls,
        ): _CARRIED_SNAPSHOT
        for cls in (
            "HoldCarriedEmbargoNode",
            "StoreEmbeddedParticipantsNode",
        )
    },
    **{
        (f"{_Y}/announce_tree.py", "create_announce_log_entry_tree", cls): (
            _REPLAY
        )
        for cls in (
            "ApplyCaseStatusFromLedgerNode",
            "ApplyCloseCaseFromLedgerNode",
            "ApplyEmbargoAbandonmentFromLedgerNode",
            "ApplyEmbargoAcceptanceFromLedgerNode",
            "ApplyEmbargoActivationFromLedgerNode",
            "ApplyEmbargoInviteFromLedgerNode",
            "ApplyEmbargoProposalFromLedgerNode",
            "ApplyEmbargoProposalRejectionFromLedgerNode",
            "ApplyEmbargoReinviteFromLedgerNode",
            "ApplyEmbargoRejectionFromLedgerNode",
            "ApplyEmbargoTeardownNode",
            "ApplyHonourLateAcceptFromLedgerNode",
            "ApplyCreateCaseParticipantFromLedgerNode",
            "ApplyUpdateCaseParticipantFromLedgerNode",
            "ApplyInviteExpiryFromLedgerNode",
            "ApplyInviteExpiryNoopFromLedgerNode",
            "ApplyNoteFromLedgerNode",
            "ApplyOfferOwnershipTransferFromLedgerNode",
            "ApplyOfferReportFromLedgerNode",
            "ApplyOwnershipTransferFromLedgerNode",
            "ApplyParticipantStatusFromLedgerNode",
            "ApplyReinstateCaseParticipantFromLedgerNode",
            "ApplyRemoveCaseParticipantFromLedgerNode",
            "ApplyRemoveNoteFromLedgerNode",
            "ApplyRmVerdictFromLedgerNode",
        )
    },
    (
        f"{_C}/announce_case_received_tree.py",
        "create_announce_vulnerability_case_received_tree",
        "SeedAnnouncedCaseNode",
    ): _SEED,
    **{
        (
            f"{_C}/create_case_received_tree.py",
            "create_create_case_received_tree",
            cls,
        ): _SEED
        for cls in (
            "HoldCarriedEmbargoNode",
            "SeedCaseReplicaNode",
            "StoreEmbeddedParticipantsNode",
        )
    },
    **{
        (
            f"{_C}/case_proposal_received_tree.py",
            "create_case_proposal_received_tree",
            cls,
        ): _MINT
        for cls in (
            "AddCaseActorParticipantNode",
            "AddOwnerParticipantNode",
            "AddReporterParticipantNode",
            "CreateCaseFromProposalNode",
            "InitializeCreationEmbargoNode",
            "RelayCreationTimeRevisionNode",
            "SeedReporterSignatoryNode",
        )
    },
}

# ---------------------------------------------------------------------------
# 3. Classes that reach a state-write seam but write no participant or case
#    state, so carry no StateWriteCapable marker.  Entries are
#    (dotted module, class) → reason.
# ---------------------------------------------------------------------------
_ARCHIVE = (
    "stores a received or outbound activity or its object, which every"
    " replica keeps (RSH-08-003, CLP-10-017)"
)
_LEDGER = "writes ledger records, gated by ledger authority (ADR-0073)"
_LOCAL = (
    "the actor's own bookkeeping before or beside a case, not a record of"
    " the case (ADR-0041, CP-06)"
)
_REPLICATION = (
    "writes the CASE_MANAGER's per-peer replication state (pause, replay"
    " position), not a record of the case (CM-10-005, SYNC-15-003)"
)
_PROPOSAL_INDEX = (
    "records which Invite proposed an embargo to this replica, a per-replica"
    " correlation the replay never displaces (EP-09-003, EP-09-007)"
)
_B = "vultron.core.behaviors"
# permanent: RSH-08-003 (writes that are not participant or case state)
WRITES_NO_CASE_STATE: dict[tuple[str, str], str] = {
    (
        f"{_B}.case.accept_case_proposal_received_tree",
        "RecordCaseActorAcceptanceNode",
    ): _LOCAL,
    (f"{_B}.case.nodes.case_setup", "EnsureCaseActorHostedNode"): _LOCAL,
    (f"{_B}.case.nodes.conditions", "WritePendingReportCaseLinkNode"): _LOCAL,
    (f"{_B}.case.nodes.embargo_resolution", "CaseNotEmbargoEligibleNode"): (
        "asks EmbargoLifecycle whether the case is eligible; writes nothing"
    ),
    (f"{_B}.case.nodes.intake", "IntakeReceivedActivityNode"): _ARCHIVE,
    (
        f"{_B}.case.nodes.invite_ledger_backfill",
        "BackfillCanonicalLedgerToInviteeNode",
    ): _LEDGER,
    (
        f"{_B}.case.nodes.invite_received",
        "RecordInviteTrustAnchorNode",
    ): _LOCAL,
    (
        f"{_B}.case.nodes.proposal",
        "RequeuePendingCreateCaseActivityNode",
    ): _LOCAL,
    (
        f"{_B}.case.nodes.proposal_admission_actions",
        "EmitRejectCaseProposalNode",
    ): _LOCAL,
    (
        f"{_B}.case.nodes.proposal_admission_actions",
        "RecordProposalAdmissionNode",
    ): _LOCAL,
    (
        f"{_B}.case.nodes.proposal_admission_actions",
        "RecordProposalDeclineNode",
    ): _LOCAL,
    (
        f"{_B}.case.nodes.proposal_case_resolution",
        "StoreProposalReportNode",
    ): _ARCHIVE,
    (
        f"{_B}.case.nodes.proposal_retry_marker",
        "ClearCreateCaseMarkerNode",
    ): _LOCAL,
    (
        f"{_B}.case.nodes.proposal_retry_marker",
        "WriteCreateCaseMarkerNode",
    ): _LOCAL,
    (f"{_B}.case.nodes.replica_bootstrap", "BindReportCaseLinkNode"): _LOCAL,
    (
        f"{_B}.case.nodes.store_received_object",
        "StoreReceivedObjectNode",
    ): _ARCHIVE,
    (
        f"{_B}.case.nodes.submit_report",
        "StoreSubmitReportOfferRecordNode",
    ): _ARCHIVE,
    (
        f"{_B}.case.reject_case_proposal_received_tree",
        "RecordCaseProposalRejectionNode",
    ): _LOCAL,
    (f"{_B}.dead_letter.nodes.store", "StoreDeadLetterRecordNode"): _ARCHIVE,
    (f"{_B}.embargo.nodes.cascade", "PersistEmbargoEventNode"): _ARCHIVE,
    (f"{_B}.embargo.nodes.expiry", "EvaluateInviteExpiryNode"): (
        "asks EmbargoLifecycle whether an invite expired; writes nothing"
    ),
    (
        f"{_B}.embargo.nodes.manager_commit",
        "IndexOwnEmbargoProposalNode",
    ): _PROPOSAL_INDEX,
    (f"{_B}.embargo.nodes.proposal", "CreateAndStoreInviteNode"): _ARCHIVE,
    (
        f"{_B}.embargo.nodes.proposal",
        "IndexReceivedEmbargoProposalNode",
    ): _PROPOSAL_INDEX,
    (f"{_B}.helpers", "CreateObject"): _ARCHIVE,
    (f"{_B}.note.nodes.storage", "SaveNoteNode"): _ARCHIVE,
    (f"{_B}.report.nodes.case_creation", "CreateCaseActivity"): _ARCHIVE,
    (f"{_B}.report.nodes.storage", "StoreReportNode"): _ARCHIVE,
    (f"{_B}.sync.nodes.chain", "PersistLogEntryNode"): _LEDGER,
    (f"{_B}.sync.nodes.chain", "UpdateReplicationStateNode"): (_REPLICATION),
    (
        f"{_B}.sync.nodes.embargo_backfill",
        "BackfillAdmittedParticipantsNode",
    ): _REPLICATION,
    (f"{_B}.sync.nodes.fanout", "SendLogEntryToEachNode"): _REPLICATION,
    (f"{_B}.sync.nodes.receive", "PersistReceivedLogEntryNode"): _LEDGER,
    (f"{_B}.sync.nodes.replay", "SendMissingEntriesNode"): _REPLICATION,
}


def _ungated_state_writes() -> frozenset[_Write]:
    """``(module, factory, class)`` for each ungated marked node."""
    return frozenset(
        (rel, factory, type(node).__name__)
        for (rel, factory), tree in built_received_trees().items()
        for node in ungated_nodes([tree], StateWriteCapable)
    )


def test_every_received_tree_factory_is_built() -> None:
    """Guard against a vacuous walk: the factories the ratchet names exist."""
    built = set(built_received_trees())
    named = {(rel, factory) for rel, factory, _ in set(REPLICA_STATE_WRITES)}
    assert named <= built, sorted(named - built)
    assert (
        f"{_Y}/announce_tree.py",
        "create_announce_log_entry_tree",
    ) in built


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("ARCH-18-001")
def test_received_tree_state_writes_are_gated_or_known() -> None:
    _assert_pinned(
        "state write outside the CASE_MANAGER gate in a received tree",
        _ungated_state_writes(),
        frozenset(REPLICA_STATE_WRITES),
        "pass it as manager_effects (RSH-08-003, RSH-08-004); a replay or"
        " bootstrap write is classified in REPLICA_STATE_WRITES with its"
        " reason",
    )


@pytest.mark.parametrize("write", sorted(REPLICA_STATE_WRITES))
def test_each_exempt_write_carries_a_one_line_reason(write: _Write) -> None:
    reason = REPLICA_STATE_WRITES[write]
    assert reason.strip() and "\n" not in reason, write


@functools.cache
def _state_write_helpers() -> frozenset[str]:
    """Top-level ``vultron.core`` functions that may reach a state write.

    A text-only fixed point (:func:`_corpus.names_reaching`) from the
    DataLayer write methods and :data:`_STATE_WRITE_METHODS`, over functions
    only, so a node that writes through a helper — ``record_embargo_proposal_index``,
    ``_create_and_attach_participant`` — is found as surely as one that calls
    ``dl.save`` itself.  The DataLayer method names are matched separately,
    as attribute calls.
    """
    return (
        _corpus.names_reaching(
            _DATALAYER_WRITES | _STATE_WRITE_METHODS,
            under=_CORE_ROOT,
            classes=False,
        )
        - _DATALAYER_WRITES
    )


class _ClassSummary(NamedTuple):
    """What the seam scan needs from one top-level behaviors class."""

    site: tuple[str, str]
    called: frozenset[str]
    calls_a_datalayer_write: bool
    bases: frozenset[str]


def _summarize(site: tuple[str, str], scope: ast.ClassDef) -> _ClassSummary:
    calls = list(_calls(scope))
    return _ClassSummary(
        site=site,
        called=frozenset(name for _, name in calls),
        calls_a_datalayer_write=any(
            name in _DATALAYER_WRITES and isinstance(call.func, ast.Attribute)
            for call, name in calls
        ),
        bases=frozenset(
            base.id for base in scope.bases if isinstance(base, ast.Name)
        ),
    )


def _hides_children(module: str, name: str) -> bool:
    """True unless the class is a composite or decorator the walk descends.

    A leaf node, or a plain helper class, that builds a writer node and
    ticks it itself hides that write from the tree walk; a composite that
    takes it as a child does not.
    """
    cls = getattr(importlib.import_module(module), name)
    return not issubclass(cls, (Composite, Decorator))


def _writer_fixed_point(
    summaries: list[_ClassSummary],
    seams: frozenset[str],
    hides_children: Callable[[tuple[str, str]], bool],
) -> set[tuple[str, str]]:
    """The classes that reach a state write, over *summaries*.

    A class reaches one by calling a DataLayer write method or a *seam*, or
    — when *hides_children* says the walk cannot see what it builds — by
    calling a writer class.  The writer classes are every class found, and
    every subclass of one, unless pinned in :data:`WRITES_NO_CASE_STATE`.
    """
    found: set[tuple[str, str]] = set()
    writers: set[str] = set()
    while True:
        before = len(writers)
        for summary in summaries:
            if (
                summary.calls_a_datalayer_write
                or summary.called & seams
                or (summary.called & writers and hides_children(summary.site))
            ):
                found.add(summary.site)
            elif not summary.bases & writers:
                continue
            if summary.site not in WRITES_NO_CASE_STATE:
                writers.add(summary.site[1])
        if len(writers) == before:
            return found


def _module_of(path: Path) -> str:
    return _rel(path).removesuffix(".py").replace("/", ".")


def _text_candidates(seams: frozenset[str]) -> set[tuple[str, str]]:
    """A superset of the writer classes, from source text alone.

    Every call the AST walk can see is a ``name(`` in the class's text, so
    the text fixed point over-approximates the precise one; it parses
    nothing, and only the files holding a candidate are parsed after it.
    """
    summaries = [
        _ClassSummary(
            site=(_module_of(path), name),
            called=_corpus.called_names(span),
            calls_a_datalayer_write=any(
                f".{write}(" in span for write in _DATALAYER_WRITES
            ),
            bases=bases,
        )
        for path, source in _corpus.all_sources(under=_BEHAVIORS_ROOT)
        for name, bases, span in _corpus.class_spans(source)
    ]
    return _writer_fixed_point(summaries, seams, lambda _: True)


@functools.cache
@_corpus.gc_paused()
def _state_write_seam_classes() -> frozenset[tuple[str, str]]:
    """(module, class) for each behaviors class that reaches a state write.

    A class reaches one by calling, in any of its methods, a DataLayer write
    method, a :data:`_STATE_WRITE_METHODS` seam, or a derived write helper
    (:func:`_state_write_helpers`) — or, unless it is a composite the walk
    descends, by building a writer class (``RMClosureWriter`` ticking a
    ``CreateParticipantStatusNode``); see :func:`_writer_fixed_point`.  A
    text pass names the candidates first (:func:`_text_candidates`), so only
    their files are parsed and only they are walked (TB-13-008).
    """
    seams = _STATE_WRITE_METHODS | _state_write_helpers()
    candidates = _text_candidates(seams)
    modules = {module for module, _ in candidates}
    summaries = [
        _summarize((module, scope.name), scope)
        for path in _corpus.paths_under(_BEHAVIORS_ROOT)
        if (module := _module_of(path)) in modules
        for scope in _top_level_scopes(_corpus.tree_of(path))
        if isinstance(scope, ast.ClassDef)
        and (module, scope.name) in candidates
    ]
    return frozenset(
        _writer_fixed_point(
            summaries, seams, lambda site: _hides_children(*site)
        )
    )


def _is_marked(module: str, name: str) -> bool:
    cls = getattr(importlib.import_module(module), name)
    return inspect.isclass(cls) and issubclass(cls, StateWriteCapable)


def _is_node(module: str, name: str) -> bool:
    """A tree node, which the walk can meet — not a helper such as
    ``RMClosureWriter``, which counts as a writer only through the node
    that builds it."""
    cls = getattr(importlib.import_module(module), name)
    return inspect.isclass(cls) and issubclass(cls, Behaviour)


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("ARCH-18-005")
def test_every_state_writer_carries_the_marker_or_is_pinned() -> None:
    classes = _state_write_seam_classes()
    assert classes, "no state-write seam caller found — seam names drifted?"
    _assert_pinned(
        "unmarked class reaching a state-write seam",
        frozenset(
            site
            for site in classes
            if _is_node(*site) and not _is_marked(*site)
        ),
        frozenset(WRITES_NO_CASE_STATE),
        "mix in StateWriteCapable if it writes participant or case state;"
        " otherwise add it to WRITES_NO_CASE_STATE with the reason",
    )


@pytest.mark.parametrize("site", sorted(WRITES_NO_CASE_STATE))
def test_each_non_state_writer_carries_a_one_line_reason(
    site: tuple[str, str],
) -> None:
    reason = WRITES_NO_CASE_STATE[site]
    assert reason.strip() and "\n" not in reason, site


def test_the_marker_covers_the_named_write_families() -> None:
    """The node families RSH-08-003 names are found by the marker."""
    from vultron.core.behaviors.case.nodes.case_participant_received import (
        ParticipantMoveEffectNode,
    )
    from vultron.core.behaviors.case.nodes.participant.status import (
        CreateParticipantStatusNode,
    )
    from vultron.core.behaviors.embargo.nodes.lifecycle import (
        _EmbargoLifecycleNode,
    )
    from vultron.core.behaviors.status.nodes.case_status import (
        AppendCaseStatusToCaseNode,
    )
    from vultron.core.behaviors.sync.nodes._helpers import _LedgerEffectNode

    for cls in (
        ParticipantMoveEffectNode,
        AppendCaseStatusToCaseNode,
        CreateParticipantStatusNode,
        _EmbargoLifecycleNode,
        _LedgerEffectNode,
    ):
        assert issubclass(cls, StateWriteCapable), cls


def test_the_seam_scan_follows_helpers_and_hidden_nodes() -> None:
    """A write through a helper function or a privately ticked writer node
    is found as surely as a direct ``dl.save`` (the marker check's reach)."""
    found = _state_write_seam_classes()
    for site in (
        # through a helper that saves the participant
        (f"{_B}.case.nodes.proposal_consent", "SeedReporterSignatoryNode"),
        # through a helper that saves the case
        (f"{_B}.embargo.nodes.proposal", "IndexReceivedEmbargoProposalNode"),
        # ticking a CreateParticipantStatusNode it builds itself
        (f"{_B}.report.nodes.develop_fix", "TransitionCStoFixReady"),
        # through RMClosureWriter, a helper class that ticks one
        (f"{_B}.case.nodes.leave.advance", "AdvanceParticipantToRMClosedNode"),
    ):
        assert site in found, site
