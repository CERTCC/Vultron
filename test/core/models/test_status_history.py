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

"""The named status histories a status ``Add`` extends (ADR-0204)."""

import pytest

from vultron.core.models.status_history import (
    is_status_history_id,
    status_history_id,
    status_history_owner,
)

_PARTICIPANT = "https://example.org/cases/1/participants/vendor"


def test_a_history_is_its_owners_id_and_statuses():
    assert status_history_id(_PARTICIPANT) == f"{_PARTICIPANT}/statuses"


def test_the_owner_is_read_back_from_its_history():
    assert status_history_owner(status_history_id(_PARTICIPANT)) == (
        _PARTICIPANT
    )


@pytest.mark.parametrize(
    "ref",
    [_PARTICIPANT, "/statuses", "", None, 3],
)
def test_anything_else_is_no_history(ref):
    assert not is_status_history_id(ref)


def test_a_history_has_no_history_of_its_own():
    with pytest.raises(ValueError):
        status_history_id(f"{_PARTICIPANT}/statuses")


def test_a_history_needs_an_owner():
    with pytest.raises(ValueError):
        status_history_id("")


def test_an_id_that_is_no_history_has_no_owner():
    with pytest.raises(ValueError):
        status_history_owner(_PARTICIPANT)
