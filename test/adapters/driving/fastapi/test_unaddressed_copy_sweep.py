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

"""An unaddressed copy of any message is refused, receipted, and acts on nothing.

Every received tree runs the addressee door guard by default (HP-01-005,
#4832), so a store that is neither the sender nor a recipient of an activity
refuses it whatever the message is.  This sweep delivers every dispatchable
example activity (the corpus ``test_vocab_examples_dispatchable`` checks) to a
bystander's store through the real inbox pipeline, one example per received
tree family, and asserts the copy is refused, that what remains of it is a
receipt stub with no body (CLP-10-018), that nothing else is written and that
nothing is sent.

No family writes before the door: ``Offer(VulnerabilityReport)``, which once
kept the report and its offer record ahead of a late check of its own, takes
the ordinary door order like every other (ADR-0154, #5046), so a bystander's
copy of it keeps nothing but the receipt stub (HP-10-001).
"""

from collections import Counter
from typing import Any

import pytest

from test.architecture._vocab_example_corpus import (
    activity_examples,
    wire_body,
)
from test.support.received import extract_stamped
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIReceivedOutcomePort,
)
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events import resolve_case_context_id
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.received_body import received_body_digest
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

_BYSTANDER = canonical_actor_uri("unaddressed-bystander")
# A separate store, so measuring the ingress never touches the bystander's.
#: Who an example with no ``to`` is addressed to, so the bystander's copy is a
#: copy of mail sent to someone else, as a misrouted one would be.
_ADDRESSEE = canonical_actor_uri("the-actual-addressee")

_EXAMPLES: dict[str, as_Activity] = activity_examples()

#: Examples with no pattern or semantics by decision; see
#: ``test_vocab_examples_dispatchable._KNOWN_UNDISPATCHABLE``.
_UNDISPATCHABLE: frozenset[str] = frozenset()

#: Examples of a recognized semantic type no received use case handles
#: (SE-05-002): reported "no use case found", so no addressee check runs, and
#: like any refusal each leaves a receipt stub and no body (CLP-10-074).  Each
#: is a CASE_MANAGER-only act (ADR-0140, #4724).
_UNHANDLED = frozenset(
    {
        "undo_embargo_invite",
        "create_participant",
        "update_participant",
        "update_case",
        "create_embargo_event",
        "create_embargo_consent",
        "update_embargo_consent",
    }
)

#: Examples a bystander refuses before any received tree runs, so intake never
#: archives them; each names the issue that owns moving the refusal into the
#: tree (CLP-10-005, CLP-10-018).  They are still refused, write nothing and
#: send nothing.
_REFUSED_BEFORE_ANY_TREE: dict[str, str] = {}


def _object_counts(dl: SqliteDataLayer) -> Counter[str]:
    """How many stored objects of each type *dl* holds."""
    return Counter(
        {
            type_: n
            for type_, n in dl.count_all().items()
            if type_ != "_default"
        }
    )


def _copy_for_someone_else(activity: as_Activity) -> as_Activity:
    """*activity* as sent to its own recipients, or to :data:`_ADDRESSEE`."""
    if activity.to:
        return activity
    return activity.model_copy(update={"to": [_ADDRESSEE]})


def _seed_named_case(dl: SqliteDataLayer, activity: as_Activity) -> None:
    """Give the bystander the case the copy names, as a replica would hold.

    A handler that looks the case up before its tree runs would otherwise
    refuse an unknown case, and the sweep would never reach the door.  The
    bystander is no participant of it, so a ``{case}/participants`` address
    would not name it either.
    """
    event = extract_stamped(activity)
    # A case-object event (``Add(Note)``, ``Remove(Note)``, ...) names the
    # case as its ``case_id``; any other names it as its context.
    case_id = resolve_case_context_id(event) or getattr(event, "case_id", None)
    if case_id and dl.read(case_id) is None:
        dl.create(VulnerabilityCase(id_=case_id, attributed_to=_ADDRESSEE))


def _deliver(dl: SqliteDataLayer, body: dict[str, Any]) -> InboxOutcome:
    """Run the inbox pipeline once, with production wiring (IBP-04-002)."""
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_BYSTANDER, dispatcher=make_dispatcher()
        ),
        received_outcome_port=FastAPIReceivedOutcomePort(dl),
        clock=SystemClock(),
    )


@pytest.fixture
def bystander_dl():
    """The store of an actor no example names as its sender or recipient."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_BYSTANDER)
    yield dl
    dl.close()


def test_the_sweep_has_examples() -> None:
    """A sweep over nothing passes vacuously (DF-09-009)."""
    assert len(_EXAMPLES) > 50
    assert set(_EXAMPLES) >= _UNDISPATCHABLE
    assert "submit_report" in _EXAMPLES
    assert set(_REFUSED_BEFORE_ANY_TREE) <= set(_EXAMPLES)
    assert set(_EXAMPLES) >= _UNHANDLED


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize(
    "name", sorted(set(_EXAMPLES) - _UNDISPATCHABLE), ids=str
)
def test_an_unaddressed_copy_is_refused_and_acts_on_nothing(
    name: str, bystander_dl: SqliteDataLayer
) -> None:
    activity = _copy_for_someone_else(_EXAMPLES[name])
    assert _BYSTANDER not in [activity.actor, *(activity.to or [])]
    _seed_named_case(bystander_dl, activity)
    before = _object_counts(bystander_dl)

    body = wire_body(activity)
    outcome = _deliver(bystander_dl, body)

    assert outcome.status is InboxOutcomeStatus.REJECTED, (
        f"{name}: {outcome.status} ({outcome.failure_reason})"
    )
    if name in _UNHANDLED:
        assert outcome.unhandled, f"{name} is handled now: drop it"
    receipt = ReceivedActivityRecord.build_id(activity.id_)
    if name in _REFUSED_BEFORE_ANY_TREE:
        # Pinned until its owning issue lands; then the entry must go.
        assert bystander_dl.read(receipt) is None, (
            f"{name} is receipted now: drop it from _REFUSED_BEFORE_ANY_TREE"
        )
    else:
        stub = bystander_dl.read(receipt)
        assert isinstance(stub, ReceivedActivityRecord), (
            f"{name}: the refused copy left no receipt"
        )
        # The receipt, not the message: the body is given up (CLP-10-018).
        assert stub.is_receipt_stub, (
            f"{name}: the refused copy is still held as {stub.stage}"
        )
        assert stub.received_body is None, (
            f"{name}: the refused copy's body is still held"
        )
        sender = getattr(activity.actor, "id_", activity.actor)
        assert stub.sender_id == str(sender), (
            f"{name}: the stub does not name the sender"
        )
        sealed = parse_activity(body).received_evidence_json
        assert sealed is not None
        assert stub.body_hash == received_body_digest(sealed), (
            f"{name}: the stub's digest is not the body's (IE-10-002)"
        )
        assert stub.refusal_reason, f"{name}: the stub records no reason"
    receipted = Counter(
        {}
        if name in _REFUSED_BEFORE_ANY_TREE
        else {ReceivedActivityRecord.__name__: 1}
    )
    # Ingress writes nothing (DL-06-006, IO-03-004), so every write counted
    # here is the handler's.
    written = _object_counts(bystander_dl) - before - receipted
    others = {type_: n for type_, n in written.items() if n}
    assert not others, f"{name}: an unaddressed copy wrote {others}"
    assert bystander_dl.outbox_list() == [], f"{name}: sent something"
    if name in _REFUSED_BEFORE_ANY_TREE:
        return
    if name in _UNHANDLED:
        return
    reason = outcome.failure_reason or ""
    assert "HP-01-005" in reason, (
        f"{name}: refused for another reason: {reason}"
    )
