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
"""Planned behaviour for the case split (ADR-0125, CM-32, VP-10).

Strict-``xfail`` tests for protocol requirements written before the code that
satisfies them exists; see ``notes/spec-authoring-rules.md`` § "Never Raise the
Ceiling — Use a Strict ``xfail``".

Two placeholders stand in for the behaviour: a message type for the split
proposal (CM-32-001 through CM-32-012, CM-32-016), and one for the
split-family embargo notice (CM-32-013 through CM-32-015, VP-10-002,
VP-10-003). Each probe names only split vocabulary, so a case-merge build,
which may use ``sibling_cases``, cannot XPASS them. When either lands,
its tests XPASS, ``strict=True`` fails the build, and the builder replaces each
placeholder with the behavioural check the requirement's ``verification:``
names. That promotion is the point: this module is a ratchet, not a test of
the split.
"""

import pytest

from vultron.core.models.events.base import MessageSemantics

_SPLIT_BUILD = "Tracked by #4242 (source #4241)."


def _has_semantics(*fragments: str) -> bool:
    """Return whether any ``MessageSemantics`` member name holds a fragment."""
    return any(
        fragment in member.name
        for member in MessageSemantics
        for fragment in fragments
    )


def _split_proposal_exists() -> bool:
    return _has_semantics("SPLIT_CASE", "CHILD_CASE")


def _family_notice_exists() -> bool:
    return _has_semantics("SPLIT_FAMILY")


@pytest.mark.spec("CM-32-001")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-001: no Owner-only split proposal exists yet. {_SPLIT_BUILD}",
)
def test_only_the_parent_owner_may_request_a_split():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-002: no split proposal answer exists yet. {_SPLIT_BUILD}",
)
def test_a_split_proposal_is_answered_like_any_case_proposal():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-003: no child case is created yet. {_SPLIT_BUILD}",
)
def test_the_parent_case_manager_creates_and_manages_the_child():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-004")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-004: nothing writes parent_cases yet. {_SPLIT_BUILD}",
)
def test_the_child_names_its_parent_by_id():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-005: nothing writes child_cases yet. {_SPLIT_BUILD}",
)
def test_the_parent_ledger_records_the_child_after_it_exists():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-006")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-006: no split family is read yet. {_SPLIT_BUILD}",
)
def test_siblings_are_read_from_the_parent():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-007")
@pytest.mark.spec("VP-10-005")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-007: no child inherits an embargo yet. {_SPLIT_BUILD}",
)
def test_the_child_inherits_the_active_embargo_terms_as_a_new_embargo():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-008")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-008: no child case is created yet. {_SPLIT_BUILD}",
)
def test_a_parent_without_an_active_embargo_gives_the_child_none():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-009")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-009: no child case is created yet. {_SPLIT_BUILD}",
)
def test_the_child_copies_nothing_else_from_the_parent():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-010")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-010: no split proposal exists yet. {_SPLIT_BUILD}",
)
def test_the_child_report_is_new_and_written_by_the_splitter():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-011")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-011: no child initialization exists yet. {_SPLIT_BUILD}",
)
def test_the_child_seats_only_its_case_manager_and_owner():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-012")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-012: no child case is created yet. {_SPLIT_BUILD}",
)
def test_a_child_participant_never_reaches_the_parent():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-013")
@pytest.mark.spec("VP-10-002")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-013: no split-family embargo notice exists yet. {_SPLIT_BUILD}",
)
def test_an_earlier_child_end_time_is_announced_to_the_family_first():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-014")
@pytest.mark.spec("VP-10-003")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-014: no split-family embargo notice exists yet. {_SPLIT_BUILD}",
)
def test_an_agreed_embargo_change_is_announced_to_the_family():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-015")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-015: no split-family embargo notice exists yet. {_SPLIT_BUILD}",
)
def test_a_family_notice_is_committed_and_changes_no_embargo():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-016")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-016: no split family exists to hold at one CASE_MANAGER yet. {_SPLIT_BUILD}",
)
def test_a_family_member_case_manager_role_cannot_be_delegated_away():
    assert _split_proposal_exists()
