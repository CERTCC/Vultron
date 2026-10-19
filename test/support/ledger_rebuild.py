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

"""Rebuild a case from its CASE_MANAGER's ledger alone (CLP-07-013, CM-23-016).

Two replicas at the same ledger position hold the same case file, and a
replica infers nothing (ADR-0124).  So a store that starts empty and is handed
every entry the CASE_MANAGER committed, through the same inbox route a replica
uses, must end holding the CASE_MANAGER's participant records, consent rows and
embargo register (#4294 AC-5).

:func:`rebuild_from_ledger` builds that store and :func:`case_file_differences`
compares it with the CASE_MANAGER's; :func:`assert_rebuilds_from_ledger` does
both.  The demo tests and the per-actor-store integration tests call it on
every case their scenarios leave behind.

No replica slot creates the case itself: a replica is seeded with it
(SYNC-15-005).  So the rebuild seeds the empty store with what the ledger
already carries in full: for a ledger that starts at the case's creation, the
records its creation entries carry (CLP-07-013, #4440); for a test network
whose ledger starts on a case built outside it, the case as it stood before
the first entry was committed.  Every later write comes from an entry.
"""

import inspect
import json
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, cast

from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.inbox_hand_back_adapter import (
    InboxHandBackAdapter,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models import ledger_gap_buffer, pending_assertion
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.events import AnyReceivedEvent
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.semantic_registry import extract_event, use_case_map
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry,
)

#: The record each creation entry carries, and where in its snapshot.
_CREATION_RECORDS: Mapping[str, tuple[str, type[CoreObject]]] = {
    "create_case": ("object", VulnerabilityCase),
    "add_report_to_case": ("object", VulnerabilityReport),
    "add_participant_status_to_participant": ("target", CaseParticipant),
    "add_case_status_to_case": ("object", CaseStatus),
}


def received_event(activity: as_Activity, receiver: str) -> AnyReceivedEvent:
    """The event the inbox routes for *activity* delivered to *receiver*."""
    return extract_event(activity).model_copy(
        update={"receiving_actor_id": receiver}
    )


def run_use_case(
    dl: SqliteDataLayer, event: Any, *, without: frozenset[str] = frozenset()
) -> Any:
    """Run the use case for an extracted *event* against *dl*.

    It is composed with the ports it accepts, as the inbox composes it, minus
    the ones named in *without*.  Then delivers whatever the run handed back
    to the receiver's own inbox (SYNC-14-009), oldest first, as the inbox loop
    does after a delivery.  Returns the first delivery's own verdict.
    """
    use_case = use_case_map()[event.semantic_type]
    offered: dict[str, Any] = {
        "sync_port": SyncActivityAdapter(cast(Any, dl)),
        "trigger_activity": TriggerActivityAdapter(cast(Any, dl)),
        "wire_render_port": As2WireRenderAdapter(),
        "inbox_hand_back": InboxHandBackAdapter(cast(Any, dl)),
    }
    accepted = inspect.signature(use_case).parameters
    ports = {
        k: v for k, v in offered.items() if k in accepted and k not in without
    }
    verdict = use_case(dl, event, **ports).execute()
    while (queued_id := dl.inbox_pop()) is not None:
        handed_back = received_event(
            cast(as_Activity, rehydrate(queued_id, dl=dl)),
            event.receiving_actor_id,
        )
        run_use_case(dl, handed_back, without=without)
    return verdict


def receive_into(
    dl: SqliteDataLayer, body: dict[str, Any], receiver: str
) -> Any:
    """Route the sealed *body* into *receiver*'s store as the inbox routes it."""
    return run_use_case(dl, received_event(parse_activity(body), receiver))


def creation_records(entries: Iterable[CaseLedgerEntry]) -> list[CoreObject]:
    """The records a ledger's leading creation entries carry, latest copy each.

    Read from the entries' snapshots alone, as a replica's copy is: a later
    entry carrying the same record replaces the earlier copy.
    """
    records: dict[str, CoreObject] = {}
    for entry in entries:
        carried = _CREATION_RECORDS.get(str(entry.event_type))
        if carried is None:
            break
        key, cls = carried
        record = cls.model_validate(entry.payload_snapshot[key])
        records[record.id_] = record
    return list(records.values())


def _fresh_store(actor_id: str) -> SqliteDataLayer:
    """An empty in-memory store no other store in the process shares."""
    name = f"rebuild-{uuid.uuid4().hex}"
    return SqliteDataLayer(
        f"sqlite:///file:{name}?mode=memory&cache=shared&uri=true",
        actor_id=actor_id,
    )


def _case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase), f"no case '{case_id}'"
    return case


def rebuild_from_ledger(
    manager_dl: SqliteDataLayer,
    case_id: str,
    *,
    as_actor: str,
    seed: Iterable[CoreObject] | None = None,
) -> SqliteDataLayer:
    """Replay the CASE_MANAGER's whole ledger for *case_id* into an empty store.

    The store belongs to *as_actor*, a participant that is not the
    CASE_MANAGER.  It is seeded with *seed* when given (a ledger that starts on
    a case built outside it), otherwise with :func:`creation_records`.  Every
    entry is then delivered as the CASE_MANAGER's ``Announce(CaseLedgerEntry)``
    and must be applied; an entry the replica defers or refuses fails the
    rebuild, naming the entry.
    """
    entries = ledger_entries(manager_dl, case_id)
    assert entries, f"the CASE_MANAGER holds no ledger for '{case_id}'"
    manager_id = resolve_case_manager_id(
        _case(manager_dl, case_id), manager_dl
    )
    assert manager_id is not None, f"'{case_id}' names no CASE_MANAGER"
    assert as_actor != manager_id, "a rebuild runs on a replica"
    replica = _fresh_store(as_actor)
    for record in creation_records(entries) if seed is None else seed:
        replica.create(record.model_copy(deep=True))
    # The gap buffer and the pending-assertion store are per actor and
    # process-wide; the rebuild gets its own of each, so it neither reads nor
    # changes those of the live store it stands in for.
    registries: list[dict[str, Any]] = [
        ledger_gap_buffer._BUFFERS,
        pending_assertion._STORES,
    ]
    held = [registry.pop(as_actor, None) for registry in registries]
    try:
        _replay(replica, entries, manager_id=manager_id, as_actor=as_actor)
    finally:
        for registry, live in zip(registries, held, strict=True):
            registry.pop(as_actor, None)
            if live is not None:
                registry[as_actor] = live
    return replica


def _replay(
    replica: SqliteDataLayer,
    entries: list[CaseLedgerEntry],
    *,
    manager_id: str,
    as_actor: str,
) -> None:
    """Deliver each entry as the CASE_MANAGER's announcement; each applies."""
    for entry in entries:
        wire_entry = as_CaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
        announce = announce_log_entry_activity(
            entry=wire_entry, actor=manager_id, to=[as_actor]
        )
        body = json.loads(dump_outbound_body(announce))
        verdict = receive_into(replica, body, as_actor)
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            f"rebuild of '{entry.case_id}' as '{as_actor}': entry"
            f" {entry.log_index} ({entry.event_type}) was"
            f" {verdict.disposition.value}: {verdict.reason}"
        )


def _register(case: VulnerabilityCase) -> list[dict[str, Any]]:
    """The embargo register, as compared.

    Known difference (#4748): the ``Remove`` that ends an embargo carries only
    the termination's reason, never its cause, so a replica records a
    threat-signal termination as ``EARLY`` with no cause.  The cause is left
    out of the comparison; the reason is still compared.
    """
    rows = []
    for entry in case.embargo_register:
        row = entry.model_dump(mode="json")
        if row.get("termination"):
            row["termination"].pop("cause", None)
        rows.append(row)
    return rows


def _participant(record: CaseParticipant) -> dict[str, Any]:
    """A participant record, as compared: whole, consent rows included.

    Known difference (#4295): replaying an RM verdict (``engage_case``,
    ``validate_report``, …) builds the ``ParticipantStatus`` afresh, with its
    own id, so each status is compared without its id and times.  Every other
    field of the status, and of the record, is compared.
    """
    data = record.model_dump(mode="json")
    data["participant_statuses"] = [
        {
            k: v
            for k, v in status.items()
            if k not in ("id_", "published", "updated")
        }
        for status in data.get("participant_statuses") or []
    ]
    return data


def case_file_differences(
    manager_dl: SqliteDataLayer, replica_dl: SqliteDataLayer, case_id: str
) -> list[str]:
    """Every way *replica_dl*'s case file differs from the CASE_MANAGER's.

    Compares the roster, each participant record whole (its consent rows
    included) and the embargo register.  Empty when they are equal.
    """
    manager, replica = _case(manager_dl, case_id), _case(replica_dl, case_id)
    found: list[str] = []
    if replica.actor_participant_index != manager.actor_participant_index:
        found.append(
            f"roster: {replica.actor_participant_index}"
            f" != {manager.actor_participant_index}"
        )
    for participant_id in map(str, manager.actor_participant_index.values()):
        held = manager_dl.read(participant_id)
        copied = replica_dl.read(participant_id)
        assert isinstance(held, CaseParticipant), participant_id
        if not isinstance(copied, CaseParticipant):
            found.append(f"participant '{participant_id}' missing")
            continue
        want, got = _participant(held), _participant(copied)
        found.extend(
            f"participant '{participant_id}' {field}: {got.get(field)!r}"
            f" != {want[field]!r}"
            for field in want
            if got.get(field) != want[field]
        )
    want_register, got_register = _register(manager), _register(replica)
    if got_register != want_register:
        found.append(f"embargo register: {got_register} != {want_register}")
    return found


def replica_actor(manager_dl: SqliteDataLayer, case_id: str) -> str | None:
    """The first participant, in roster order, that is not the CASE_MANAGER.

    ``None`` when the CASE_MANAGER is the case's only participant: nothing
    replicates such a case.
    """
    case = _case(manager_dl, case_id)
    manager_id = resolve_case_manager_id(case, manager_dl)
    return next(
        (
            str(actor)
            for actor in case.actor_participant_index
            if str(actor) != manager_id
        ),
        None,
    )


def assert_rebuilds_from_ledger(
    manager_dl: SqliteDataLayer,
    case_id: str,
    *,
    as_actor: str | None = None,
    seed: Iterable[CoreObject] | None = None,
) -> None:
    """Rebuild *case_id* from its ledger and assert it equals the CASE_MANAGER's.

    *as_actor* defaults to :func:`replica_actor`.
    """
    if as_actor is None:
        as_actor = replica_actor(manager_dl, case_id)
    assert as_actor is not None, f"'{case_id}' has no participant to rebuild"
    replica = rebuild_from_ledger(
        manager_dl, case_id, as_actor=as_actor, seed=seed
    )
    try:
        differences = case_file_differences(manager_dl, replica, case_id)
    finally:
        replica.close()
    assert not differences, (
        f"'{case_id}' rebuilt from its ledger differs from the CASE_MANAGER's:\n"
        + "\n".join(differences)
    )
