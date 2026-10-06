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
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from vultron.core.models.replication_state import VultronReplicationState

_BASE = {"case_id": "https://example.org/case", "peer_id": "https://x/peer"}
_WHEN = datetime(2026, 10, 1, tzinfo=UTC)

#: field name -> a non-default value for it.
_VALUES: dict[str, Any] = {
    "last_acknowledged_hash": "abc123",
    "updated_at": _WHEN,
    "join_backfill_target_index": 4,
    "join_backfill_last_sent_index": 4,
    "last_replayed_from_hash": "def456",
    "last_replayed_at": _WHEN,
    "join_backfill_complete": False,
    "embargo_paused_from_index": 7,
}

#: The backfill fields validate against one another, so these are stated with
#: a companion that keeps the pair consistent (by field name, which both
#: spellings of the field under test must coexist with).
_COMPANION: dict[str, dict[str, Any]] = {
    "join_backfill_target_index": {"join_backfill_complete": False},
    "join_backfill_last_sent_index": {"join_backfill_target_index": 4},
}


def test_every_aliased_field_is_covered() -> None:
    aliased = {
        name
        for name, info in VultronReplicationState.model_fields.items()
        if isinstance(info.validation_alias, str)
        and name not in {"id_", "type_"}
    }
    assert aliased == set(_VALUES)


@pytest.mark.spec("ARCH-12-003")
@pytest.mark.parametrize("field", sorted(_VALUES))
def test_alias_and_name_spellings_both_read(field: str) -> None:
    alias = VultronReplicationState.model_fields[field].validation_alias
    assert isinstance(alias, str)
    by_alias = VultronReplicationState.model_validate(
        {**_BASE, **_COMPANION.get(field, {}), alias: _VALUES[field]}
    )
    by_name = VultronReplicationState.model_validate(
        {**_BASE, **_COMPANION.get(field, {}), field: _VALUES[field]}
    )
    assert getattr(by_alias, field) == _VALUES[field]
    assert getattr(by_name, field) == _VALUES[field]
