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
"""Core reference fields refuse a blank at construction (CS-08-001, #3877).

Spec: CS-08-001, ARCH-10-001

Each case below constructs the model twice from the same kwargs: once with a
real URI in the reference slot (the control, which must succeed, so the failing
case is not failing for some other reason) and once with a blank (which must
raise).  The architecture ratchet proves the *type* of every field refuses a
blank; this proves the models actually do, through their own validators and
model config, in the shapes callers use.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.blank_strings import BLANKS
from vultron.core.models.activity import (
    VultronAccept,
    VultronActivity,
    VultronCreateCaseActivity,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronOutbox
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.pending_assertion import PendingAssertion
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.states.embargo_register import EmbargoRegisterStatus

ACTOR = "https://example.org/actors/vendor"
CASE = "https://example.org/cases/1"
URI = "https://example.org/things/1"

#: ``(label, build)`` where ``build(value)`` constructs the model with *value*
#: in the reference slot under test.
CASES: list[tuple[str, Callable[[Any], Any]]] = [
    (
        "VultronActivity.to",
        lambda v: VultronActivity(type_="Offer", actor=ACTOR, to=[v]),
    ),
    (
        "VultronActivity.cc",
        lambda v: VultronActivity(type_="Offer", actor=ACTOR, cc=[URI, v]),
    ),
    ("VultronAccept.result", lambda v: VultronAccept(actor=ACTOR, result=v)),
    (
        "VultronCreateCaseActivity.context",
        lambda v: VultronCreateCaseActivity(actor=ACTOR, context=v),
    ),
    (
        "VultronCreateCaseActivity.in_reply_to",
        lambda v: VultronCreateCaseActivity(actor=ACTOR, in_reply_to=v),
    ),
    (
        "VulnerabilityCase.case_participants",
        lambda v: VulnerabilityCase(id_=CASE, case_participants=[v]),
    ),
    (
        "VulnerabilityCase.actor_participant_index (value)",
        lambda v: VulnerabilityCase(
            id_=CASE, actor_participant_index={ACTOR: v}
        ),
    ),
    (
        "VulnerabilityCase.actor_participant_index (key)",
        lambda v: VulnerabilityCase(
            id_=CASE, actor_participant_index={v: URI}
        ),
    ),
    (
        "VulnerabilityCase.embargo_register (embargo)",
        lambda v: VulnerabilityCase(
            id_=CASE,
            embargo_register=[
                EmbargoRegisterEntry(
                    embargo=v, status=EmbargoRegisterStatus.ACTIVE
                )
            ],
        ),
    ),
    (
        "EmbargoRegisterEntry.embargo",
        lambda v: EmbargoRegisterEntry(
            embargo=v, status=EmbargoRegisterStatus.PROPOSED
        ),
    ),
    (
        "EmbargoRegisterEntry.replaces",
        lambda v: EmbargoRegisterEntry(
            embargo=f"{CASE}/embargoes/revision",
            status=EmbargoRegisterStatus.ACTIVE,
            replaces=v,
        ),
    ),
    (
        "VulnerabilityCase.parent_cases",
        lambda v: VulnerabilityCase(id_=CASE, parent_cases=[v]),
    ),
    (
        "VulnerabilityCase.case_activity",
        lambda v: VulnerabilityCase(id_=CASE, case_activity=[v]),
    ),
    ("VultronOutbox.items", lambda v: VultronOutbox(items=[v])),
    (
        "VultronOfferRecord.offer_to",
        lambda v: VultronOfferRecord(
            offer_id=URI, report_id=URI, offer_actor_id=ACTOR, offer_to=[v]
        ),
    ),
    (
        "VultronReplicationState.case_id",
        lambda v: VultronReplicationState(case_id=v, peer_id=ACTOR),
    ),
    (
        "VultronReplicationState.peer_id",
        lambda v: VultronReplicationState(case_id=CASE, peer_id=v),
    ),
    (
        "CaseLedgerEntry.case_id",
        lambda v: CaseLedgerEntry(
            case_id=v, log_object_id=URI, event_type="note_added"
        ),
    ),
    (
        "CaseLedgerEntry.log_object_id",
        lambda v: CaseLedgerEntry(
            case_id=CASE, log_object_id=v, event_type="note_added"
        ),
    ),
    (
        "HashChainLedgerRecord.object_id",
        lambda v: HashChainLedgerRecord(
            case_id=CASE, object_id=v, event_type="note_added"
        ),
    ),
    (
        "VultronEvent.receiving_actor_id",
        lambda v: VultronEvent(
            semantic_type=next(iter(MessageSemantics)),
            activity_id=URI,
            actor_id=ACTOR,
            receiving_actor_id=v,
        ),
    ),
]


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize(("label", "build"), CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("blank", BLANKS)
def test_blank_reference_is_refused_at_construction(
    label: str, build: Callable[[Any], Any], blank: str
) -> None:
    build(URI)  # control: the same construction with a real URI succeeds
    with pytest.raises(ValidationError):
        build(blank)


#: The core records that are stdlib dataclasses rather than Pydantic models;
#: ``NonEmptyString`` cannot reach them, so their ``__post_init__`` calls
#: ``require_non_empty`` instead.  ``(label, build)`` as above.
DATACLASS_CASES: list[tuple[str, Callable[[Any], Any]]] = [
    (
        "ProtocolPair.case_id",
        lambda v: ProtocolPair(
            case_id=v, request_event_type="offer", object_id=URI
        ),
    ),
    (
        "ProtocolPair.object_id",
        lambda v: ProtocolPair(
            case_id=CASE, request_event_type="offer", object_id=v
        ),
    ),
    (
        "ProtocolPair.reply_object_id",
        lambda v: ProtocolPair(
            case_id=CASE,
            request_event_type="offer",
            object_id=URI,
            reply_object_id=v,
        ),
    ),
    (
        "PendingAssertion.case_id",
        lambda v: PendingAssertion(case_id=v, event_type="e", object_id=URI),
    ),
    (
        "PendingAssertion.object_id",
        lambda v: PendingAssertion(case_id=CASE, event_type="e", object_id=v),
    ),
]


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize(
    ("label", "build"), DATACLASS_CASES, ids=[c[0] for c in DATACLASS_CASES]
)
@pytest.mark.parametrize("blank", BLANKS)
def test_blank_reference_is_refused_by_core_dataclasses(
    label: str, build: Callable[[Any], Any], blank: str
) -> None:
    build(URI)  # control
    with pytest.raises(ValueError, match="must be a non-empty string"):
        build(blank)


def test_protocol_pair_reply_object_id_stays_optional() -> None:
    """Absence is still allowed — the rule is "if present, then non-empty"."""
    pair = ProtocolPair(
        case_id=CASE, request_event_type="offer", object_id=URI
    )
    assert pair.reply_object_id is None and pair.is_open()


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("CS-22-001")
@pytest.mark.parametrize("blank", BLANKS)
def test_one_blank_predicate_decides_every_spelling(blank: str) -> None:
    """``is_blank_string`` is the single predicate the three checkers share.

    ``NonEmptyString``'s validator, ``require_non_empty`` and the wire layer's
    ``is_blank`` all decide through it, so a blank spelling any one of them
    refuses, all of them refuse.
    """
    from pydantic import TypeAdapter

    from vultron.primitives import (
        NonEmptyString,
        is_blank_string,
        require_non_empty,
    )
    from vultron.wire.as2.vocab.base.utils import is_blank

    assert is_blank_string(blank)
    assert is_blank(blank)
    with pytest.raises(ValueError, match="case_id must be a non-empty string"):
        require_non_empty(blank, "case_id")
    with pytest.raises(ValidationError):
        TypeAdapter(NonEmptyString).validate_python(blank)

    assert not is_blank_string("x")
    assert require_non_empty("x", "case_id") == "x"
