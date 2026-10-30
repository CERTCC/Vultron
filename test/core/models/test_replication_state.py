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

"""``VultronReplicationState`` reads each aliased field under both spellings.

Its stored fields carry camelCase aliases; under ``extra="forbid"`` on
``CoreRecord`` (#4186) a key that is neither spelling is refused, so each
alias is pinned: alias key in, field value out, and the same for the name.
The retired join-backfill fields are refused by name (#5074).
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState

_BASE = {"case_id": "https://example.org/case", "peer_id": "https://x/peer"}
_WHEN = datetime(2026, 10, 1, tzinfo=UTC)

#: field name -> a non-default value for it.
_VALUES: dict[str, Any] = {
    "last_acknowledged_hash": "abc123",
    "last_acknowledged_published": _WHEN,
    "updated_at": _WHEN,
    "last_replayed_from_hash": "def456",
    "last_replayed_at": _WHEN,
    "replays_at_position": 3,
    "embargo_paused_from_index": 7,
    "last_reseeded_at": _WHEN,
    "last_reseed_position": LedgerPosition(log_index=2, entry_hash="f" * 64),
}


def test_every_aliased_field_is_covered() -> None:
    aliased = {
        name
        for name, info in VultronReplicationState.model_fields.items()
        if isinstance(info.validation_alias, str)
        and name not in {"id_", "type_"}
    }
    assert aliased == set(_VALUES)


@pytest.mark.spec("ARCH-12-013")
@pytest.mark.parametrize("field", sorted(_VALUES))
def test_alias_and_name_spellings_both_read(field: str) -> None:
    alias = VultronReplicationState.model_fields[field].validation_alias
    assert isinstance(alias, str)
    by_alias = VultronReplicationState.model_validate(
        {**_BASE, alias: _VALUES[field]}
    )
    by_name = VultronReplicationState.model_validate(
        {**_BASE, field: _VALUES[field]}
    )
    assert getattr(by_alias, field) == _VALUES[field]
    assert getattr(by_name, field) == _VALUES[field]


_RETIRED = [
    "join_backfill_target_index",
    "join_backfill_last_sent_index",
    "join_backfill_complete",
]


@pytest.mark.spec("CM-17-012")
@pytest.mark.parametrize(
    "old",
    [key for name in _RETIRED for key in (name, to_camel(name))],
)
def test_a_row_with_a_retired_join_backfill_key_is_refused(old: str) -> None:
    """A stored row from before #5074 fails to load naming the reset.

    The join backfill keeps no state, so the three fields are deleted with no
    replacement (notes/datalayer-design.md § "Retiring a Stored Field").
    """
    with pytest.raises(ValidationError, match="must be reset") as excinfo:
        VultronReplicationState.model_validate({**_BASE, old: 0})

    message = str(excinfo.value)
    assert repr(old) in message
    assert "#5074" in message
