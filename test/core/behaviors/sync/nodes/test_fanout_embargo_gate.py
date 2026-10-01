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
"""Ledger fan-out applies the CM-10-004 embargo content gate (CM-10-005).

Strict ``xfail`` until the gate lands: today the fan-out
collectors filter on RM-closed only, so a participant that has not accepted
the active embargo receives every committed entry.
"""

import py_trees
import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectLogEntryRecipientsNode,
    CollectNonClosedLogEntryRecipientsNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/fanout-gate"
MANAGER_ID = "https://example.org/actors/coordinator"
SIGNATORY_ID = "https://example.org/actors/vendor"
NON_SIGNATORY_ID = "https://example.org/actors/finder"
EMBARGO_ID = "https://example.org/embargoes/fanout-gate"


def _seed_embargoed_case(bt_scenario: BTTestScenario) -> None:
    """A case under an active embargo that one participant has not accepted."""
    dl = bt_scenario.dl
    dl.create(
        as_EmbargoEvent(
            id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
        )
    )
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        attributed_to=MANAGER_ID,
        active_embargo=EMBARGO_ID,
    )
    for actor_id, accepted in (
        (MANAGER_ID, [EMBARGO_ID]),
        (SIGNATORY_ID, [EMBARGO_ID]),
        (NON_SIGNATORY_ID, []),
    ):
        participant = as_CaseParticipant(
            id_=f"{actor_id}/participant",
            attributed_to=actor_id,
            context=CASE_ID,
            accepted_embargo_ids=accepted,
        )
        dl.create(participant)
        case.actor_participant_index[actor_id] = participant.id_
    dl.create(case)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-10-005: ledger fan-out does not yet apply the CM-10-004 embargo"
        " content gate. Source: #3917."
    ),
)
@pytest.mark.spec("CM-10-005")
@pytest.mark.executes_as(MANAGER_ID)
@pytest.mark.parametrize(
    "node_cls",
    [CollectLogEntryRecipientsNode, CollectNonClosedLogEntryRecipientsNode],
)
def test_fanout_withholds_entries_from_non_signatory(
    bt_scenario: BTTestScenario, node_cls: type
) -> None:
    _seed_embargoed_case(bt_scenario)
    entry = CaseLedgerEntry(
        case_id=CASE_ID,
        log_object_id="https://example.org/activities/act-001",
        event_type="add_note_to_case",
    )

    result = bt_scenario.run(
        node_cls(case_id=CASE_ID), actor_id=MANAGER_ID, log_entry=entry
    )

    bt_scenario.assert_success(result)
    recipients = py_trees.blackboard.Blackboard.storage["/fanout_recipients"]
    assert SIGNATORY_ID in recipients
    assert NON_SIGNATORY_ID not in recipients
