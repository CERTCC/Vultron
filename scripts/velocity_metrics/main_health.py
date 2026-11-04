"""Health of main: weekly failed CI runs and the red episodes on main, each
with its candidate partner merges (PAD-18-007)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime

from .periods import _iso_z, iso_to_date, week_key
from .pr_pipeline import (
    _FAILED_CONCLUSIONS,
    _IGNORED_CONCLUSIONS,
    _RunIndex,
)


def _weekly_main_failures(
    main_runs: list[dict], all_weeks: list[str]
) -> list[dict]:
    """Count failed CI runs on the main branch per week.

    ``main_runs`` is a list of workflow-run dicts from the REST API.  As for
    PRs, a CI run is one head commit: a commit on main counts once, in the
    week of its first failed workflow run, however many of its workflows
    failed.
    """
    week_set = set(all_weeks)
    first_failure: dict[str, date] = {}
    for run in main_runs:
        if run.get("conclusion") not in _FAILED_CONCLUSIONS:
            continue
        d = iso_to_date(run.get("created_at"))
        sha = run.get("head_sha") or ""
        if d is None or not sha:
            continue
        if sha not in first_failure or d < first_failure[sha]:
            first_failure[sha] = d
    counts: dict[str, int] = defaultdict(int)
    for d in first_failure.values():
        w = week_key(d)
        if w in week_set:
            counts[w] += 1
    return [
        {"week": w, "failed_ci_runs_on_main": counts.get(w, 0)}
        for w in all_weeks
    ]


def _workflow_key(run: dict) -> str:
    """Return the identity of the workflow a run belongs to.

    ``path`` names the workflow file and survives a rename of the display
    ``name``; ``workflow_id`` and ``name`` are fallbacks for trimmed records.
    """
    for field in ("path", "workflow_id", "name"):
        value = run.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def _run_order(run: dict) -> tuple[str, int]:
    """Sort key for runs: creation time, then numeric run id.

    Run ids grow with creation, so they order runs that share a
    ``created_at`` second; they are compared as numbers, not strings.
    """
    run_id = run.get("id")
    return run["created_at"], run_id if isinstance(run_id, int) else -1


def _main_red_spans(main_runs: list[dict]) -> list[dict]:
    """Group consecutive failed push runs on main into episodes, per workflow.

    For each workflow, runs are walked in creation order.  An episode opens
    at a failed run that follows a green (``success``) run and closes at the
    next green run; every failed run between them belongs to it.  Cancelled
    and skipped runs say nothing about main and are passed over, as are runs
    with any other conclusion that is neither failed nor ``success`` (such
    as ``neutral``) and runs with no ``created_at``.  A red streak that is
    already under way at the first run in the window has no green run before
    it, so its start is unknown: it is returned with ``opened_after_green`` false and
    ``prior_green_sha``/``prior_green_at`` ``None``.

    Returns one dict per episode with ``workflow`` (display name),
    ``workflow_path`` (the grouping key, see ``_workflow_key``),
    ``opened_after_green``, ``prior_green_sha``, ``prior_green_at``,
    ``first_red_sha``, ``first_red_at``, ``last_red_sha``, ``red_runs``, and
    ``ended_at`` (the closing green run's ``created_at``, or ``None`` while
    the episode is still open).  Episodes are ordered by ``first_red_at``.
    """
    by_workflow: dict[str, list[dict]] = defaultdict(list)
    for run in main_runs:
        conclusion = run.get("conclusion") or ""
        if conclusion in _IGNORED_CONCLUSIONS or not run.get("created_at"):
            continue
        by_workflow[_workflow_key(run)].append(run)

    episodes: list[dict] = []
    for key, runs in by_workflow.items():
        runs.sort(key=_run_order)
        last_green: dict | None = None
        current: dict | None = None
        for run in runs:
            conclusion = run.get("conclusion")
            if conclusion in _FAILED_CONCLUSIONS:
                if current is None:
                    current = {
                        "workflow": run.get("name") or key,
                        "workflow_path": key,
                        "opened_after_green": last_green is not None,
                        "prior_green_sha": (
                            last_green.get("head_sha") if last_green else None
                        ),
                        "prior_green_at": (
                            last_green["created_at"] if last_green else None
                        ),
                        "first_red_sha": run.get("head_sha"),
                        "first_red_at": run["created_at"],
                        "last_red_sha": run.get("head_sha"),
                        "red_runs": 0,
                        "ended_at": None,
                    }
                    episodes.append(current)
                current["last_red_sha"] = run.get("head_sha")
                current["red_runs"] += 1
            elif conclusion == "success":
                if current is not None:
                    current["ended_at"] = run["created_at"]
                    current = None
                last_green = run
    episodes.sort(key=lambda e: (e["first_red_at"], e["workflow_path"]))
    return episodes


def _merged_to_main(prs: list[dict]) -> list[dict]:
    """Return the PRs merged into ``main``, leaving out other bases.

    PRs merged into an integration branch or ``publish`` are not merges to
    main: they neither count toward the merge rate nor partner a break.
    """
    return [pr for pr in prs if pr.get("baseRefName") == "main"]


def _last_green_ci_at(runs: list[dict]) -> str | None:
    """Return when a PR's last green CI run started, or ``None``.

    A CI run is one head commit (see ``_ci_iteration_counts``); it is green
    when at least one of its workflow runs succeeded and none failed.  Its
    start is its earliest workflow run's ``created_at``, the moment CI
    checked out the base it tested against.  Runs with no ``head_sha`` or
    no ``created_at`` are passed over.
    """
    by_sha: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        sha = run.get("head_sha") or ""
        if sha and run.get("created_at"):
            by_sha[sha].append(run)
    starts = [
        min(r["created_at"] for r in group)
        for group in by_sha.values()
        if "success" in {r.get("conclusion") for r in group}
        and not {r.get("conclusion") for r in group} & _FAILED_CONCLUSIONS
    ]
    return max(starts) if starts else None


def _merged_between(prs: list[dict], after: str, before: str) -> list[int]:
    """Return the numbers of PRs merged strictly between two times.

    Ordered by merge time.  The bounds are ISO-8601 UTC strings, which
    compare in time order.
    """
    window = [p for p in prs if after < (p.get("mergedAt") or "") < before]
    window.sort(key=lambda p: p.get("mergedAt") or "")
    return [p["number"] for p in window]


def _landed_at(
    by_merge_sha: dict[str, dict], sha: str | None, run_at: str
) -> str:
    """Return when a commit on main landed.

    That is the merge time of the PR whose merge commit it is, or, for a
    direct push or a merge from before the window, its run's ``created_at``.
    A run starts seconds after its commit lands, so the merge time is the
    tighter bound when it is known.
    """
    pr = by_merge_sha.get(sha or "")
    return (pr.get("mergedAt") if pr else None) or run_at


def _main_red_episodes(
    main_runs: list[dict],
    prs: list[dict],
    index: _RunIndex,
    merged_since: date,
) -> list[dict]:
    """Build the red-episode records on main, with candidate partners.

    ``prs`` are the merged PRs fetched from ``merged_since``; only those
    merged into main are used (see ``_merged_to_main``).  Each episode from
    ``_main_red_spans`` gains:

    - ``pr_number``: the PR whose merge commit is the episode's first red
      commit, or ``None`` when no PR merged to main in the window owns it
      (a direct push, or a merge from before the window).
    - ``last_green_ci_at``: that PR's last green CI run (see
      ``_last_green_ci_at``), or ``None`` when the PR or its green run is
      unknown.
    - ``candidate_partners``: the PRs merged to main after that run and
      before the PR's own merge, the merges its last green run could not
      have seen.  ``None`` when the run is unknown, or when it predates
      ``merged_since`` and so earlier partners were never fetched; ``[]``
      means no merge landed in between.
    - ``unverified_merges``: the PRs, other than ``pr_number``, merged to
      main after the prior green commit and before the first red commit.
      None of them has a completed run in this workflow: each run was
      cancelled or skipped, or never started because of a ``paths`` filter.
      Any of them may be the real breaker, and ``pr_number`` only the first
      commit to finish red.  Each bound is the merge time of the PR whose
      merge commit is that green or red commit, or the run's ``created_at``
      for a direct push, since a run starts after its commit lands.
      ``None`` when there was no prior green run.

    Classifying an episode (semantic conflict, scenario coverage gap,
    already red, infrastructure) is left to a human.
    """
    main_prs = _merged_to_main(prs)
    window_start = _iso_z(
        datetime.combine(merged_since, datetime.min.time(), UTC)
    )
    by_merge_sha = {
        oid: pr
        for pr in main_prs
        if (oid := (pr.get("mergeCommit") or {}).get("oid"))
    }
    records = []
    for span in _main_red_spans(main_runs):
        pr = by_merge_sha.get(span["first_red_sha"] or "")
        last_green = _last_green_ci_at(index.runs_for(pr)) if pr else None
        partners = (
            _merged_between(main_prs, last_green, pr.get("mergedAt") or "")
            if pr is not None
            and last_green is not None
            and last_green >= window_start
            else None
        )
        unverified = (
            _merged_between(
                main_prs,
                _landed_at(
                    by_merge_sha,
                    span["prior_green_sha"],
                    span["prior_green_at"],
                ),
                _landed_at(
                    by_merge_sha, span["first_red_sha"], span["first_red_at"]
                ),
            )
            if span["prior_green_at"] is not None
            else None
        )
        records.append(
            {
                **span,
                "pr_number": pr.get("number") if pr else None,
                "last_green_ci_at": last_green,
                "candidate_partners": partners,
                "unverified_merges": unverified,
            }
        )
    return records


def _weekly_main_episodes(
    episodes: list[dict], prs: list[dict], all_weeks: list[str]
) -> list[dict]:
    """Count red episodes opened on main, and merges to main, per week.

    Episodes are grouped per workflow, so one breaking commit that fails
    several workflows opens several episodes.  The weekly count is of
    breaks, not workflows: episodes that share a ``first_red_sha`` count
    once, in the week of their first red run, and only when they opened
    after a green run (a streak already red at the window start did not open
    in that week).  ``merges_to_main`` counts PRs merged into main by
    ``mergedAt``.  ``red_episodes_per_100_merges`` is ``None`` for a week
    with no merges, where the rate is undefined.
    """
    week_set = set(all_weeks)
    breaks: dict[str, set[str]] = defaultdict(set)
    for ep in episodes:
        d = iso_to_date(ep.get("first_red_at"))
        if ep.get("opened_after_green") and d and week_key(d) in week_set:
            breaks[week_key(d)].add(ep.get("first_red_sha") or "")
    merges: dict[str, int] = defaultdict(int)
    for pr in _merged_to_main(prs):
        d = iso_to_date(pr.get("mergedAt"))
        if d and week_key(d) in week_set:
            merges[week_key(d)] += 1
    rows = []
    for w in all_weeks:
        n_ep, n_merge = len(breaks.get(w, ())), merges.get(w, 0)
        rows.append(
            {
                "week": w,
                "red_episodes_opened_on_main": n_ep,
                "merges_to_main": n_merge,
                "red_episodes_per_100_merges": (
                    round(100 * n_ep / n_merge, 1) if n_merge else None
                ),
            }
        )
    return rows
