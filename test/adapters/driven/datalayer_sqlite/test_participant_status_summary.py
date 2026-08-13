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

"""Tests for the participant-status save/read log summary (issue #2232).

``participant_status_summary`` is the adapter's read/save observability hook —
the thing that makes a read-after-write shape problem diagnosable from container
logs without dumping full JSON.  It read only the flat wire spellings
(``rm_state``/``rmState``), so once rows became canonically core-shaped every
line reported ``vfd=None,rm=None``: the diagnostic went blank at exactly the
moment a shape migration made it most useful.
"""

from vultron.adapters.driven.datalayer_sqlite.schema import (
    _dimension_state,
    participant_status_summary,
)


class TestDimensionState:
    """``_dimension_state`` reads either persisted shape."""

    def test_reads_the_canonical_nested_shape(self):
        """Core shape (ADR-0036): ``{"rm": {"state": ...}}``."""
        status = {"rm": {"state": "RECEIVED"}}
        assert _dimension_state(status, "rm") == "RECEIVED"

    def test_reads_the_flat_wire_shape(self):
        """Legacy/wire rows must remain readable while they still exist."""
        assert _dimension_state({"rm_state": "VALID"}, "rm") == "VALID"

    def test_reads_the_camel_cased_wire_shape(self):
        assert _dimension_state({"vfdState": "Vfd"}, "vfd") == "Vfd"

    def test_prefers_the_nested_shape_when_both_are_present(self):
        """A mixed row is exactly the bug; report the canonical side."""
        status = {"rm": {"state": "ACCEPTED"}, "rm_state": "START"}
        assert _dimension_state(status, "rm") == "ACCEPTED"

    def test_falls_back_when_the_nested_dimension_has_no_state(self):
        status = {"rm": {}, "rm_state": "START"}
        assert _dimension_state(status, "rm") == "START"

    def test_returns_none_when_the_dimension_is_absent(self):
        assert _dimension_state({}, "rm") is None

    def test_non_dict_nested_value_does_not_raise(self):
        """A malformed row must degrade to the flat lookup, not explode.

        This helper runs inside a logging call; raising here would turn a
        diagnostic into an outage.
        """
        assert _dimension_state({"rm": "RECEIVED"}, "rm") is None


class TestParticipantStatusSummary:
    """The summary line must report real states for core-shaped rows."""

    def test_reports_states_for_a_core_shaped_row(self):
        data = {
            "participant_statuses": [
                {
                    "rm": {"state": "RECEIVED"},
                    "vfd": {"state": "vfd"},
                    "published": "2026-01-01T00:00:00Z",
                    "updated": None,
                }
            ]
        }
        summary = participant_status_summary(data)
        assert "n_statuses=1" in summary
        assert "rm='RECEIVED'" in summary
        assert "vfd='vfd'" in summary

    def test_reports_states_for_a_flat_wire_row(self):
        data = {
            "participant_statuses": [{"rm_state": "VALID", "vfd_state": "Vfd"}]
        }
        summary = participant_status_summary(data)
        assert "rm='VALID'" in summary
        assert "vfd='Vfd'" in summary

    def test_reports_every_entry_in_the_ladder(self):
        data = {
            "participant_statuses": [
                {"rm": {"state": "START"}},
                {"rm": {"state": "RECEIVED"}},
            ]
        }
        summary = participant_status_summary(data)
        assert "n_statuses=2" in summary
        assert "[0]" in summary and "[1]" in summary
        assert "rm='START'" in summary
        assert "rm='RECEIVED'" in summary

    def test_empty_ladder_is_reported_as_zero(self):
        assert participant_status_summary({"participant_statuses": []}) == (
            "n_statuses=0"
        )

    def test_camel_cased_status_list_key_is_accepted(self):
        data = {"participantStatuses": [{"rm": {"state": "START"}}]}
        assert "rm='START'" in participant_status_summary(data)

    def test_non_participant_row_returns_empty_string(self):
        """Callers branch on ``""`` to skip the log line cheaply."""
        assert participant_status_summary({"id_": "urn:uuid:x"}) == ""
        assert participant_status_summary(None) == ""
        assert participant_status_summary("not-a-row") == ""

    def test_non_dict_status_entry_is_reported_by_type(self):
        summary = participant_status_summary({"participant_statuses": ["x"]})
        assert "[0]<str>" in summary
