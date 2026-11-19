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

"""Both status ``Add`` forms name their history and their case (ADR-0204).

A status ``Add`` names the status history it extends in ``target`` and the
case in ``context``; a receiver reads the participant or case from the
history and the case from ``context``, with no shim for the old forms.
"""

import pytest

from test.support.objects import make
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Add
from vultron.wire.as2.vocab.examples._base import case
from vultron.wire.as2.vocab.examples.status import (
    add_status_to_case,
    add_status_to_participant,
)

#: The sender's ledger tail, which every case activity states (SYNC-18-015).
_TAIL = LedgerPosition(log_index=-1, entry_hash="0" * 64)

_CASE = case().id_
_PARTICIPANT = "https://vultron.example/cases/1/participants/vendor"


@pytest.mark.spec("VAM-08-004")
def test_a_participant_status_names_its_history_and_case():
    activity = add_status_to_participant().model_copy(
        update={"ledger_position": _TAIL}
    )
    assert activity.target == f"{_PARTICIPANT}/statuses"
    assert activity.context == _CASE
    event = extract_event(activity)
    assert event.semantic_type is (
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    )
    assert event.participant_id == _PARTICIPANT
    assert event.case_id == _CASE


@pytest.mark.spec("VAM-08-002")
def test_a_case_status_names_its_history_and_case():
    activity = add_status_to_case().model_copy(
        update={"ledger_position": _TAIL}
    )
    assert activity.target == f"{_CASE}/statuses"
    assert activity.context == _CASE
    event = extract_event(activity)
    assert event.semantic_type is MessageSemantics.ADD_CASE_STATUS_TO_CASE
    assert event.case_id == _CASE
    assert event.history_owner_id == _CASE


@pytest.mark.parametrize(
    "example", [add_status_to_case, add_status_to_participant]
)
def test_the_old_form_has_no_semantics(example):
    """A status added to the record itself, not its history, has no
    context and so matches no status pattern: there is no shim."""
    old = as_Add.model_validate(
        example().model_dump(by_alias=True, exclude={"context"})
        | {"target": _PARTICIPANT}
    )
    assert find_matching_semantics(old) not in {
        MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
    }


def test_a_participant_status_to_a_record_reads_no_participant():
    """A target that is no status history names no participant, so the
    received tree refuses the Add as incomplete."""
    activity = add_status_to_participant()
    stale = as_Add.model_validate(
        activity.model_dump(by_alias=True) | {"target": _PARTICIPANT}
    ).model_copy(update={"ledger_position": _TAIL})
    event = extract_event(stale)
    assert event.semantic_type is (
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
    )
    assert event.participant_id is None


_HISTORY = f"{_PARTICIPANT}/statuses"


@pytest.mark.parametrize(
    "target,context,reason",
    [
        (_PARTICIPANT, _CASE, "must be a status history"),
        (_HISTORY, None, "must name its one case"),
        (
            _HISTORY,
            [_CASE, "https://vultron.example/cases/2"],
            "must name its one case",
        ),
    ],
)
def test_a_participant_status_add_refuses_a_bad_shape(target, context, reason):
    from pydantic import ValidationError

    from vultron.wire.as2.vocab.activities.case_participant import (
        _AddStatusToParticipantActivity,
    )

    with pytest.raises(ValidationError, match=reason):
        make(
            _AddStatusToParticipantActivity,
            actor=_PARTICIPANT,
            object_=add_status_to_participant().object_,
            target=target,
            context=context,
        )


def test_a_case_status_add_refuses_another_cases_history():
    from pydantic import ValidationError

    from vultron.wire.as2.vocab.activities.case.content import (
        _AddStatusToCaseActivity,
    )

    with pytest.raises(ValidationError, match="extends its case's history"):
        make(
            _AddStatusToCaseActivity,
            actor=_PARTICIPANT,
            object_=add_status_to_case().object_,
            target="https://vultron.example/cases/2/statuses",
            context=_CASE,
        )
