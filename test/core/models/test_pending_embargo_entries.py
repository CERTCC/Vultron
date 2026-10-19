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

"""The stored plan of an embargo act's owed entries (CLP-07-015)."""

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.pending_embargo_entries import (
    PendingEmbargoEntries,
    PlannedEmbargoEntryRecord,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)

_BASE = "https://example.org"
_EMBARGO = f"{_BASE}/embargoes/e1"


def _row() -> ConsentRowChange:
    return ConsentRowChange(
        verb=ConsentRowVerb.UPDATE,
        row=EmbargoConsent(
            embargo_id=_EMBARGO,
            state=EmbargoConsentState.DECLINED,
            attributed_to=f"{_BASE}/actors/a",
        ),
    )


def _committing(**overrides: object) -> dict[str, object]:
    return {
        "change": _row(),
        "activity_id": f"{_BASE}/activities/row",
        "event_type": "update_embargo_consent",
        "activity_json": '{"id": "x"}',
        **overrides,
    }


@pytest.mark.parametrize(
    "missing", ["activity_id", "event_type", "activity_json"]
)
def test_an_entry_with_a_commit_names_its_whole_activity(missing: str):
    with pytest.raises(ValidationError, match="names its activity id"):
        PlannedEmbargoEntryRecord.model_validate(
            _committing(**{missing: None})
        )


def test_an_entry_with_no_commit_must_carry_a_change():
    with pytest.raises(ValidationError, match="must carry a change"):
        PlannedEmbargoEntryRecord()


def test_an_entry_carried_by_the_acts_own_has_no_commit():
    entry = PlannedEmbargoEntryRecord(change=_row())
    assert entry.commits is False
    assert PlannedEmbargoEntryRecord.model_validate(_committing()).commits


def test_a_plan_owes_at_least_one_entry():
    with pytest.raises(ValidationError):
        PendingEmbargoEntries(
            case_id=f"{_BASE}/cases/c",
            act_id=f"{_BASE}/activities/act",
            author_id=f"{_BASE}/actors/m",
            entries=[],
        )


def test_the_plan_id_derives_from_the_case_and_the_act():
    plan = PendingEmbargoEntries(
        case_id=f"{_BASE}/cases/c",
        act_id=f"{_BASE}/activities/act",
        author_id=f"{_BASE}/actors/m",
        entries=[PlannedEmbargoEntryRecord(change=_row())],
    )
    assert plan.id_ == PendingEmbargoEntries.build_id(
        f"{_BASE}/cases/c", f"{_BASE}/activities/act"
    )


def test_a_stored_plan_reads_back_unchanged():
    """Every change kind and the sealed body survive the store (ADR-0146)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=f"{_BASE}/actors/m")
    plan = PendingEmbargoEntries(
        case_id=f"{_BASE}/cases/c",
        act_id=f"{_BASE}/activities/act",
        act_event_type="activate_embargo_on_case",
        author_id=f"{_BASE}/actors/m",
        entries=[
            PlannedEmbargoEntryRecord.model_validate(
                _committing(activity_json='{"id": "x", "object": {"id": 1}}')
            ),
            PlannedEmbargoEntryRecord(
                change=RegisterStep(
                    kind=RegisterStepKind.REJECT, embargo=_EMBARGO
                )
            ),
        ],
    )

    dl.save(plan)

    assert dl.read(plan.id_) == plan
