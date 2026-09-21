"""Tests for vultron.metadata.planning.bundle_fit (ISSUE-3482).

All tests here are pure: they construct ``Candidate`` records directly or feed
a GraphQL-shaped dict to ``parse_graphql``. Nothing touches the network, so
these stay in the default suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.planning.bundle_fit import (
    DEFAULT_BUDGET,
    Candidate,
    _render,
    coherence_hints,
    effective_schedule,
    eligibility,
    parse_graphql,
    select_bundle,
)


def task(number: int, size: str | None = "size:M", **kw) -> Candidate:
    """A minimal eligible Task candidate."""
    labels = list(kw.pop("labels", []))
    if size:
        labels.append(size)
    return Candidate(
        number=number,
        title=kw.pop("title", f"task {number}"),
        issue_type=kw.pop("issue_type", "Task"),
        labels=labels,
        **kw,
    )


class TestEligibility:
    """Stage 1 is unchanged behaviour — these lock it in place."""

    def test_open_unassigned_unblocked_leaf_is_eligible(self):
        kept, rejected = eligibility([task(1)])
        assert [c.number for c in kept] == [1]
        assert rejected == []

    @pytest.mark.parametrize(
        "kwargs,reason_fragment",
        [
            ({"state": "CLOSED"}, "closed"),
            ({"assignees": ["someone"]}, "assigned"),
            ({"labels": ["stale-claim"]}, "stale-claim"),
            ({"open_blockers": [99]}, "blocked"),
            ({"child_count": 3}, "children"),
        ],
    )
    def test_ineligible_candidates_are_rejected_with_a_reason(
        self, kwargs, reason_fragment
    ):
        kept, rejected = eligibility([task(1, **kwargs)])
        assert kept == []
        assert len(rejected) == 1
        assert rejected[0].stage == "eligibility"
        assert reason_fragment in rejected[0].reason.lower()


class TestWorkflowPartition:
    """A bundle is homogeneous by executing skill (work-issue's routing)."""

    def test_idea_is_not_a_build_candidate(self):
        """#3340 (Idea) passed eligibility and was proposed for /build."""
        bundle = select_bundle([task(1), task(2, issue_type="Idea")])
        assert bundle.workflow == "build"
        assert [c.number for c in bundle.members] == [1]
        (rej,) = [r for r in bundle.rejected if r.number == 2]
        assert rej.stage == "fit"
        assert "plan-issue" in rej.reason

    def test_concern_is_not_a_build_candidate(self):
        """#3446 (Concern) was proposed for /build."""
        bundle = select_bundle([task(1), task(2, issue_type="Concern")])
        assert [c.number for c in bundle.members] == [1]
        assert "plan-issue" in next(
            r.reason for r in bundle.rejected if r.number == 2
        )

    def test_bug_routes_to_bugfix_not_build(self):
        """#3355 (Bug) was proposed for /build."""
        bundle = select_bundle([task(1), task(2, issue_type="Bug")])
        assert [c.number for c in bundle.members] == [1]
        assert "bugfix" in next(
            r.reason for r in bundle.rejected if r.number == 2
        )

    def test_workflow_follows_the_top_ranked_candidate(self):
        """With no workflow requested, the highest-priority candidate picks it."""
        bundle = select_bundle(
            [
                task(1, issue_type="Bug", schedule="Now"),
                task(2, schedule="Later"),
            ]
        )
        assert bundle.workflow == "bugfix"
        assert [c.number for c in bundle.members] == [1]

    def test_requested_workflow_overrides_ranking(self):
        bundle = select_bundle(
            [
                task(1, issue_type="Bug", schedule="Now"),
                task(2, schedule="Later"),
            ],
            workflow="build",
        )
        assert bundle.workflow == "build"
        assert [c.number for c in bundle.members] == [2]

    def test_unknown_issue_type_is_rejected_not_silently_bundled(self):
        bundle = select_bundle([task(1), task(2, issue_type=None)])
        assert [c.number for c in bundle.members] == [1]
        assert (
            "type"
            in next(r.reason for r in bundle.rejected if r.number == 2).lower()
        )


class TestScheduleTier:
    """PAD-03-001: Schedule on Project #24 is authoritative, not list order."""

    def test_now_outranks_next_outranks_later(self):
        bundle = select_bundle(
            [
                task(1, size="size:S", schedule="Later"),
                task(2, size="size:S", schedule="Now"),
                task(3, size="size:S", schedule="Next"),
            ]
        )
        assert [c.number for c in bundle.members] == [2, 3, 1]

    def test_someday_is_excluded_below_tier(self):
        bundle = select_bundle([task(1), task(2, schedule="Someday")])
        assert [c.number for c in bundle.members] == [1]
        rej = next(r for r in bundle.rejected if r.number == 2)
        assert rej.stage == "fit"
        assert "tier" in rej.reason.lower()

    def test_unset_leaf_inherits_the_epic_schedule(self):
        """Most leaves carry no Schedule of their own; PAD-03-001 allows the
        tier to sit on the Epic instead."""
        assert effective_schedule(task(1, schedule=None), "Next") == "Next"
        assert effective_schedule(task(1, schedule="Now"), "Next") == "Now"

    def test_epic_schedule_does_not_override_an_explicit_leaf_tier(self):
        bundle = select_bundle(
            [task(1, size="size:S", schedule="Someday")], epic_schedule="Now"
        )
        assert bundle.members == []

    def test_ties_break_on_list_order(self):
        bundle = select_bundle(
            [task(7, size="size:S"), task(3, size="size:S")],
            epic_schedule="Now",
        )
        assert [c.number for c in bundle.members] == [7, 3]


class TestSizeBudget:
    """The headline defect: five size:L issues bundled as readily as five S."""

    def test_weights_are_s1_m2_l3(self):
        assert task(1, size="size:S").weight == 1
        assert task(1, size="size:M").weight == 2
        assert task(1, size="size:L").weight == 3

    def test_unsized_candidate_is_weighted_as_largest(self):
        """#3340 carried no size: label and was bundled with no accounting."""
        assert task(1, size=None).weight == 3

    def test_budget_stops_the_bundle(self):
        bundle = select_bundle(
            [task(n, size="size:L") for n in (1, 2, 3)], epic_schedule="Now"
        )
        assert [c.number for c in bundle.members] == [1, 2]
        assert bundle.weight == DEFAULT_BUDGET
        rej = next(r for r in bundle.rejected if r.number == 3)
        assert rej.stage == "fit"
        assert "budget" in rej.reason.lower()

    def test_small_issues_bundle_freely(self):
        bundle = select_bundle(
            [task(n, size="size:S") for n in range(1, 6)], epic_schedule="Now"
        )
        assert len(bundle.members) == 5
        assert bundle.weight == 5

    def test_member_ceiling_applies_under_budget(self):
        cands = [task(n, size="size:S") for n in range(1, 8)]
        bundle = select_bundle(cands, epic_schedule="Now", budget=99)
        assert len(bundle.members) == 5
        assert (
            "member"
            in next(r.reason for r in bundle.rejected if r.number == 6).lower()
        )

    def test_an_oversized_candidate_does_not_block_a_smaller_one(self):
        """Budget refusal must not terminate the scan — a later small issue
        that still fits belongs in the bundle."""
        bundle = select_bundle(
            [
                task(1, size="size:L"),
                task(2, size="size:L"),
                task(3, size="size:S"),
            ],
            epic_schedule="Now",
            budget=4,
        )
        assert [c.number for c in bundle.members] == [1, 3]


class TestRejectionStages:
    """SKILL.md:54-58 reported only eligibility reasons, never fit reasons."""

    def test_fit_and_eligibility_rejections_are_distinguishable(self):
        bundle = select_bundle(
            [
                task(1, size="size:S"),
                task(2, assignees=["a"]),
                task(3, schedule="Someday"),
            ],
            epic_schedule="Now",
        )
        stages = {r.number: r.stage for r in bundle.rejected}
        assert stages == {2: "eligibility", 3: "fit"}

    def test_every_non_member_is_accounted_for(self):
        cands = [
            task(1, size="size:S"),
            task(2, issue_type="Idea"),
            task(3, state="CLOSED"),
            task(4, schedule="Someday"),
        ]
        bundle = select_bundle(cands, epic_schedule="Now")
        accounted = {c.number for c in bundle.members} | {
            r.number for r in bundle.rejected
        }
        assert accounted == {1, 2, 3, 4}


class TestCoherenceHints:
    """Hints only — the grain call stays with the agent (calve-epics:290)."""

    def test_shared_spec_id_is_surfaced(self):
        members = [
            task(1, title="Eradicate broad except (CS-23-001) in adapters"),
            task(2, title="Fix the CS-23-001 rules eradication missed"),
        ]
        assert any("CS-23-001" in h for h in coherence_hints(members))

    def test_unrelated_titles_produce_no_shared_signal(self):
        members = [
            task(1, title="Fix inbox endpoint"),
            task(2, title="Add a demo"),
        ]
        assert coherence_hints(members) == []

    def test_shared_label_is_surfaced_but_size_labels_are_not(self):
        members = [
            task(1, size="size:L", labels=["concern"]),
            task(2, size="size:L", labels=["concern"]),
        ]
        hints = coherence_hints(members)
        assert any("concern" in h for h in hints)
        assert not any("size:" in h for h in hints)


class TestBundleRendering:
    def test_closed_candidates_are_not_listed_as_not_workable(self):
        """A long Epic has dozens of closed children; listing finished work
        buries the rows a human can act on."""
        bundle = select_bundle(
            [
                task(1, size="size:S"),
                task(2, state="CLOSED"),
                task(3, assignees=["a"]),
            ],
            epic_schedule="Now",
        )
        report = _render(bundle)
        assert "#2" not in report
        assert "#3" in report

    def test_report_names_the_budget_and_the_grain_question(self):
        bundle = select_bundle([task(1, size="size:S")], epic_schedule="Now")
        report = _render(bundle)
        assert "1/6" in report
        assert "one sentence" in report

    def test_command_names_the_workflow_and_members(self):
        bundle = select_bundle(
            [task(1, size="size:S"), task(2, size="size:S")],
            epic_schedule="Now",
        )
        assert bundle.command == "/build 1 2"

    def test_empty_bundle_has_no_command(self):
        bundle = select_bundle([task(1, schedule="Someday")])
        assert bundle.members == []
        assert bundle.command is None


class TestSharedQueryContract:
    """The fit rules are inert unless the shared query supplies their inputs.

    Dropping ``issueType`` fails loudly (every candidate becomes unroutable),
    but dropping the ``Schedule`` field fails **silently**: every tier reads as
    unset, so ordering quietly degrades back to sub-issue list order — the exact
    defect ISSUE-3482 fixed. These assertions keep both fields requested.
    """

    QUERY = (
        Path(__file__).parents[2]
        / ".agents/skills/shared/query-epic-subissues.sh"
    )

    def test_query_requests_issue_type(self):
        assert "issueType" in self.QUERY.read_text()

    def test_query_requests_the_schedule_field_for_epic_and_leaves(self):
        text = self.QUERY.read_text()
        assert text.count('fieldValueByName(name: \\"Schedule\\")') == 2


class TestParseGraphQL:
    """The shared query must supply issueType and the leaf Schedule."""

    @staticmethod
    def _payload():
        def item(project_number, schedule):
            return {
                "project": {"number": project_number},
                "fieldValueByName": (
                    {"name": schedule} if schedule is not None else None
                ),
            }

        return {
            "data": {
                "repository": {
                    "issue": {
                        "number": 3329,
                        "title": "Fail-loud defensive code",
                        "projectItems": {"nodes": [item(24, "Next")]},
                        "subIssues": {
                            "nodes": [
                                {
                                    "number": 3326,
                                    "title": "Eradicate broad except",
                                    "state": "OPEN",
                                    "issueType": {"name": "Task"},
                                    "assignees": {"nodes": []},
                                    "blockedBy": {"nodes": []},
                                    "subIssues": {"totalCount": 0},
                                    "labels": {"nodes": [{"name": "size:L"}]},
                                    "projectItems": {
                                        "nodes": [
                                            item(7, "Now"),
                                            item(24, None),
                                        ]
                                    },
                                },
                                {
                                    "number": 3355,
                                    "title": "potential_actions bug",
                                    "state": "OPEN",
                                    "issueType": {"name": "Bug"},
                                    "assignees": {"nodes": [{"login": "x"}]},
                                    "blockedBy": {
                                        "nodes": [
                                            {"number": 9, "state": "OPEN"}
                                        ]
                                    },
                                    "subIssues": {"totalCount": 2},
                                    "labels": {"nodes": [{"name": "size:M"}]},
                                    "projectItems": {
                                        "nodes": [item(24, "Now")]
                                    },
                                },
                            ]
                        },
                    }
                }
            }
        }

    def test_epic_number_and_schedule_are_extracted(self):
        epic, schedule, _ = parse_graphql(self._payload())
        assert epic == 3329
        assert schedule == "Next"

    def test_leaf_fields_are_extracted(self):
        _, _, cands = parse_graphql(self._payload())
        by_number = {c.number: c for c in cands}
        assert by_number[3326].issue_type == "Task"
        assert by_number[3326].labels == ["size:L"]
        assert by_number[3355].issue_type == "Bug"
        assert by_number[3355].assignees == ["x"]
        assert by_number[3355].open_blockers == [9]
        assert by_number[3355].child_count == 2

    def test_only_the_planning_board_supplies_the_schedule(self):
        """A Schedule value from another project must not be read as tier."""
        _, _, cands = parse_graphql(self._payload(), project_number=24)
        by_number = {c.number: c for c in cands}
        assert by_number[3326].schedule is None
        assert by_number[3355].schedule == "Now"
