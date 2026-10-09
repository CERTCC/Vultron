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

"""The vocabulary examples do not depend on the wall clock (#4095, TB-06-006).

The example tests compare an activity's embedded object against a second,
independent call to the same builder. That holds only when the builder reads
no clock: a ``start_time`` truncated to the minute, or a ``published`` stamp at
second precision, differs between two calls that straddle a tick.

Each test runs under ``straddling_clock`` (see ``conftest.py``), which moves
the clock past a minute boundary between consecutive reads.
"""

from collections.abc import Callable

import pytest

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)


@pytest.mark.parametrize(
    "builder",
    [
        examples.propose_embargo,
        examples.activate_embargo,
        examples.reject_embargo_proposal,
        examples.announce_embargo,
    ],
    ids=lambda f: f.__name__,
)
def test_embargo_examples_equal_across_minute_boundary(
    straddling_clock: type, builder: Callable[[], as_TransitiveActivity]
) -> None:
    activity = builder()
    expected = examples.embargo_event()

    assert activity.object_ == expected


@pytest.mark.parametrize(
    "builder",
    [
        examples.embargo_event,
        examples.note,
        examples.case_participant,
        examples.invite_to_case,
        examples.rm_invite_to_case,
        examples.vendor_profile,
    ],
    ids=lambda f: f.__name__,
)
def test_examples_equal_across_second_boundary(
    straddling_clock: type, builder: Callable[[], object]
) -> None:
    assert builder() == builder()


def test_create_note_carries_an_equal_note_across_second_boundary(
    straddling_clock: type,
) -> None:
    activity = examples.create_note()

    assert activity.object_ == examples.note()
