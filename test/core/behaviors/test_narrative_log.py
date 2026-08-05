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

"""Unit tests for the narrative INFO log helpers (SL-04-001, SL-04-006)."""

import logging

import pytest

from vultron.core.behaviors.narrative_log import (
    NO_CHANGE_LABEL,
    REGRESSION_LABEL,
    cs_event_label,
    log_case_engagement,
    log_cs_transition,
    log_em_transition,
    log_invite_received,
    log_rm_transition,
)
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM

ACTOR = "https://example.org/actors/vendor"
CASE = "https://example.org/cases/case-001"

logger = logging.getLogger("test.narrative_log")


class TestCsEventLabel:
    """cs_event_label() names the sub-dimension(s) that advanced."""

    @pytest.mark.parametrize(
        "before,after,expected",
        [
            (CS_vfd.vfd, CS_vfd.Vfd, "vendor aware"),
            (CS_vfd.Vfd, CS_vfd.VFd, "fix ready"),
            (CS_vfd.VFd, CS_vfd.VFD, "fix deployed"),
            (CS_pxa.pxa, CS_pxa.Pxa, "publicly known"),
            (CS_pxa.Pxa, CS_pxa.PXa, "exploit public"),
            (CS_pxa.Pxa, CS_pxa.PxA, "attacks observed"),
        ],
    )
    def test_single_dimension_label(self, before, after, expected):
        assert cs_event_label(before, after) == expected

    def test_multi_dimension_label_joins_all_events(self):
        """A multi-step transition names every sub-dimension that advanced."""
        assert (
            cs_event_label(CS_pxa.pxa, CS_pxa.PXa)
            == "publicly known, exploit public"
        )

    def test_no_change_label(self):
        assert cs_event_label(CS_vfd.Vfd, CS_vfd.Vfd) == NO_CHANGE_LABEL

    @pytest.mark.parametrize(
        "before,after",
        [
            (CS_vfd.VFd, CS_vfd.vfd),
            (CS_vfd.VFD, CS_vfd.VFd),
            (CS_pxa.Pxa, CS_pxa.pxa),
        ],
    )
    def test_backward_move_is_labelled_a_regression(self, before, after):
        """CS events are monotonic, so a backward move is an anomaly.

        Without this branch the label fell through to "no change", producing a
        line that simultaneously claimed a transition and denied it.
        """
        assert cs_event_label(before, after) == REGRESSION_LABEL

    def test_mixed_dimensions_raise_type_error(self):
        """A VFD/PXA mix has non-comparable fields — fail loudly, not silently.

        Previously this raised an opaque ``AttributeError`` from inside the
        comparison loop.
        """
        with pytest.raises(TypeError, match="same CS dimension"):
            cs_event_label(CS_vfd.vfd, CS_pxa.Pxa)


class TestLogCsTransition:
    """log_cs_transition() emits the SL-04-006 CS template at INFO."""

    def test_vfd_transition_logged_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_cs_transition(logger, ACTOR, CASE, CS_vfd.Vfd, CS_vfd.VFd)

        assert (
            f"Actor '{ACTOR}' CS: Vfd → VFd (fix ready) for case '{CASE}'"
            in caplog.text
        )
        assert caplog.records[0].levelno == logging.INFO

    def test_pxa_transition_logged_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_cs_transition(logger, ACTOR, CASE, CS_pxa.pxa, CS_pxa.Pxa)

        assert (
            f"Actor '{ACTOR}' CS: pxa → Pxa (publicly known)"
            f" for case '{CASE}'" in caplog.text
        )

    def test_no_op_transition_emits_nothing(self, caplog):
        """An unchanged CS dimension is not a protocol event (SL-04-007)."""
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_cs_transition(logger, ACTOR, CASE, CS_vfd.Vfd, CS_vfd.Vfd)

        assert caplog.records == []

    def test_backward_move_logged_at_warning_not_info(self, caplog):
        """A regression is an anomaly to investigate, not a case milestone."""
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            log_cs_transition(logger, ACTOR, CASE, CS_vfd.VFd, CS_vfd.vfd)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING
        assert REGRESSION_LABEL in caplog.text


class TestLogRmTransition:
    """log_rm_transition() emits the SL-04-006 RM template at INFO."""

    def test_transition_logged_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_rm_transition(logger, ACTOR, CASE, RM.VALID, RM.ACCEPTED)

        assert (
            f"Actor '{ACTOR}' RM: VALID → ACCEPTED for case '{CASE}'"
            in caplog.text
        )
        assert caplog.records[0].levelno == logging.INFO

    def test_no_op_transition_emits_nothing(self, caplog):
        """Re-asserting the current RM state is bookkeeping (SL-04-007)."""
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_rm_transition(logger, ACTOR, CASE, RM.ACCEPTED, RM.ACCEPTED)

        assert caplog.records == []


class TestLogEmTransition:
    """log_em_transition() emits the SL-04-006 embargo template at INFO."""

    def test_proposed_to_active_logged_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_em_transition(logger, ACTOR, CASE, EM.PROPOSED, EM.ACTIVE)

        assert (
            f"Actor '{ACTOR}' embargo PROPOSED → ACTIVE for case '{CASE}'"
            in caplog.text
        )
        assert caplog.records[0].levelno == logging.INFO

    def test_active_to_exited_logged_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_em_transition(logger, ACTOR, CASE, EM.ACTIVE, EM.EXITED)

        assert (
            f"Actor '{ACTOR}' embargo ACTIVE → EXITED for case '{CASE}'"
            in caplog.text
        )

    def test_no_op_transition_emits_nothing(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_em_transition(logger, ACTOR, CASE, EM.ACTIVE, EM.ACTIVE)

        assert caplog.records == []


class TestOtherNarrativeHelpers:
    """Engagement and invite-receipt templates (SL-04-006)."""

    def test_case_engagement_logged_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_case_engagement(logger, ACTOR, CASE, RM.VALID, RM.ACCEPTED)

        assert (
            f"Actor '{ACTOR}' engaged case '{CASE}' (RM VALID → ACCEPTED)"
            in caplog.text
        )
        assert caplog.records[0].levelno == logging.INFO

    def test_invite_received_logged_at_info(self, caplog):
        sender = "https://example.org/actors/coordinator"
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_invite_received(logger, ACTOR, CASE, sender)

        assert (
            f"Actor '{ACTOR}' received case invite for '{CASE}'"
            f" from '{sender}'" in caplog.text
        )
        assert caplog.records[0].levelno == logging.INFO

    def test_engagement_no_op_emits_nothing(self, caplog):
        """Re-engaging an already-engaged case did not engage it.

        ``update_participant_rm_state`` returns ``True`` on the idempotent
        path, so the BT succeeds and ``_handle_result`` still runs — the guard
        has to live here.
        """
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_case_engagement(logger, ACTOR, CASE, RM.ACCEPTED, RM.ACCEPTED)

        assert caplog.records == []
