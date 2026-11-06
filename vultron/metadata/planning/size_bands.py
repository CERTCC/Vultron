"""The ``size:`` label band table — one table, every consumer derives.

Requirements: PAD-05 (size labelling), PAD-15-005 (the bundle size budget).

The band thresholds used to be restated in prose in eight places and computed
in none, and a rule that lives only in agent prose is applied inconsistently.
This module is the single definition; the ``pr-size`` console script applies it
and ``bundle_fit`` imports its weights. ``pr-size --calibrate`` re-runs the
survey against the table (:mod:`~vultron.metadata.planning.size_calibration`),
so a drifted threshold shows up as a number rather than a retrospective.

Two bands, two domains. An **estimate** comes from the acceptance-criteria
count at Issue creation; a **measurement** comes from the diff at PR-open time.
``size:XL`` exists only in the measured domain (``measured_only``), and the
estimate domain ends at the ``size:L`` AC ceiling: an Issue with more ACs than
that gets no label and is decomposed instead (:class:`DecompositionRequired`).
XL is reachable only by discovering after the fact that a PR grew past the
size where CI-fix rates rise. "Estimated L, landed XL" is the signal worth
keeping.

The survey figures behind the thresholds are stated once, dated, in the
PAD-05-011 rationale (``spec-dump --ids PAD-05-011``); do not restate them here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from vultron.metadata.base import repo_root
from vultron.metadata.git_runner import GitError, GitRunner
from vultron.metadata.planning.gh import (
    DEFAULT_REPO,
    GH_FAILURES,
    Runner,
    gh_failure_detail,
    run_gh,
)
from vultron.metadata.planning.size_calibration import (
    BandScheme,
    complete_commits,
    fetch_window,
    render_report,
    run_git,
    trace_fixes,
)


@dataclass(frozen=True)
class SizeBand:
    """One row of the band table.

    Both ceilings are **inclusive**. ``max_lines=None`` means unbounded above,
    which only the last band is. Every estimate band has a finite ``max_acs``:
    past the last one an Issue is decomposed, not labelled, so a
    ``measured_only`` band carries ``None`` there. ``weight`` is the PAD-15-005
    bundle size-weight; ``None`` means the band is never bundled at all.
    """

    label: str
    max_lines: int | None
    max_acs: int | None
    weight: int | None
    measured_only: bool = False

    @property
    def lines_range(self) -> str:
        """The diff range this band covers, for humans."""
        floor = _LINE_FLOORS[self.label]
        if self.max_lines is None:
            return f"{floor}+"
        if floor == 0:
            return f"≤{self.max_lines}"
        return f"{floor}-{self.max_lines}"

    @property
    def acs_range(self) -> str:
        """The AC-count range this band covers, for humans."""
        if self.measured_only or self.max_acs is None:
            return "—"
        floor = _AC_FLOORS[self.label]
        if floor == 0:
            return f"≤{self.max_acs}"
        return f"{floor}-{self.max_acs}"

    @property
    def description(self) -> str:
        """The GitHub label description, so the UI cannot drift either."""
        if self.measured_only:
            return (
                f"{self.lines_range} diff lines — CI-fix rate doubles "
                "here; split it or justify why not"
            )
        return f"{self.lines_range} diff lines or {self.acs_range} ACs"


# The one table. Ordered smallest first; every derived constant below reads it.
SIZE_BANDS: tuple[SizeBand, ...] = (
    SizeBand("size:S", max_lines=200, max_acs=1, weight=1),
    SizeBand("size:M", max_lines=1000, max_acs=3, weight=2),
    SizeBand("size:L", max_lines=2500, max_acs=8, weight=3),
    SizeBand(
        "size:XL",
        max_lines=None,
        max_acs=None,
        weight=None,
        measured_only=True,
    ),
)

# Label colours, kept beside the table they describe. Green through red.
LABEL_COLORS: dict[str, str] = {
    "size:S": "0e8a16",
    "size:M": "f9d0c4",
    "size:L": "e4e669",
    "size:XL": "d93f0b",
}

SIZE_LABELS: tuple[str, ...] = tuple(band.label for band in SIZE_BANDS)

# Bundle weights (PAD-15-005). A band with no weight is not bundlable, so it is
# absent here rather than present with a large number — see UNSIZED_WEIGHT.
SIZE_WEIGHTS: dict[str, int] = {
    band.label: band.weight for band in SIZE_BANDS if band.weight is not None
}

# Bands too big to bundle on their own. `select` refuses these outright instead
# of weighting them, because a weight implies "fits alongside something
# smaller" and an XL PR does not.
UNBUNDLABLE_LABELS: frozenset[str] = frozenset(
    band.label for band in SIZE_BANDS if band.weight is None
)

# An unlabelled Issue is unmeasured, not small, so it counts as the largest
# *bundlable* size. Deliberately not the XL refusal: `size:` is on 91% of open
# Tasks, and making every unlabelled Issue unbundlable would fail closed on the
# remaining 9% rather than merely conservatively.
UNSIZED_WEIGHT: int = max(SIZE_WEIGHTS.values())

UNSIZED_LABEL = "unsized"


def _floors(
    ceilings: list[int | None], labels: tuple[str, ...]
) -> dict[str, int]:
    """Inclusive lower bounds derived from the ceiling above each band.

    A band's floor is one past the previous band's ceiling, so the ranges the
    table renders cannot disagree with the ranges it classifies by.
    """
    floors: dict[str, int] = {}
    previous: int | None = None
    for label, ceiling in zip(labels, ceilings, strict=False):
        floors[label] = 0 if previous is None else previous + 1
        if ceiling is not None:
            previous = ceiling
    return floors


_LINE_FLOORS = _floors([b.max_lines for b in SIZE_BANDS], SIZE_LABELS)
_AC_FLOORS = _floors([b.max_acs for b in SIZE_BANDS], SIZE_LABELS)


def band_for_diff(lines: int) -> SizeBand:
    """The band a PR of ``lines`` total changed lines falls in (PAD-05-002).

    ``lines`` is additions plus deletions across every changed file, unfiltered
    — the same number GitHub reports, because that is what the bands were
    calibrated against.
    """
    if lines < 0:
        raise ValueError(f"diff lines cannot be negative: {lines}")
    for band in SIZE_BANDS:
        if band.max_lines is None or lines <= band.max_lines:
            return band
    raise AssertionError("the last band must be unbounded")  # pragma: no cover


class DecompositionRequired(Exception):
    """An AC count past every estimate ceiling: split the Issue, label nothing.

    Not a ``ValueError``: the count is valid input, and the answer is a
    planning instruction rather than a band (PAD-05-013).
    """

    def __init__(self, count: int, ceiling: SizeBand) -> None:
        self.count = count
        self.ceiling = ceiling
        super().__init__(
            f"{count} acceptance criteria is past the {ceiling.label} ceiling "
            f"of {ceiling.max_acs}: decompose the Issue into smaller ones "
            "instead of labelling it"
        )


DECOMPOSE = "decompose"
"""What ``pr-size --acs`` prints in place of a label past the AC ceiling."""

DECOMPOSE_EXIT = 3
"""``pr-size``'s exit status for "decompose", so a capture is not a label."""


def _estimate_bands() -> tuple[SizeBand, ...]:
    return tuple(band for band in SIZE_BANDS if not band.measured_only)


def band_for_acs(count: int) -> SizeBand:
    """The band an Issue with ``count`` acceptance criteria estimates to.

    Only the estimate bands are reachable: ``size:XL`` is ``measured_only``.

    Raises:
        ValueError: If ``count`` is negative.
        DecompositionRequired: If ``count`` is past the last estimate band's
            AC ceiling, so the Issue should be split instead (PAD-05-013).
    """
    if count < 0:
        raise ValueError(f"AC count cannot be negative: {count}")
    estimable = _estimate_bands()
    for band in estimable:
        if band.max_acs is not None and count <= band.max_acs:
            return band
    raise DecompositionRequired(count, estimable[-1])


def weight_of(labels: list[str]) -> int:
    """The PAD-15-005 bundle weight for a candidate carrying ``labels``.

    The largest ``size:`` label wins, and no label at all counts as the largest
    bundlable size. An unbundlable label has no weight, so callers must check
    ``UNBUNDLABLE_LABELS`` before asking.
    """
    weights = [SIZE_WEIGHTS[name] for name in labels if name in SIZE_WEIGHTS]
    return max(weights) if weights else UNSIZED_WEIGHT


def markdown_table() -> str:
    """The band table as markdown, so prose can cite one rendering of it."""
    rows = [
        "| Label | Diff lines (measured, authoritative) | ACs (estimate) |"
        " Bundle weight |",
        "|---|---|---|---|",
    ]
    for band in SIZE_BANDS:
        weight = "never bundled" if band.weight is None else str(band.weight)
        rows.append(
            f"| `{band.label}` | {band.lines_range} | {band.acs_range} |"
            f" {weight} |"
        )
    return "\n".join(rows)


def _git(*args: str) -> str:
    """Run a read-only git command, raising with its own stderr on failure."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=repo_root(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"`git {' '.join(args)}` failed:\n{result.stderr.strip()}"
        )
    return result.stdout


def _untracked_lines() -> int:
    """Lines in files git does not track yet.

    New files are the normal shape of agent work and ``git diff`` cannot see
    them, so omitting them is how a branch that adds two modules measures as
    empty. Binary files contribute nothing, matching ``--numstat``.
    """
    root = repo_root()
    total = 0
    listing = _git("ls-files", "--others", "--exclude-standard", "-z")
    for name in listing.split("\0"):
        if not name:
            continue
        try:
            blob = (root / name).read_bytes()
        except OSError:
            continue
        if b"\0" in blob:
            continue
        total += blob.count(b"\n") + (0 if blob.endswith(b"\n") else 1)
    return total


def _diff_lines(base: str) -> int:
    """Lines this branch will contribute once everything is committed.

    Measured from the merge base to the **working tree**, not to ``HEAD``:
    committed, staged, unstaged and untracked changes all count. An agent asks
    for this before the commit exists, and `build` already warns that the
    ``base...HEAD`` form "may be empty if changes are unstaged" — a sizing tool
    that answers ``0`` for a branch full of uncommitted work is worse than no
    tool. After the commit lands the two forms agree, so the CI workflow's API
    numbers and this number describe the same diff.
    """
    try:
        merge_base = _git("merge-base", base, "HEAD").strip()
    except RuntimeError as exc:
        raise RuntimeError(
            f"cannot find the merge base with {base!r} — is it a known ref? "
            f"(`git fetch origin` may be needed)\n{exc}"
        ) from exc

    total = _untracked_lines()
    for line in _git("diff", "--numstat", merge_base).splitlines():
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        # Binary files report "-" for both counts; they contribute no lines.
        added, deleted = fields[0], fields[1]
        total += int(added) if added.isdigit() else 0
        total += int(deleted) if deleted.isdigit() else 0
    return total


def _estimate_measure(count: int) -> str:
    return f"{count} acceptance criteria (estimate)"


def _classify(args: argparse.Namespace) -> tuple[SizeBand, str]:
    """The band, plus the measurement that produced it in human words.

    Raises ``ValueError`` for out-of-range input and ``RuntimeError`` for an
    unusable git ref; ``main`` prints either verbatim, so the message a user
    sees is written where the failure is detected. An AC count past every
    estimate ceiling raises :class:`DecompositionRequired`.
    """
    if args.acs is not None:
        return (
            band_for_acs(args.acs),
            _estimate_measure(args.acs),
        )
    if args.lines is not None:
        lines = args.lines
    else:
        lines = _diff_lines(args.base or "origin/main")
    return band_for_diff(lines), f"{lines} diff lines (measured)"


DEFAULT_CALIBRATION_DAYS = 60
"""The ``--calibrate`` window when ``--days`` is not given."""


def calibration_scheme() -> BandScheme:
    """This table and its classifier, as ``--calibrate`` measures them."""
    return BandScheme(bands=SIZE_BANDS, classify=band_for_diff)


def calibrate(
    days: int,
    run: Runner = run_gh,
    now: datetime | None = None,
    repo: str = DEFAULT_REPO,
    git: GitRunner = run_git,
) -> str:
    """The calibration report for PRs merged in the last ``days`` days.

    Each bug-fix PR in the window is traced through ``git`` in this clone, so
    the clone needs the base branch fetched up to the window's end.

    Raises:
        ValueError: If ``days`` is not positive.
        GhError: If a ``gh`` response cannot be read.
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
        GitError: If a bug fix cannot be traced.
    """
    if days < 1:
        raise ValueError(f"--days must be at least 1, got {days}")
    until = now or datetime.now(UTC)
    data = fetch_window(repo, until - timedelta(days=days), until, run)
    prs = complete_commits(data.prs, git)
    data = replace(data, prs=prs, fix_traces=trace_fixes(prs, git))
    return render_report(data, calibration_scheme())


def _print_calibration(days: int) -> int:
    """Print the ``--calibrate`` report; exit 1 when ``gh`` or ``git`` fails."""
    try:
        print(calibrate(days))
    except GH_FAILURES as exc:
        print(f"❌ {gh_failure_detail(exc)}", file=sys.stderr)
        return 1
    except GitError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    return 0


def _report_band(args: argparse.Namespace) -> int:
    """Print the band for ``--base``, ``--lines`` or ``--acs``; the exit code.

    0 for a label, :data:`DECOMPOSE_EXIT` for "decompose", 2 for bad input.
    """
    try:
        band, measure = _classify(args)
    except DecompositionRequired as exc:
        if args.quiet:
            print(DECOMPOSE)
        else:
            print(f"{DECOMPOSE}  —  {_estimate_measure(exc.count)}")
            print(f"   {exc}. It takes no size: label.")
        return DECOMPOSE_EXIT
    except (ValueError, RuntimeError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if args.quiet:
        print(band.label)
    else:
        print(f"{band.label}  —  {measure}")
        if band.label in UNBUNDLABLE_LABELS:
            print(
                "   This PR is past the size where the CI-fix rate doubles "
                "(PAD-05-009). Split it, or say in the PR body why it cannot "
                "be split.",
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: report the ``size:`` band for a diff or an AC count."""
    parser = argparse.ArgumentParser(
        description=(
            "Report the size: label for a PR diff or an Issue's AC count. "
            "The band table lives in one place; do not restate it."
        )
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--base",
        metavar="REF",
        help=(
            "measure the merge base with REF against the working tree, so "
            "uncommitted and untracked work counts (default: origin/main)"
        ),
    )
    source.add_argument(
        "--lines", type=int, help="measure an already-known diff line count"
    )
    source.add_argument(
        "--acs",
        type=int,
        help=(
            "estimate from an acceptance-criteria count; a count past the "
            f"last estimate band prints {DECOMPOSE!r} and exits "
            f"{DECOMPOSE_EXIT}, with no label"
        ),
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="print the band table as markdown and exit",
    )
    parser.add_argument(
        "--labels-json",
        action="store_true",
        help="print label name/description/color as JSON and exit",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help=(
            "survey recent merged PRs against the band table, the AC rule, "
            "later bug fixes and heavy review (reads GitHub through gh and "
            "traces bug fixes with git blame in this clone) and exit"
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        metavar="N",
        help=(
            "with --calibrate, the window in days "
            f"(default: {DEFAULT_CALIBRATION_DAYS})"
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(f"print only the label (or {DECOMPOSE!r}), for shell capture"),
    )
    args = parser.parse_args(argv)
    if args.days is not None and not args.calibrate:
        parser.error("--days applies only with --calibrate")
    if args.days is not None and args.days < 1:
        parser.error(f"--days must be at least 1, got {args.days}")

    if args.calibrate:
        return _print_calibration(
            DEFAULT_CALIBRATION_DAYS if args.days is None else args.days
        )

    if args.table:
        print(markdown_table())
        return 0

    if args.labels_json:
        print(
            json.dumps(
                [
                    {
                        "name": band.label,
                        "description": band.description,
                        "color": LABEL_COLORS[band.label],
                    }
                    for band in SIZE_BANDS
                ],
                indent=2,
            )
        )
        return 0

    return _report_band(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
