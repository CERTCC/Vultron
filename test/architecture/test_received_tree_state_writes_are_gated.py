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
2. **Ratchet** :data:`KNOWN_UNGATED_STATE_WRITES` — ungated writes awaiting
   the gating fix, one owner per tree.  Terminal value: empty; its strict
   ``xfail`` goal test fails the build when it empties without being deleted.
3. **Pinned exemption set** :data:`REPLICA_STATE_WRITES` — trees whose
   ungated writes are the design: the ledger replay itself, and the
   bootstrap trees that mint a case or seed a replica before any
   CASE_MANAGER gate could pass.
4. Every behaviors class that reaches a state-write seam carries the marker,
   or is in the **pinned exemption set** :data:`WRITES_NO_CASE_STATE` with
   its reason — so the marker, not a name list, decides what the walk finds.

Every set is held to equality in both directions (TB-10-002, ARCH-18-001):
a new ungated write fails, and so does a row the code no longer needs.
Entries are ``(module, factory, node class)`` so a second ungated writer in
an already-listed tree fails too.
"""

import ast
import importlib
import inspect

import pytest

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

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"

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
#: Core services that write case or participant state on a node's behalf.
_STATE_WRITE_SERVICES = frozenset(
    {
        "EmbargoLifecycle",
        "apply_pec_transition",
        "apply_pec_transition_if_legal",
        "idempotent_store",
        "link_report_case_links",
        "persist_creation_time_embargo",
        "store_carried_embargo",
        "store_embedded_participants",
    }
)

# ---------------------------------------------------------------------------
# 2. Received trees whose state writes still run on every replica.  Each row
#    leaves when its tree moves the write into manager_effects — after the
#    write's replay slot exists (RSH-08-004) — in the same commit
#    (ARCH-18-002).
# ---------------------------------------------------------------------------
# owner: #3814 (every entry; the RSH-08-003 gating half of that issue)
KNOWN_UNGATED_STATE_WRITES: frozenset[_Write] = frozenset(
    {
        # owner: #3814
        (
            f"{_C}/case_participant_received_tree.py",
            "create_add_case_participant_received_tree",
            "AddCaseParticipantToCaseReceivedNode",
        ),
        # owner: #3814
        (
            f"{_C}/ownership_transfer_tree.py",
            "create_accept_ownership_transfer_tree",
            "AcceptCaseOwnershipTransferNode",
        ),
        # owner: #3814
        (
            f"{_C}/update_tree.py",
            "create_update_case_received_tree",
            "ApplyCaseUpdateNode",
        ),
        # owner: #3814
        (
            f"{_E}/announce_teardown_tree.py",
            "add_embargo_to_case_tree",
            "SetEmbargoActiveNode",
        ),
        # owner: #3814 — CM-31-010's paused-stream exception is decided here
        (
            f"{_E}/announce_teardown_tree.py",
            "remove_embargo_from_case_tree",
            "ClearActiveEmbargoNode",
        ),
        # owner: #3814
        (
            f"{_E}/announce_teardown_tree.py",
            "remove_embargo_from_case_tree",
            "RemoveFromProposedEmbargoesNode",
        ),
        # owner: #3814
        (
            f"{_N}/create_note_tree.py",
            "create_note_tree",
            "AttachNoteToCaseNode",
        ),
        # owner: #3814
        (
            f"{_R}/prioritize_tree.py",
            "create_defer_case_tree",
            "CreateParticipantStatusNode",
        ),
        # owner: #3814
        (
            f"{_R}/prioritize_tree.py",
            "create_engage_case_tree",
            "CreateParticipantStatusNode",
        ),
        # owner: #3814 — the Engage's carried snapshot is written by every
        # receiver, from a participant sender, before the commit
        (
            f"{_R}/prioritize_tree.py",
            "create_engage_case_tree",
            "HoldCarriedEmbargoNode",
        ),
        # owner: #3814 — as above
        (
            f"{_R}/prioritize_tree.py",
            "create_engage_case_tree",
            "StoreEmbeddedParticipantsNode",
        ),
        # owner: #3814 — gate after #4304 makes the commit canonical
        (
            f"{_R}/received_report_trees.py",
            "create_close_report_received_tree",
            "CreateParticipantStatusNode",
        ),
        # owner: #3814 — gate after #4304 makes the commit canonical
        (
            f"{_R}/received_report_trees.py",
            "create_invalidate_report_received_tree",
            "CreateParticipantStatusNode",
        ),
        # owner: #3814
        (
            f"{_R}/received_report_trees.py",
            "create_validate_report_received_tree",
            "TransitionRMtoValid",
        ),
        # owner: #3814
        (
            f"{_S}/add_case_status_tree.py",
            "add_case_status_tree",
            "AppendCaseStatusToCaseNode",
        ),
        # owner: #3814
        (
            f"{_S}/add_participant_status_tree.py",
            "add_participant_status_tree",
            "AppendStatusAndSaveParticipantNode",
        ),
        # owner: #3814
        (
            f"{_S}/add_participant_status_tree.py",
            "add_participant_status_tree",
            "EmitCaseStatusUpdateNode",
        ),
        # owner: #3814
        (
            f"{_S}/add_participant_status_tree.py",
            "add_participant_status_tree",
            "ResolveAndPersistStatusObjectNode",
        ),
    }
)

# ---------------------------------------------------------------------------
# 3. Received trees whose ungated writes are the design, with the reason.
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
# permanent: RSH-08-003 (replay and bootstrap writes; see each reason)
REPLICA_STATE_WRITES: dict[_Write, str] = {
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
            "ApplyEmbargoReinviteFromLedgerNode",
            "ApplyEmbargoRejectionFromLedgerNode",
            "ApplyHonourLateAcceptFromLedgerNode",
            "ApplyInviteAcceptFromLedgerNode",
            "ApplyInviteExpiryFromLedgerNode",
            "ApplyInviteExpiryNoopFromLedgerNode",
            "ApplyNoteFromLedgerNode",
            "ApplyOfferOwnershipTransferFromLedgerNode",
            "ApplyOfferReportFromLedgerNode",
            "ApplyOwnershipTransferFromLedgerNode",
            "ApplyParticipantStatusFromLedgerNode",
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
        )
    },
    # create_create_case_tree has no production caller; #4330 retires or wires it
    **{
        (f"{_C}/create_tree.py", "create_create_case_tree", cls): _MINT
        for cls in ("PersistCase", "PersistOwnerCaseNode")
    },
}

# ---------------------------------------------------------------------------
# 4. Classes that reach a state-write seam but write no participant or case
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
_B = "vultron.core.behaviors"
# permanent: RSH-08-003 (writes that are not participant or case state)
WRITES_NO_CASE_STATE: dict[tuple[str, str], str] = {
    (
        f"{_B}.case.accept_case_proposal_received_tree",
        "RecordCaseActorAcceptanceNode",
    ): _LOCAL,
    (f"{_B}.case.nodes.case_setup", "EnsureCaseActorHostedNode"): _LOCAL,
    (
        f"{_B}.case.nodes.communication",
        "CreateAndPersistCaseActivityNode",
    ): _ARCHIVE,
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
    (f"{_B}.embargo.nodes.proposal", "CreateAndStoreInviteNode"): _ARCHIVE,
    (f"{_B}.helpers", "CreateObject"): _ARCHIVE,
    (f"{_B}.note.nodes.storage", "SaveNoteNode"): _ARCHIVE,
    (f"{_B}.report.nodes.case_creation", "CreateCaseActivity"): _ARCHIVE,
    (f"{_B}.report.nodes.storage", "StoreReportNode"): _ARCHIVE,
    (f"{_B}.sync.nodes.chain", "PersistLogEntryNode"): _LEDGER,
    (f"{_B}.sync.nodes.chain", "UpdateReplicationStateNode"): _LEDGER,
    (f"{_B}.sync.nodes.receive", "PersistReceivedLogEntryNode"): _LEDGER,
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
    named = {
        (rel, factory)
        for rel, factory, _ in KNOWN_UNGATED_STATE_WRITES
        | set(REPLICA_STATE_WRITES)
    }
    assert named <= built, sorted(named - built)
    assert (
        f"{_Y}/announce_tree.py",
        "create_announce_log_entry_tree",
    ) in built


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("ARCH-18-001")
def test_received_tree_state_writes_are_gated_or_known() -> None:
    assert not KNOWN_UNGATED_STATE_WRITES & set(REPLICA_STATE_WRITES)
    _assert_pinned(
        "state write outside the CASE_MANAGER gate in a received tree",
        _ungated_state_writes(),
        KNOWN_UNGATED_STATE_WRITES | frozenset(REPLICA_STATE_WRITES),
        "pass it as manager_effects once its replay slot exists"
        " (RSH-08-003, RSH-08-004); a replay or bootstrap write is"
        " classified in REPLICA_STATE_WRITES with its reason",
    )


@pytest.mark.spec("RSH-08-003")
@pytest.mark.xfail(
    strict=True,
    reason="goal: every received-side state write is CASE_MANAGER-gated"
    " (#3814); when KNOWN_UNGATED_STATE_WRITES empties this passes and"
    " strict xfail fails the build — delete this test and the empty set",
)
def test_goal_no_received_state_write_is_ungated() -> None:
    assert frozenset() == KNOWN_UNGATED_STATE_WRITES


@pytest.mark.parametrize("write", sorted(REPLICA_STATE_WRITES))
def test_each_exempt_write_carries_a_one_line_reason(write: _Write) -> None:
    reason = REPLICA_STATE_WRITES[write]
    assert reason.strip() and "\n" not in reason, write


@_corpus.gc_paused()
def _state_write_seam_classes() -> frozenset[tuple[str, str]]:
    """(module, class) for each behaviors class that calls a state-write seam."""
    found: set[tuple[str, str]] = set()
    fragments = (
        *(f".{name}(" for name in _DATALAYER_WRITES),
        *_STATE_WRITE_SERVICES,
    )
    for path, tree in _corpus.files_mentioning(
        *fragments, under=_BEHAVIORS_ROOT
    ):
        module = _rel(path).removesuffix(".py").replace("/", ".")
        for scope in _top_level_scopes(tree):
            if not isinstance(scope, ast.ClassDef):
                continue
            if any(
                name in _STATE_WRITE_SERVICES
                or (
                    name in _DATALAYER_WRITES
                    and isinstance(call.func, ast.Attribute)
                )
                for call, name in _calls(scope)
            ):
                found.add((module, scope.name))
    return frozenset(found)


def _is_marked(module: str, name: str) -> bool:
    cls = getattr(importlib.import_module(module), name)
    return inspect.isclass(cls) and issubclass(cls, StateWriteCapable)


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("ARCH-18-005")
def test_every_state_writer_carries_the_marker_or_is_pinned() -> None:
    classes = _state_write_seam_classes()
    assert classes, "no state-write seam caller found — seam names drifted?"
    _assert_pinned(
        "unmarked class reaching a state-write seam",
        frozenset(site for site in classes if not _is_marked(*site)),
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
        AddCaseParticipantToCaseReceivedNode,
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
        AddCaseParticipantToCaseReceivedNode,
        AppendCaseStatusToCaseNode,
        CreateParticipantStatusNode,
        _EmbargoLifecycleNode,
        _LedgerEffectNode,
    ):
        assert issubclass(cls, StateWriteCapable), cls
