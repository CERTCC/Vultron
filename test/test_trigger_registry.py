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

"""The trigger registry's public API and row validation (ADR-0110).

``vultron.trigger_registry`` is a data table with a lookup: ``entries()``
enumerates, ``lookup_entry(verb)`` resolves a verb, and
``index_by_request_model`` keys rows by request model for the dispatcher.  A
row validates itself at construction so a table that would misroute fails at
import (TRIG-12-004): a verb that is not a path segment, a request model that
binds a different result than the row names, a ``bt_backed`` flag that
contradicts the class, or a row citing no requirement.
"""

import dataclasses
from typing import Any

import pytest

from vultron.core.models.use_case_result import (
    ActivityResult,
    RoleOfferResult,
    StatusResult,
)
from vultron.core.use_cases.triggers.actor import (
    SvcOfferCaseParticipantRoleUseCase,
)
from vultron.core.use_cases.triggers.case import (
    SvcAddParticipantStatusUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AddParticipantStatusTriggerRequest,
    EngageCaseTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
)
from vultron.errors import TriggerRegistryError, VultronApiHandlerNotFoundError
from vultron.trigger_registry import (
    TRIGGER_REGISTRY,
    TriggerEntry,
    TriggerExposure,
    entries,
    index_by_request_model,
    lookup_entry,
)

_ENGAGE_ROW = TriggerEntry(
    verb="engage-case",
    request_model=EngageCaseTriggerRequest,
    use_case_class=SvcEngageCaseUseCase,
    result_type=ActivityResult,
    exposure=TriggerExposure.GENERAL_PURPOSE,
    bt_backed=True,
    spec_ids=("TRIG-02-004",),
)


def _engage_row(**overrides: Any) -> TriggerEntry:
    """A valid row with *overrides* applied — re-validated on construction."""
    return dataclasses.replace(_ENGAGE_ROW, **overrides)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@pytest.mark.spec("TRIG-12-004")
def test_entries_is_the_assembled_immutable_table() -> None:
    rows = entries()
    assert rows is TRIGGER_REGISTRY
    assert isinstance(rows, tuple)
    assert len(rows) > 0


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.parametrize("row", entries(), ids=lambda r: r.verb)
def test_lookup_entry_returns_the_enumerated_row(row: TriggerEntry) -> None:
    assert lookup_entry(row.verb) is row


def test_lookup_entry_unknown_verb_is_a_caller_fault() -> None:
    with pytest.raises(VultronApiHandlerNotFoundError, match="no-such-verb"):
        lookup_entry("no-such-verb")


@pytest.mark.spec("TRIG-08-002")
def test_exposure_values() -> None:
    assert TriggerExposure.GENERAL_PURPOSE == "general-purpose"
    assert TriggerExposure.DEMO_ONLY == "demo-only"
    assert set(TriggerExposure) == {
        TriggerExposure.GENERAL_PURPOSE,
        TriggerExposure.DEMO_ONLY,
    }


# ---------------------------------------------------------------------------
# Row validation
# ---------------------------------------------------------------------------


def test_row_is_frozen() -> None:
    row = _engage_row()
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.verb = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "verb", ["Engage-Case", "engage_case", "engage case", ""]
)
def test_row_rejects_a_verb_that_is_not_a_path_segment(verb: str) -> None:
    with pytest.raises(TriggerRegistryError, match="kebab-case"):
        _engage_row(verb=verb)


@pytest.mark.spec("UCORG-05-006")
def test_row_rejects_a_result_type_the_request_does_not_bind() -> None:
    with pytest.raises(TriggerRegistryError, match="binds ActivityResult"):
        _engage_row(result_type=StatusResult)


@pytest.mark.spec("TRIG-12-004")
def test_row_rejects_a_bt_backed_flag_that_contradicts_the_class() -> None:
    with pytest.raises(TriggerRegistryError, match="bt_backed=False"):
        _engage_row(bt_backed=False)
    with pytest.raises(TriggerRegistryError, match="bt_backed=True"):
        TriggerEntry(
            verb="offer-case-participant-role",
            request_model=OfferCaseParticipantRoleTriggerRequest,
            use_case_class=SvcOfferCaseParticipantRoleUseCase,
            result_type=RoleOfferResult,
            exposure=TriggerExposure.GENERAL_PURPOSE,
            bt_backed=True,
            spec_ids=("TRIG-02-007",),
        )


def test_row_rejects_empty_spec_ids() -> None:
    with pytest.raises(TriggerRegistryError, match="cites no spec"):
        _engage_row(spec_ids=())


# ---------------------------------------------------------------------------
# Request-model index
# ---------------------------------------------------------------------------


def _status_row(verb: str) -> TriggerEntry:
    return TriggerEntry(
        verb=verb,
        request_model=AddParticipantStatusTriggerRequest,
        use_case_class=SvcAddParticipantStatusUseCase,
        result_type=StatusResult,
        exposure=TriggerExposure.DEMO_ONLY,
        bt_backed=True,
        spec_ids=("TRIG-02-003",),
    )


@pytest.mark.spec("TRIG-12-004")
def test_index_keys_rows_by_request_model() -> None:
    engage = _engage_row()
    index = index_by_request_model([engage, _status_row("notify-fix-ready")])
    assert index[EngageCaseTriggerRequest] is engage
    assert index[AddParticipantStatusTriggerRequest].verb == "notify-fix-ready"


@pytest.mark.spec("TRIG-12-004")
def test_index_accepts_rows_that_share_a_model_and_agree() -> None:
    index = index_by_request_model(
        [_status_row("notify-fix-ready"), _status_row("notify-published")]
    )
    assert index[AddParticipantStatusTriggerRequest].use_case_class is (
        SvcAddParticipantStatusUseCase
    )


@pytest.mark.spec("TRIG-12-004")
def test_index_refuses_rows_that_share_a_model_and_disagree() -> None:
    from vultron.core.use_cases.triggers.case import (
        SvcAddOnBehalfStatusUseCase,
    )

    disagreeing = dataclasses.replace(
        _status_row("notify-published"),
        use_case_class=SvcAddOnBehalfStatusUseCase,
    )
    with pytest.raises(TriggerRegistryError, match="disagree"):
        index_by_request_model([_status_row("notify-fix-ready"), disagreeing])


@pytest.mark.spec("TRIG-12-004")
def test_the_assembled_table_indexes_cleanly() -> None:
    """Import already ran this check; it is repeated here so a failure names
    the test rather than the collection phase."""
    index = index_by_request_model(entries())
    assert set(index) == {row.request_model for row in entries()}
