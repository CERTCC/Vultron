"""Tests for vultron.metadata.planning.bundle_fit (ISSUE-3482).

All tests here are pure: they construct ``Candidate`` records directly or feed
a GraphQL-shaped dict to ``parse_graphql``. Nothing touches the network, so
these stay in the default suite.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from vultron.metadata.planning.bundle_fit import (
    DEFAULT_BUDGET,
    EXCLUDED_TIERS,
    KNOWN_TIERS,
    SCHEDULE_ORDER,
    SIZE_WEIGHTS,
    UNBUNDLABLE_LABELS,
    UNSIZED_LABEL,
    UNSIZED_WEIGHT,
    Candidate,
    _render,
    coherence_hints,
    effective_schedule,
    eligibility,
    graphql_errors,
    main,
    parse_graphql,
    schedule_rank,
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

    def test_focus_is_the_best_tier_not_the_worst(self):
        """`Focus` is the board's top tier, but was absent from SCHEDULE_ORDER,
        so it fell through to the unknown-tier rank and sorted below `Someday`.
        """
        assert schedule_rank("Focus") < schedule_rank("Now")
        bundle = select_bundle(
            [
                task(1, size="size:S", schedule="Later"),
                task(2, schedule="Focus"),
            ]
        )
        assert [c.number for c in bundle.members] == [2, 1]

    def test_every_board_tier_is_ranked_or_excluded(self):
        """Ratchet: a tier in neither set ranks *last*, silently — which is how
        `Focus` came to sort below `Someday`.

        The authority is `board-id.sh`, whose usage block enumerates the Schedule
        options it can resolve. `board-ids.json` holds the live values but is a
        gitignored TTL cache, so it is absent in CI and cannot be the ratchet.
        """
        usage = (
            Path(__file__).parents[2] / ".agents/skills/shared/board-id.sh"
        ).read_text()
        match = re.search(r"Schedule option ID \(([^)]+)\)", usage)
        assert match, "board-id.sh no longer documents the Schedule options"
        documented = {name.strip() for name in match.group(1).split("|")}
        assert documented == KNOWN_TIERS, (
            "SCHEDULE_ORDER/EXCLUDED_TIERS are out of step with the board: "
            f"{documented ^ KNOWN_TIERS}"
        )
        # Anything not deliberately excluded must be *ranked*, not merely known.
        # (`Someday` is in both sets: it has a rank and is never bundled.)
        assert documented - EXCLUDED_TIERS <= set(SCHEDULE_ORDER)

    def test_a_focus_bug_is_not_evicted_by_a_later_task(self):
        """The workflow is chosen by the top-ranked candidate, so mis-ranking
        `Focus` handed the bundle to a `Later` item and rejected the `Focus` one.
        """
        bundle = select_bundle(
            [
                task(1, size="size:S", schedule="Later"),
                task(2, size="size:S", issue_type="Bug", schedule="Focus"),
            ]
        )
        assert bundle.workflow == "bugfix"
        assert [c.number for c in bundle.members] == [2]

    def test_completed_is_never_bundled(self):
        bundle = select_bundle([task(1, schedule="Completed")])
        assert bundle.members == []
        assert "tier" in next(iter(bundle.rejected)).reason.lower()

    def test_an_unrecognised_tier_is_reported_not_ranked(self):
        """Board options are server-generated and mutable, so a renamed or
        case-slipped tier must be loud rather than sorted as if unset."""
        bundle = select_bundle([task(1, size="size:S", schedule="someday")])
        assert bundle.members == []
        (rej,) = bundle.rejected
        assert rej.stage == "fit"
        assert "unrecognised" in rej.reason.lower()

    def test_inheritance_drives_ordering_inside_select_bundle(self):
        """`effective_schedule` is unit-tested directly, but nothing asserted
        that inheritance reaches the *sort* — a worse explicit leaf tier must
        lose to a sibling that inherits a better Epic tier."""
        bundle = select_bundle(
            [
                task(1, size="size:S", schedule="Later"),
                task(2, size="size:S", schedule=None),
            ],
            epic_schedule="Now",
        )
        assert [c.number for c in bundle.members] == [2, 1]

    def test_an_excluded_epic_tier_is_inherited_too(self):
        bundle = select_bundle(
            [task(1, size="size:S")], epic_schedule="Someday"
        )
        assert bundle.members == []
        assert "Someday" in next(iter(bundle.rejected)).reason


class TestSizeBudget:
    """The headline defect: five size:L issues bundled as readily as five S."""

    def test_weights_derive_from_the_band_table(self):
        """The values live in `size_bands`; restating them here would be the
        ninth copy of a table that was already wrong in eight places."""
        for label, weight in SIZE_WEIGHTS.items():
            assert task(1, size=label).weight == weight

    def test_unsized_candidate_is_weighted_as_largest_bundlable(self):
        """#3340 carried no size: label and was bundled with no accounting."""
        assert task(1, size=None).weight == UNSIZED_WEIGHT
        assert UNSIZED_WEIGHT == max(SIZE_WEIGHTS.values())

    def test_the_largest_size_label_wins_and_is_the_one_reported(self):
        """Two size labels resolved by `max` for the weight but by list order
        for the report, so a row could read `size:S ... weight=3`."""
        c = Candidate(number=1, issue_type="Task", labels=["size:S", "size:L"])
        assert c.weight == SIZE_WEIGHTS["size:L"]
        assert c.size_label == "size:L"
        assert Candidate(number=2).size_label == UNSIZED_LABEL

    def test_a_weightless_band_is_still_a_measured_size(self):
        """`sized` and `size_label` test against every band, not just the
        weighted ones — a size:XL issue is measured, so reporting it as
        `unsized` would be a second wrong answer on top of refusing it."""
        xl = sorted(UNBUNDLABLE_LABELS)[0]
        c = Candidate(number=1, issue_type="Task", labels=[xl])
        assert c.sized is True
        assert c.size_label == xl
        assert c.unbundlable is True

    def test_a_weightless_band_is_not_mistaken_for_a_topic_label(self):
        """It is a size signal, so it is never coherence evidence."""
        xl = sorted(UNBUNDLABLE_LABELS)[0]
        c = Candidate(number=1, issue_type="Task", labels=[xl, "wire"])
        assert c.topic_labels == ["wire"]

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


class TestReviewCeiling:
    """The top band is refused, not weighted.

    A weight says "fits alongside something smaller". Review findings per 1000
    diff lines fall by half above this band's floor, so a PR that big already
    exhausts the review budget on its own and must never carry a passenger.
    """

    def test_an_unbundlable_candidate_is_refused_at_the_fit_stage(self):
        xl = sorted(UNBUNDLABLE_LABELS)[0]
        bundle = select_bundle([task(1, size=xl)], epic_schedule="Now")
        assert bundle.members == []
        rej = next(r for r in bundle.rejected if r.number == 1)
        assert rej.stage == "fit"
        assert "review ceiling" in rej.reason
        assert xl in rej.reason

    def test_it_is_refused_even_when_the_budget_could_absorb_it(self):
        """Weighting it at 4 against a budget of 6 would let it bundle with an
        M. The refusal is categorical, so a raised budget cannot reopen it."""
        xl = sorted(UNBUNDLABLE_LABELS)[0]
        bundle = select_bundle(
            [task(1, size=xl), task(2, size="size:M")],
            epic_schedule="Now",
            budget=99,
        )
        assert [c.number for c in bundle.members] == [2]

    def test_refusing_it_does_not_end_the_scan(self):
        xl = sorted(UNBUNDLABLE_LABELS)[0]
        bundle = select_bundle(
            [task(1, size=xl), task(2, size="size:S")], epic_schedule="Now"
        )
        assert [c.number for c in bundle.members] == [2]

    def test_an_unbundlable_candidate_never_reaches_the_weight_check(self):
        """Its reason names the band, not a weight — `weight` is meaningless
        for a band that has none, and no report may print one."""
        xl = sorted(UNBUNDLABLE_LABELS)[0]
        bundle = select_bundle([task(1, size=xl)], epic_schedule="Now")
        reason = next(r for r in bundle.rejected if r.number == 1).reason
        assert "weight" not in reason
        assert "budget" not in reason


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

    def test_shared_file_path_is_surfaced(self):
        """Path overlap is advertised in the module docstring, `bundling.md` and
        PAD-15-007, but the `_PATH_RE` branch had no test at all."""
        members = [
            task(1, title="Harden specs/outbox.yaml retry caps"),
            task(2, title="Document specs/outbox.yaml in notes/outbox.md"),
        ]
        hints = coherence_hints(members)
        assert any(
            "path specs/outbox.yaml" in h for h in hints
        ), f"no path hint in {hints}"

    def test_process_labels_are_not_coherence_evidence(self):
        """`needs-rebase` on two members says nothing about subject matter."""
        members = [
            task(1, labels=["needs-rebase", "needs-triage"]),
            task(2, labels=["needs-rebase", "needs-triage"]),
        ]
        assert coherence_hints(members) == []

    def test_one_member_citing_a_token_twice_is_not_two_members(self):
        """Counts are per member, so a repeated citation must not forge a hint."""
        members = [
            task(1, title="CS-23-001 blocks CS-23-001 in adapters"),
            task(2, title="unrelated work"),
        ]
        assert coherence_hints(members) == []

    def test_a_single_member_has_no_hints(self):
        assert coherence_hints([task(1, title="CS-23-001")]) == []


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

    Both guards read the GraphQL document only, never the whole script. The
    script's header comment *names* both fields it requests, so a bare substring
    search over the file stays green with the query body gutted — the trap
    ``vultron/metadata/AGENTS.md`` § "Changing a Linter Check" describes, where
    naming a symbol in the check's own text puts that token back into the
    scanned corpus.
    """

    QUERY = (
        Path(__file__).parents[2]
        / ".agents/skills/shared/query-epic-subissues.sh"
    )
    SCHEDULE_FIELD = 'fieldValueByName(name: \\"Schedule\\")'

    @classmethod
    def _graphql(cls) -> str:
        """The GraphQL document, with the script's comments excluded."""
        _, sep, query = cls.QUERY.read_text().partition("gh api graphql")
        assert sep, "query-epic-subissues.sh no longer calls `gh api graphql`"
        return "\n".join(
            line
            for line in query.splitlines()
            if not line.lstrip().startswith("#")
        )

    @classmethod
    def _epic_and_leaf_scopes(cls) -> tuple[str, str]:
        """The query split at the sub-issue block: (Epic fields, leaf fields).

        Counting occurrences cannot tell the two nesting levels apart, so
        deleting the Epic-level block and duplicating the leaf one keeps the
        count right while Epic-tier inheritance dies. Splitting pins each level
        to its own assertion.
        """
        epic, sep, leaves = cls._graphql().partition("subIssues(first:")
        assert sep, "the query no longer requests the Epic's sub-issues"
        return epic, leaves

    def test_query_requests_issue_type(self):
        assert "issueType { name }" in self._graphql()

    def test_query_requests_the_schedule_field_for_the_epic(self):
        """Without this, `epic_schedule` is always None and no leaf inherits."""
        epic_scope, _ = self._epic_and_leaf_scopes()
        assert self.SCHEDULE_FIELD in epic_scope

    def test_query_requests_the_schedule_field_for_every_leaf(self):
        _, leaf_scope = self._epic_and_leaf_scopes()
        assert self.SCHEDULE_FIELD in leaf_scope

    def test_the_guards_ignore_the_scripts_own_documentation(self):
        """Ratchet on the ratchets above: prove they read the query, not prose.

        Both field names appear in the header comment. If ``_graphql()`` ever
        stops excluding it, the three guards above become unfalsifiable without
        any of them failing — so assert the header is really out of scope.
        """
        header, _, _ = self.QUERY.read_text().partition("gh api graphql")
        # A naive `"issueType" in read_text()` would be satisfied by this alone.
        assert "issueType" in header, "header no longer documents issueType"
        assert "Schedule" in header, "header no longer documents Schedule"
        # The tokens the guards actually require appear only in the query body.
        assert "issueType { name }" not in header
        assert self.SCHEDULE_FIELD not in header


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

    @pytest.mark.parametrize(
        "blocker,expected",
        [
            ({"number": 7, "state": "CLOSED"}, []),
            ({"number": 7, "state": "OPEN"}, [7]),
            # Fail closed: an absent or null state must not read as unblocked.
            ({"number": 7}, [7]),
            ({"number": 7, "state": None}, [7]),
        ],
    )
    def test_only_a_closed_blocker_stops_blocking(self, blocker, expected):
        payload = {
            "data": {
                "repository": {
                    "issue": {
                        "number": 1,
                        "subIssues": {
                            "nodes": [
                                {
                                    "number": 5,
                                    "state": "OPEN",
                                    "issueType": {"name": "Task"},
                                    "blockedBy": {"nodes": [blocker]},
                                }
                            ]
                        },
                    }
                }
            }
        }
        _, _, cands = parse_graphql(payload)
        assert cands[0].open_blockers == expected

    def test_a_graphql_error_payload_is_surfaced_not_swallowed(self):
        assert graphql_errors({"errors": [{"message": "boom"}]}) == ["boom"]
        assert graphql_errors({"data": {}}) == []
        assert graphql_errors({}) == []


class TestCLI:
    """`bundle-fit` is the console script every skill invokes, and `main` had
    no tests: the JSON contract, the exit codes and the diagnostics were all
    unverified."""

    @staticmethod
    def _payload(*leaves, epic_schedule="Now"):
        return {
            "data": {
                "repository": {
                    "issue": {
                        "number": 3329,
                        "title": "Epic",
                        "projectItems": {
                            "nodes": [
                                {
                                    "project": {"number": 24},
                                    "fieldValueByName": {
                                        "name": epic_schedule
                                    },
                                }
                            ]
                        },
                        "subIssues": {"nodes": list(leaves)},
                    }
                }
            }
        }

    @staticmethod
    def _leaf(number, *, size="size:S", issue_type="Task", title="t"):
        return {
            "number": number,
            "title": title,
            "state": "OPEN",
            "issueType": {"name": issue_type},
            "assignees": {"nodes": []},
            "blockedBy": {"nodes": []},
            "subIssues": {"totalCount": 0},
            "labels": {"nodes": [{"name": size}]},
            "projectItems": {"nodes": []},
        }

    def _run(self, monkeypatch, payload, argv=None):
        monkeypatch.setattr(
            "sys.stdin",
            io.StringIO(
                payload if isinstance(payload, str) else json.dumps(payload)
            ),
        )
        return main(argv or [])

    def test_text_report_names_the_command(self, monkeypatch, capsys):
        rc = self._run(
            monkeypatch, self._payload(self._leaf(1), self._leaf(2))
        )
        assert rc == 0
        assert "Run: /build 1 2" in capsys.readouterr().out

    def test_json_output_is_machine_readable(self, monkeypatch, capsys):
        rc = self._run(
            monkeypatch,
            self._payload(self._leaf(1), self._leaf(2, size="size:L")),
            ["--json"],
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["epic"] == 3329
        assert data["workflow"] == "build"
        assert data["command"] == "/build 1 2"
        assert data["weight"] == 4
        assert data["budget"] == DEFAULT_BUDGET
        # The effective tier is resolved per member, not echoed as the raw leaf
        # value, so an inheriting member reports the tier that governed it.
        assert [m["schedule"] for m in data["members"]] == ["Now", "Now"]
        assert data["rejected"] == []

    def test_budget_and_workflow_flags_are_plumbed(self, monkeypatch, capsys):
        rc = self._run(
            monkeypatch,
            self._payload(
                self._leaf(1, size="size:L"), self._leaf(2, size="size:L")
            ),
            ["--json", "--budget", "3"],
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert [m["number"] for m in data["members"]] == [1]
        assert "budget" in data["rejected"][0]["reason"]

    def test_max_members_flag_is_plumbed(self, monkeypatch, capsys):
        rc = self._run(
            monkeypatch,
            self._payload(self._leaf(1), self._leaf(2)),
            ["--json", "--max-members", "1"],
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert [m["number"] for m in data["members"]] == [1]

    def test_project_number_flag_is_plumbed(self, monkeypatch, capsys):
        """Pointing at another board must yield no tier, not board #24's."""
        rc = self._run(
            monkeypatch,
            self._payload(self._leaf(1)),
            ["--json", "--project-number", "99"],
        )
        assert rc == 0
        assert json.loads(capsys.readouterr().out)["epic_schedule"] is None

    def test_invalid_json_on_stdin_exits_two(self, monkeypatch, capsys):
        assert self._run(monkeypatch, "not json") == 2
        assert "not valid JSON" in capsys.readouterr().err

    def test_a_graphql_error_names_the_real_cause(self, monkeypatch, capsys):
        rc = self._run(
            monkeypatch,
            {"errors": [{"message": "Could not resolve to an Issue"}]},
        )
        err = capsys.readouterr().err
        assert rc == 2
        assert "Could not resolve to an Issue" in err
        # The old code guessed at the cause and leaked `None` into the message.
        assert "#None" not in err
        assert "read:project" in err

    def test_a_missing_issue_is_distinguished_from_an_empty_epic(
        self, monkeypatch, capsys
    ):
        assert self._run(monkeypatch, {"data": {"repository": {}}}) == 1
        assert "#None" not in capsys.readouterr().err

        assert self._run(monkeypatch, self._payload()) == 1
        assert "Epic #3329 has no sub-issues" in capsys.readouterr().err
