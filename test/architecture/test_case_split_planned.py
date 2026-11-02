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
satisfies them exists; see ``notes/spec-authoring-rules.md`` § "Use a
Strict ``xfail`` for Not-Yet-Implemented Specs".

Two placeholders stand in for the behaviour: a message type for the split
proposal (CM-32-001 through CM-32-012, CM-32-016 and their split-off
children CM-32-017 through CM-32-039 and CM-32-045), and one for the
split-family embargo notice (CM-32-013 through CM-32-015, CM-32-040 through
CM-32-044, VP-10-002, VP-10-003). CM-32-025 rules on a case merge, so its probe
names merge vocabulary instead. Each probe names only split vocabulary, so a case-merge build,
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


def _case_merge_exists() -> bool:
    return _has_semantics("MERGE_CASE")


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


@pytest.mark.spec("CM-32-017")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-017: no Owner-only split proposal exists yet. {_SPLIT_BUILD}"
    ),
)
def test_a_split_proposal_from_a_non_owner_is_refused():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-018")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-018: no split proposal answer exists yet. {_SPLIT_BUILD}",
)
def test_a_redelivered_split_proposal_creates_no_second_child():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-019")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-019: no child case is created yet. {_SPLIT_BUILD}",
)
def test_the_parent_case_manager_manages_the_child():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-020")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-020: no child case is created yet. {_SPLIT_BUILD}",
)
def test_the_child_is_attributed_to_the_splitter():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-021")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-021: no child case is created yet. {_SPLIT_BUILD}",
)
def test_the_child_genesis_hash_is_its_own():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-022")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-022: nothing writes the split links yet. {_SPLIT_BUILD}",
)
def test_split_cross_references_are_case_ids():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-023")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-023: nothing writes child_cases yet. {_SPLIT_BUILD}",
)
def test_a_parent_replica_takes_the_child_link_from_the_ledger():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-024")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-024: no child case is created yet. {_SPLIT_BUILD}",
)
def test_a_split_writes_no_sibling_cases():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-025")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-025: no case merge exists yet. {_SPLIT_BUILD}",
)
def test_a_merge_records_no_merged_case_in_child_cases():
    assert _case_merge_exists()


@pytest.mark.spec("CM-32-026")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-026: no child inherits an embargo yet. {_SPLIT_BUILD}",
)
def test_the_owner_agrees_to_the_child_embargo():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-027")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-027: no child inherits an embargo yet. {_SPLIT_BUILD}",
)
def test_no_parent_consent_row_carries_over():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-028")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-028: no child inherits an embargo yet. {_SPLIT_BUILD}",
)
def test_no_open_parent_proposal_is_inherited():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-029")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-029: no child case is created yet. {_SPLIT_BUILD}",
)
def test_no_default_embargo_runs_for_a_child():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-030")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-030: no child case is created yet. {_SPLIT_BUILD}",
)
def test_the_child_ledger_begins_at_its_own_genesis():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-031")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-031: no split proposal exists yet. {_SPLIT_BUILD}",
)
def test_the_split_report_is_the_child_only_report():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-032")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-032: no split proposal exists yet. {_SPLIT_BUILD}",
)
def test_child_stub_invites_carry_the_split_stub_summary():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-033")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-033: no split proposal exists yet. {_SPLIT_BUILD}",
)
def test_a_split_proposal_with_a_parent_report_or_no_summary_is_refused():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-034")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-034: no child initialization exists yet. {_SPLIT_BUILD}",
)
def test_child_initialization_skips_the_reporter_steps():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-035")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-035: no child initialization exists yet. {_SPLIT_BUILD}",
)
def test_child_initialization_seats_the_case_manager_and_owner():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-036")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-036: no child initialization exists yet. {_SPLIT_BUILD}",
)
def test_authoring_the_child_report_gives_no_reporter_role():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-037")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-037: no child initialization exists yet. {_SPLIT_BUILD}",
)
def test_no_child_invite_before_the_creation_entry():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-038")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-038: no child case is created yet. {_SPLIT_BUILD}",
)
def test_parent_recipients_exclude_a_child_only_participant():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-039")
@pytest.mark.xfail(
    strict=True,
    reason=f"CM-32-039: no child case is created yet. {_SPLIT_BUILD}",
)
def test_a_child_only_participant_gets_no_parent_entry():
    assert _split_proposal_exists()


@pytest.mark.spec("CM-32-040")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-040: no split-family embargo notice exists yet. {_SPLIT_BUILD}"
    ),
)
def test_an_earlier_end_notice_carries_id_end_time_and_rationale():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-041")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-041: no split-family embargo notice exists yet. {_SPLIT_BUILD}"
    ),
)
def test_the_earlier_end_rationale_is_on_the_child_ledger():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-042")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-042: no split-family embargo notice exists yet. {_SPLIT_BUILD}"
    ),
)
def test_an_earlier_end_proposal_with_no_rationale_is_refused():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-043")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-043: no split-family embargo notice exists yet. {_SPLIT_BUILD}"
    ),
)
def test_a_family_notice_changes_no_em_state_or_consent():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-044")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-044: no split-family embargo notice exists yet. {_SPLIT_BUILD}"
    ),
)
def test_a_family_notice_carries_only_three_items():
    assert _family_notice_exists()


@pytest.mark.spec("CM-32-045")
@pytest.mark.xfail(
    strict=True,
    reason=(
        f"CM-32-045: no split family exists to hold at one CASE_MANAGER yet. "
        f"{_SPLIT_BUILD}"
    ),
)
def test_a_delegation_out_of_the_family_is_refused():
    assert _split_proposal_exists()
