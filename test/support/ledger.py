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

"""Read what a store's canonical case ledger holds, for test assertions."""

from collections.abc import Callable
from types import ModuleType
from typing import Any, cast

import py_trees
import pytest

from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent_semantic_types import (
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.predicates.addressing import snapshot_actor_id
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM


def committed_semantic_types(dl: DataLayer, case_id: str) -> list[str]:
    """``semantic_type`` of every ledger entry committed for *case_id*."""
    return [
        str(entry.semantic_type)
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry) and entry.case_id == case_id
    ]


def ledger_entries(dl: DataLayer, case_id: str) -> list[CaseLedgerEntry]:
    """Every ledger entry committed for *case_id*, in chain order."""
    entries = [
        entry
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry) and entry.case_id == case_id
    ]
    return sorted(entries, key=lambda entry: entry.log_index)


def is_consent_row_update(
    entry: CaseLedgerEntry,
    state: EmbargoConsentState,
    participant_id: str | None = None,
) -> bool:
    """Whether *entry* is the CASE_MANAGER's ``Update(EmbargoConsent)`` to *state*.

    An invitation expiry is the ``TIMED_OUT`` row's ``Update`` and an
    honoured late Accept the ``AGREED`` row's (CM-28-009, EMB-17-002,
    ADR-0140).  *participant_id*, when given, must be the row's participant.
    """
    if entry.semantic_type != UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE:
        return False
    row = entry.payload_snapshot.get("object")
    if not isinstance(row, dict) or row.get("state") != state.value:
        return False
    return participant_id is None or (
        snapshot_actor_id(row.get("attributedTo")) == participant_id
    )


def consent_row_updates(
    dl: DataLayer,
    case_id: str,
    state: EmbargoConsentState,
    participant_id: str | None = None,
) -> list[CaseLedgerEntry]:
    """*case_id*'s ``Update(EmbargoConsent)`` entries to *state*, in order."""
    return [
        entry
        for entry in ledger_entries(dl, case_id)
        if is_consent_row_update(entry, state, participant_id)
    ]


def commit_case_manager_closure(dl: DataLayer, case_id: str) -> None:
    """Append the CASE_MANAGER's own ``RM.CLOSED`` status entry to *case_id*.

    That entry is the owner-close write boundary (CM-23-002 step 2,
    CM-23-013): once the ledger holds it the case is fully closed.  The
    CASE_MANAGER is the one *dl*'s case names.  Only the entry is written:
    every closure check reads the ledger, never the CASE_MANAGER's
    participant record.  Chained to the current tail, so the case's ledger
    stays a valid chain.
    """
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase), f"no case '{case_id}' held"
    manager_id = resolve_case_manager_id(case, cast(CasePersistence, dl))
    assert manager_id is not None, f"case '{case_id}' names no CASE_MANAGER"
    entries = ledger_entries(dl, case_id)
    dl.create(
        _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=case_id,
                log_index=entries[-1].log_index + 1 if entries else 0,
                object_id=f"{case_id}/activities/case-manager-closed",
                semantic_type=(
                    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value
                ),
                payload_snapshot={
                    "type": "Add",
                    "actor": manager_id,
                    "object": {
                        "type": "ParticipantStatus",
                        "attributedTo": manager_id,
                        "rmState": RM.CLOSED.value,
                    },
                },
                prev_log_hash=entries[-1].entry_hash if entries else "0" * 64,
            )
        )
    )


def creation_entry_sequence(
    dl: DataLayer, case: VulnerabilityCase
) -> list[tuple[str, str]]:
    """The ``(semantic_type, object id)`` entries creating *case* commits.

    One rule for every creation path, read off the resulting case file: the
    genesis ``create_case``, each linked report, each participant's record
    created with its first status and then its later statuses, in roster
    order, then each case status (CLP-07-013, CM-23-007).  Two paths that
    produce the same case therefore commit the same sequence.
    """
    sequence = [("create_case", case.id_)]
    sequence += [
        ("add_report_to_case", str(_as_id(report)))
        for report in case.vulnerability_reports
    ]
    for participant_ref in case.case_participants:
        participant = dl.read(str(_as_id(participant_ref)))
        assert isinstance(participant, CaseParticipant), participant_ref
        sequence.append(("create_case_participant", participant.id_))
        sequence += [
            ("add_participant_status_to_participant", status.id_)
            for status in participant.participant_statuses[1:]
        ]
    sequence += [
        ("add_case_status_to_case", str(_as_id(status)))
        for status in case.case_statuses
    ]
    return sequence


def fail_commits(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    *,
    allowed: int = 0,
    when: Callable[[dict[str, Any]], bool] = lambda _kwargs: True,
) -> list[str]:
    """Make *module*'s ledger commits fail, after *allowed* of them succeed.

    Replaces ``create_commit_log_entry_tree`` as *module* names it with a
    tree that fails, so the code under test sees a refused commit exactly as
    it would see a real one.  Only commits whose keyword arguments satisfy
    *when* are counted and failed; any other commit runs as normal.

    Returns:
        The ``object_id`` of every counted commit, in order, as it is made.
    """
    original: Callable[..., py_trees.behaviour.Behaviour] = (
        module.create_commit_log_entry_tree
    )
    seen: list[str] = []

    def _tree(*args: Any, **kwargs: Any) -> py_trees.behaviour.Behaviour:
        if when(kwargs):
            seen.append(kwargs["object_id"])
            if len(seen) > allowed:
                return py_trees.behaviours.Failure(name="ForcedCommitFailure")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "create_commit_log_entry_tree", _tree)
    return seen


def record_sends_and_commits(
    monkeypatch: pytest.MonkeyPatch, actor_id: str
) -> list[tuple[str, str]]:
    """Record, in order, what *actor_id*'s store queues and commits.

    Each outbox append that queues an activity adds ``("queued", activity
    id)``; each ledger entry the store commits adds ``(semantic_type, object
    id)``.  The one list shows whether a sent activity reached the outbox
    before the entry recording it (ADR-0119).

    Returns:
        The list, filled in as the code under test runs.
    """
    from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

    events: list[tuple[str, str]] = []
    original_append = SqliteDataLayer.outbox_append
    original_save = SqliteDataLayer.save

    def _append(self: SqliteDataLayer, activity_id: str) -> bool:
        queued = original_append(self, activity_id)
        if queued and self.actor_id == actor_id:
            events.append(("queued", activity_id))
        return queued

    def _save(self: SqliteDataLayer, obj: Any) -> Any:
        is_new_entry = (
            isinstance(obj, CaseLedgerEntry)
            and self.actor_id == actor_id
            and self.read(obj.id_) is None
        )
        result = original_save(self, obj)
        if is_new_entry:
            events.append((str(obj.semantic_type), str(obj.log_object_id)))
        return result

    monkeypatch.setattr(SqliteDataLayer, "outbox_append", _append)
    monkeypatch.setattr(SqliteDataLayer, "save", _save)
    return events
