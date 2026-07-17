#!/usr/bin/env python
"""Regression tests: Announce(CaseLedgerEntry) ingress routing without pre-store.

These tests pin the SYNC-13 boundary: message ingress MUST route an inbound
``Announce(CaseLedgerEntry)`` to the log-entry semantic
(``ANNOUNCE_CASE_LEDGER_ENTRY``) on first delivery *without* the adapter
pre-storing the inline ``CaseLedgerEntry`` in the ledger/DataLayer
(SYNC-13-002, SYNC-13-003, SYNC-13-004).

Before the fix, ``FastAPIIngressAdapter.rehydrate`` re-read the activity from
the DataLayer by ID, which collapsed ``object_`` to a bare ID string when the
entry was (correctly) not pre-stored; ``find_matching_semantics`` then
mis-matched ``AnnounceVulnerabilityCasePattern`` and the log-entry BT never
ran.  See issues #1324, #1447, #1472.
"""

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

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
    StoredActivityIngressAdapter,
)
from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import CaseLedgerEntry

_CASE_ID = "https://example.org/cases/case-ingress-routing"
_ENTRY_ID = "https://example.org/cases/case-ingress-routing/log/entry-1"
_INVITEE_ID = "https://example.org/actors/vendor2"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(db_url="sqlite:///:memory:")


def _make_announce_body() -> dict:
    """Build the wire body for an Announce(CaseLedgerEntry)."""
    entry = CaseLedgerEntry(
        id_=_ENTRY_ID,
        case_id=_CASE_ID,
        log_object_id=_INVITEE_ID,
        event_type="accept_invite_actor_to_case",
        payload_snapshot={"actor": _INVITEE_ID},
        entry_hash="hash-1",
        prev_log_hash="hash-0",
        log_index=1,
    )
    announce = announce_log_entry_activity(
        entry,
        id_="https://example.org/activities/announce-entry-1",
        actor="https://example.org/actors/case-actor",
        to=["https://example.org/actors/finder"],
    )
    return announce.model_dump(mode="json", by_alias=True, exclude_none=True)


def test_ingress_routes_ledger_entry_without_prestoring_entry(
    dl: SqliteDataLayer,
) -> None:
    """parse+rehydrate routes to ANNOUNCE_CASE_LEDGER_ENTRY, entry not stored.

    SYNC-13-002/003/004: the adapter must not write the CaseLedgerEntry to the
    DataLayer, and routing must still resolve to the log-entry semantic using
    the in-memory typed object.
    """
    body = _make_announce_body()
    adapter = FastAPIIngressAdapter(dl=dl, body=body)

    activity = adapter.parse(body)
    assert activity is not None

    # SYNC-13-002: the inline CaseLedgerEntry MUST NOT have been persisted by
    # the ingress adapter — only core's PersistReceivedLogEntry may do that.
    assert dl.read(_ENTRY_ID) is None, (
        "Ingress adapter must not pre-store the CaseLedgerEntry"
        " (SYNC-13-002); PersistReceivedLogEntry is the only writer."
    )

    rehydrated = adapter.rehydrate(activity)

    # SYNC-13-004: object_ must be the typed CaseLedgerEntry so routing is
    # unambiguous (not a bare ID string that also matches the case pattern).
    rehydrated_object = getattr(rehydrated, "object_", None)
    assert isinstance(rehydrated_object, CaseLedgerEntry), (
        "rehydrate must yield a typed CaseLedgerEntry object_ so semantic"
        f" routing is unambiguous; got {type(rehydrated_object).__name__}"
    )

    semantics = find_matching_semantics(rehydrated)
    assert semantics == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY, (
        "Announce(CaseLedgerEntry) must route to the log-entry semantic on"
        f" first delivery (SYNC-13-004); got {semantics}"
    )

    # Still not stored after rehydration.
    assert dl.read(_ENTRY_ID) is None


def test_replayed_ledger_entry_announce_routes_and_keeps_fields(
    dl: SqliteDataLayer,
) -> None:
    """A deferred Announce(CaseLedgerEntry) replayed by ID keeps its fields.

    #1472 AC-4: the replay path (StoredActivityIngressAdapter) reads the stored
    Announce by ID.  The inline entry is not stored as its own record
    (SYNC-13-002), so the full typed entry must survive inside the stored
    Announce and route to ANNOUNCE_CASE_LEDGER_ENTRY on replay.
    """
    body = _make_announce_body()
    ingress = FastAPIIngressAdapter(dl=dl, body=body)
    activity = ingress.parse(body)
    assert activity is not None

    # The entry itself is not an independent record...
    assert dl.read(_ENTRY_ID) is None

    # ...but replaying the stored Announce by ID reconstructs the typed entry.
    replayed = StoredActivityIngressAdapter(dl=dl).parse(activity.id_)
    assert replayed is not None
    replayed_object = getattr(replayed, "object_", None)
    assert isinstance(replayed_object, CaseLedgerEntry), (
        "Replayed Announce must carry a typed CaseLedgerEntry;"
        f" got {type(replayed_object).__name__}"
    )
    assert replayed_object.case_id == _CASE_ID
    assert replayed_object.event_type == "accept_invite_actor_to_case"
    assert (
        find_matching_semantics(replayed)
        == MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY
    )
