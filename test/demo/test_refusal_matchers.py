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
    RECEIVED_RUNNER_LOGGER,
    expect_no_inbox_refusals,
    expect_no_sender_refusals,
)

_LOGGER = logging.getLogger("vultron.test.refusal_matchers")

#: The received runner's logger: the one writer of a refused delivery's line.
_RUNNER = logging.getLogger(RECEIVED_RUNNER_LOGGER)


@pytest.mark.parametrize(
    "message",
    [
        "Sender 'a' is not the CASE_MANAGER for case 'c', which is 'm'"
        " — REFUSED (HP-01-006)",
        "No CASE_MANAGER is known — REFUSED (HP-01-006, PCR-03-004)",
        "No sender is entitled to send this activity to the CASE_MANAGER"
        " — REFUSED (HP-01-006, HP-01-024)",
        "Invite 'i' was never recorded here — REFUSED (EP-09-010, HP-01-006)",
        # Four reasons the demos never drive: the matcher must still fail
        # the run when the runner reports one (#5786).
        "Sender 'a' is not an active participant of case 'c', or has left it"
        " — REFUSED (HP-01-006, CM-10-004, CM-23-018)",
        "Sender 'a' may not add a status to participant record 'p': the"
        " record does not name the sender — REFUSED (RSH-08-007, HP-01-006)",
        "Sender 'a' is not the author of note 'n' (author: 'b') or not an"
        " active participant of case 'c' that has not left it — REFUSED"
        " (CM-30-001, CM-23-018, HP-01-006)",
        "Sender 'a' is not a participant of case 'c' — REFUSED (HP-01-006,"
        " DEMOMA-07-003 step 1)",
        # The same node's no-case refusal (#5786).
        "No case in this store to check sender 'a' against — REFUSED"
        " (HP-01-006, DEMOMA-07-003 step 1)",
        # The lone-CASE_OWNER refusal (#5845).  No demo drives one, so the
        # reason is pinned here rather than discovered the first time a demo
        # step sends an owner-only activity from someone else.
        "Sender 'a' is not the Case Owner of case 'c' — REFUSED (HP-01-006)",
    ],
)
def test_sender_matcher_catches_any_group_citing_hp_01_006(caplog, message):
    """A runner line whose ``REFUSED (...)`` group cites HP-01-006 fails the
    run."""
    with caplog.at_level(logging.WARNING):
        with pytest.raises(AssertionError, match="HP-01-006"):
            with expect_no_sender_refusals(caplog):
                _RUNNER.warning(
                    "Probe refused activity 'x' from 'a' at 'v': %s", message
                )


def test_sender_matcher_ignores_a_line_the_runner_did_not_write(caplog):
    """Only the runner knows the verdict, so a group citing HP-01-006 in any
    other logger's line — a node's, or the bridge's — is not a refusal
    (#6477)."""
    with caplog.at_level(logging.WARNING), expect_no_sender_refusals(caplog):
        _LOGGER.warning(
            "Sender 'a' is not the Case Owner of case 'c' — REFUSED (HP-01-006)"
        )


@pytest.mark.parametrize(
    "message",
    [
        "Invite 'i' was never recorded here — REFUSED (EP-09-010)",
        "Sender 'a' has no standing — REFUSED (HP-01-0061)",
        # The same three facts without their group, as a node logs them
        # (SL-03-003, #5786).
        "Sender 'a' is not an active participant of case 'c', or has left it",
        "Sender 'a' is not a participant of case 'c'",
        "No case in this store to check sender 'a' against",
    ],
)
def test_sender_matcher_ignores_groups_without_hp_01_006(caplog, message):
    """A refusal that does not cite HP-01-006 is not a sender refusal."""
    with caplog.at_level(logging.WARNING), expect_no_sender_refusals(caplog):
        _RUNNER.warning(
            "Probe refused activity 'x' from 'a' at 'v': %s", message
        )


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
