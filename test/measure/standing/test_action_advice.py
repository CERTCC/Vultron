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


"""The CVD actions a participant's case state makes possible (#6515).

They change no state, so the standing record lists them as advice with no
number, each naming its participant (AC-6 of #6368).
"""

import json

from test.measure.history.builders import (
    OWNER,
    VENDOR,
    Ledger,
    publish,
    seat_vendor,
)
from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.cs import CS
from vultron.core.states.cs_actions import cs_actions
from vultron.measure.standing import (
    ActionAdvice,
    StandingGap,
    StandingRecord,
    case_standing,
)


def _vendor_case() -> Ledger:
    """The standard genesis, and a vendor aware at RM Received."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    return ledger


def _actions_of(record: StandingRecord, participant: str) -> list[Actions]:
    return [
        a.action for a in record.action_advice if a.participant == participant
    ]


def test_a_vendor_before_attacks_is_advised_to_monitor_for_them():
    record = case_standing(_vendor_case().case_ledger())
    actions = _actions_of(record, VENDOR)
    assert Actions.MONITOR_FOR_ATTACKS in actions
    assert Actions.MONITOR_FOR_ADDITIONAL_ATTACKS not in actions
    assert actions == list(cs_actions(CS.Vfdpxa))


def test_once_attacks_are_observed_the_advice_moves_on():
    ledger = _vendor_case()
    publish(ledger, "pxA")
    record = case_standing(ledger.case_ledger())
    actions = _actions_of(record, VENDOR)
    assert Actions.MONITOR_FOR_ATTACKS not in actions
    assert Actions.MONITOR_FOR_ADDITIONAL_ATTACKS in actions
    assert actions == list(cs_actions(CS.VfdpxA))


def test_a_participant_with_no_case_state_gets_no_action_advice():
    record = case_standing(_vendor_case().case_ledger())
    owner = record.for_participant(OWNER)
    assert owner is not None and owner.case_state is None
    assert _actions_of(record, OWNER) == []


def test_action_advice_follows_participant_order():
    record = case_standing(_vendor_case().case_ledger())
    order = [p.participant for p in record.participants]
    named = [a.participant for a in record.action_advice]
    assert named == sorted(named, key=order.index)


def test_action_advice_carries_no_number_and_serializes_by_name():
    record = case_standing(_vendor_case().case_ledger())
    data = json.loads(record.model_dump_json())
    entries = [e for e in data["action_advice"] if e["participant"] == VENDOR]
    assert {"participant": VENDOR, "action": "MONITOR_FOR_ATTACKS"} in entries
    assert all(set(e) == {"participant", "action"} for e in entries)
    assert set(ActionAdvice.model_fields) == {"participant", "action"}


def test_a_record_with_a_gap_has_no_action_advice():
    gap = StandingGap(missing_log_indices=[3])
    record = StandingRecord(case_id="c", end_confirmed=False, gap=gap)
    assert record.action_advice == ()
