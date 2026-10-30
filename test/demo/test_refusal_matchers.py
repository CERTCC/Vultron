#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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


"""The demo tests' refusal matchers catch every refusal they name (#5438)."""

import logging

import pytest

from test.demo._helpers import (
    expect_no_inbox_refusals,
    expect_no_sender_refusals,
)

_LOGGER = logging.getLogger("vultron.test.refusal_matchers")


@pytest.mark.parametrize(
    "message",
    [
        "Sender 'a' is not the CASE_MANAGER for case 'c' — REFUSED (HP-01-006)",
        "No CASE_MANAGER is known — REFUSED (HP-01-006, PCR-03-004)",
        "No sender is entitled to send this activity to the CASE_MANAGER"
        " — REFUSED (HP-01-006, HP-01-024)",
        "Invite 'i' was never recorded here — REFUSED (EP-09-010, HP-01-006)",
    ],
)
def test_sender_matcher_catches_any_group_citing_hp_01_006(caplog, message):
    """A ``REFUSED (...)`` group citing HP-01-006 anywhere fails the run."""
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AssertionError, match="HP-01-006"):
            with expect_no_sender_refusals(caplog):
                _LOGGER.warning(message)


@pytest.mark.parametrize(
    "message",
    [
        "Invite 'i' was never recorded here — REFUSED (EP-09-010)",
        "Sender 'a' has no standing — REFUSED (HP-01-0061)",
    ],
)
def test_sender_matcher_ignores_groups_without_hp_01_006(caplog, message):
    """A refusal that does not cite HP-01-006 is not a sender refusal."""
    with caplog.at_level(logging.WARNING), expect_no_sender_refusals(caplog):
        _LOGGER.warning(message)


def test_inbox_matcher_catches_a_rejected_inbox_activity(caplog):
    """The queue drain's rejected-outcome line fails the run, any cause."""
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AssertionError, match="inbox refused"):
            with expect_no_inbox_refusals(caplog):
                _LOGGER.warning(
                    "Inbox activity rejected (actor_id=v activity_id=a"
                    " context_id=None replayed=False): not the CASE_MANAGER"
                    " of case 'c'"
                )


def test_inbox_matcher_ignores_an_unhandled_inbox_activity(caplog):
    """An unhandled activity is not a refusal (UCORG-05-013)."""
    with caplog.at_level(logging.WARNING), expect_no_inbox_refusals(caplog):
        _LOGGER.warning(
            "Inbox activity not handled (actor_id=v activity_id=a"
            " context_id=None replayed=False): no use case"
        )
