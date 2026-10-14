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
from typing import Any

import py_trees
import pytest

from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.datalayer import DataLayer


def committed_event_types(dl: DataLayer, case_id: str) -> list[str]:
    """``event_type`` of every ledger entry committed for *case_id*."""
    return [
        str(entry.event_type)
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


def commit_case_fully_closed(
    dl: DataLayer, case_id: str, actor_id: str
) -> None:
    """Append the ``case_fully_closed`` entry at the tail of *case_id*'s ledger.

    Chained to the current tail, so the case's ledger stays a valid chain.
    """
    entries = ledger_entries(dl, case_id)
    dl.create(
        _to_persistable_entry(
            HashChainLedgerRecord(
                case_id=case_id,
                log_index=entries[-1].log_index + 1 if entries else 0,
                object_id=f"{case_id}/activities/owner-leave",
                event_type="case_fully_closed",
                payload_snapshot={"actor": actor_id},
                prev_log_hash=entries[-1].entry_hash if entries else "0" * 64,
            )
        )
    )


def creation_entry_sequence(
    dl: DataLayer, case: VulnerabilityCase
) -> list[tuple[str, str]]:
    """The ``(event_type, object id)`` entries creating *case* commits.

    One rule for every creation path, read off the resulting case file: the
    genesis ``create_case``, each linked report, each participant's statuses
    in roster order, then each case status (CLP-07-013).  Two paths that
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
        sequence += [
            ("add_participant_status_to_participant", status.id_)
            for status in participant.participant_statuses
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
