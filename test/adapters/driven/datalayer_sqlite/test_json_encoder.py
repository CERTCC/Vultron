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

"""The SQLite JSON encoder writes times in the fixed form (CS-13-007)."""

import json
from datetime import UTC, date, datetime

import pytest

from vultron.adapters.driven.datalayer_sqlite.engine import json_serializer


@pytest.mark.spec("CS-13-007")
def test_a_whole_second_datetime_is_stored_with_six_digits() -> None:
    stored = json_serializer({"at": datetime(2026, 10, 30, 12, 0, tzinfo=UTC)})
    assert json.loads(stored) == {"at": "2026-10-30T12:00:00.000000+00:00"}


def test_a_date_is_stored_as_its_iso_date() -> None:
    assert json.loads(json_serializer({"on": date(2026, 10, 30)})) == {
        "on": "2026-10-30"
    }


def test_an_unknown_type_is_refused() -> None:
    with pytest.raises(TypeError, match="not JSON serializable"):
        json_serializer({"x": object()})
