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

"""The ``compare-demo-runs`` command: one scenario's two runs, both traces.

A change that extracts or merges demo code is a consolidation, so no
scenario's pass or fail may move in it (DEMOMA-17-002).  What a scenario
passes or fails on is its protocol acts **and** its checks, and a recording
holds only the acts: a ``demo_check`` moved out of its ``demo_gate``, or a
wait that reads another actor's replica, leaves the recording byte-identical
(#5596).  The evidence is therefore each scenario recorded twice — once at a
pull request's base and once at its head — and compared on its normalized
ledger *and* its check tree (DEMOCI-11-055).

Three forms:

- ``--write DIR`` records the selected scenarios and writes each run's two
  traces under ``DIR/<scenario>/``.  ``demo-verdict.yml`` calls it once per
  commit, and a person reading a difference before pushing calls it the same
  way, as ``notes/demo-scenario-tree.md`` § "Composition" describes.
- ``--base DIR --head DIR`` compares two directories ``--write`` left.
- Neither records each selected scenario **twice in this process** and
  compares the pair.  That is the recorder's own determinism check: two runs
  of one unchanged tree differ in nothing.

Nothing is committed either way (#3901).

Exit status:

- ``0`` — every compared scenario agrees, or one differed and
  ``--allow-difference`` was given.
- :data:`DIFFERENT_EXIT_CODE` — at least one scenario differs, with its
  per-scenario diff printed (DEMOCI-11-061).  Its own code rather than ``1``,
  which is what a crashed recorder exits with: a caller keying its
  ``demo-verdict-change`` opt-out on "non-zero" would otherwise excuse a
  broken run as a deliberate verdict change, the collision the sibling
  command avoided the same way.
- :data:`NO_SCENARIOS_EXIT_CODE` — the run compared no scenario at all.  A
  blocking gate reports an empty target set as its own failure rather than as
  success (DEMOCI-11-062, DF-09-009).

``--allow-difference`` is the input a job passes exactly when its pull request
carries the ``demo-verdict-change`` label: the differences are still printed,
so the opt-out shows what it admits, and the command exits zero
(DEMOCI-11-063, DEMOCI-11-064).  Which pull requests get it is the job's
business (#6026).

Design: ``notes/demo-scenario-tree.md`` § "Composition".
"""

import difflib
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import click

from vultron.demo.recordings.runner import record_scenario
from vultron.demo.recordings.selection import select_scenarios
from vultron.demo.recordings.topology import load_topology
from vultron.demo.recordings.traces import (
    NormalizedRun,
    ScenarioRun,
    normalize_run,
    prune_runs,
    read_runs,
    write_run,
)
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios

#: Exit status when a scenario's two runs differ.  Not ``1``: click exits ``1``
#: on an uncaught exception, which is what a scenario that fails to run gives,
#: and not ``2``, which click uses for a usage error.
DIFFERENT_EXIT_CODE = 4

#: Exit status when the run compared no scenario.  Distinct from a difference,
#: so a caller can tell "the gate ran and found a change" from "the gate ran
#: over nothing" (DEMOCI-11-062, DF-09-009).
NO_SCENARIOS_EXIT_CODE = 3

#: What a one-sided scenario's missing run reads as in its diff.
MISSING_RUN = "(not recorded)"


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    """One scenario's base run against its head run, trace by trace.

    Attributes:
        scenario: The scenario name.
        ledger: The unified diff of the two normalized ledgers, empty when
            they agree.
        checks: The unified diff of the two normalized check trees, empty when
            they agree.
    """

    scenario: str
    ledger: tuple[str, ...]
    checks: tuple[str, ...]

    @property
    def differs(self) -> bool:
        """Whether either trace differs."""
        return bool(self.ledger or self.checks)

    def report(self) -> str:
        """The per-scenario difference, as a person reads it."""
        parts = [f"{self.scenario}: the two runs differ"]
        for trace, diff in (("ledger", self.ledger), ("checks", self.checks)):
            if diff:
                parts.append(f"--- {self.scenario} {trace} ---")
                parts.extend(diff)
        return "\n".join(parts)


def _diff(
    scenario: str, trace: str, base: Sequence[str], head: Sequence[str]
) -> tuple[str, ...]:
    """The unified diff of one trace, or empty when the two agree."""
    return tuple(
        difflib.unified_diff(
            list(base),
            list(head),
            fromfile=f"base/{scenario}/{trace}",
            tofile=f"head/{scenario}/{trace}",
            lineterm="",
        )
    )


def _missing(scenario: str) -> NormalizedRun:
    """The stand-in for a side that holds no run of *scenario*.

    A scenario recorded on one side only is reported as a difference rather
    than skipped: a scenario added or dropped between base and head is exactly
    the kind of change the gate exists to show, and a side that holds no run
    for it is not evidence that nothing moved.
    """
    return NormalizedRun(
        scenario, ledger=(MISSING_RUN,), checks=(MISSING_RUN,)
    )


def _compare(
    scenario: str, before: NormalizedRun, after: NormalizedRun
) -> ScenarioComparison:
    """Diff one scenario's two normalized runs, on both traces."""
    return ScenarioComparison(
        scenario=scenario,
        ledger=_diff(scenario, "ledger", before.ledger, after.ledger),
        checks=_diff(scenario, "checks", before.checks, after.checks),
    )


def compare_runs(
    base: Mapping[str, ScenarioRun], head: Mapping[str, ScenarioRun]
) -> list[ScenarioComparison]:
    """Compare each scenario's base run with its head run, on both traces.

    Every scenario either side holds is compared, in name order, so no
    scenario is held out of the comparison.

    Raises:
        DemoRecordingError: When a run's ledger is not readable as entries.
    """
    comparisons: list[ScenarioComparison] = []
    for scenario in sorted(set(base) | set(head)):
        # A side that holds no run of this scenario stands in as `_missing`,
        # so one call shape covers both sides present and either side absent.
        before = (
            normalize_run(base[scenario])
            if scenario in base
            else _missing(scenario)
        )
        after = (
            normalize_run(head[scenario])
            if scenario in head
            else _missing(scenario)
        )
        comparisons.append(_compare(scenario, before, after))
    return comparisons


def _record(
    specs: Mapping[str, ScenarioSpec], label: str
) -> dict[str, ScenarioRun]:
    """Record each of *specs* in this process, reporting each one's wall time.

    *label* names which side of the comparison this pass is, so the wall time
    a caller reports can be read per pass.
    """
    topology = load_topology()
    runs: dict[str, ScenarioRun] = {}
    for name, spec in specs.items():
        started = time.monotonic()
        runs[name] = record_scenario(spec, topology).traces
        click.echo(
            f"Recorded {name} ({label}) in {time.monotonic() - started:.1f}s"
        )
    return runs


@click.command(name="compare-demo-runs")
@click.option(
    "--scenario",
    "scenarios",
    multiple=True,
    help="Record or compare only this scenario (repeatable). Default: every "
    "registered scenario.",
)
@click.option(
    "--write",
    "write_to",
    type=click.Path(file_okay=False, path_type=Path),
    help="Record the selected scenarios and write each run's two traces "
    "under this directory, then exit. Compares nothing.",
)
@click.option(
    "--base",
    "base_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="The directory a --write pass left at the pull request's base.",
)
@click.option(
    "--head",
    "head_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="The directory a --write pass left at the pull request's head.",
)
@click.option(
    "--allow-difference",
    is_flag=True,
    help="Print the differences but exit zero. The input a job passes exactly "
    "when its pull request carries the demo-verdict-change label.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="ERROR",
    show_default=True,
    help="Log level of the scenario runs.",
)
def main(
    scenarios: tuple[str, ...],
    write_to: Path | None,
    base_dir: Path | None,
    head_dir: Path | None,
    allow_difference: bool,
    log_level: str,
) -> None:
    """Compare each demo scenario's base and head runs on ledger and checks.

    With no directory option, records each selected scenario twice in this
    process and compares the pair, which is the recorder's own determinism
    check.
    """
    logging.basicConfig(level=log_level)
    _refuse_a_bad_combination(write_to, base_dir, head_dir, allow_difference)
    started = time.monotonic()
    try:
        if write_to is not None:
            _write(write_to, scenarios)
            return
        if base_dir is not None and head_dir is not None:
            base, head = _written_pair(base_dir, head_dir, scenarios)
        else:
            base, head = _recorded_pair(scenarios)
        _report(compare_runs(base, head), allow_difference=allow_difference)
    finally:
        # In a `finally`, so the run a reader most wants timed — the one that
        # found a difference — is not the one that reports no time.
        click.echo(f"Total wall time: {time.monotonic() - started:.1f}s")


def _refuse_a_bad_combination(
    write_to: Path | None,
    base_dir: Path | None,
    head_dir: Path | None,
    allow_difference: bool,
) -> None:
    """Refuse an option combination that would compare nothing real."""
    if write_to is not None and (base_dir or head_dir):
        raise click.UsageError(
            "--write records one side; it does not compare, so it takes "
            "neither --base nor --head."
        )
    if write_to is not None and allow_difference:
        raise click.UsageError(
            "--write compares nothing, so there is no difference for "
            "--allow-difference to admit. Pass it to the comparison run."
        )
    if (base_dir is None) != (head_dir is None):
        raise click.UsageError(
            "a comparison needs both --base and --head; pass neither to "
            "record both sides in this process."
        )
    if (
        base_dir is not None
        and head_dir is not None
        and base_dir.resolve() == head_dir.resolve()
    ):
        raise click.UsageError(
            "--base and --head name one directory, so every scenario would "
            "be compared with itself and nothing could fail. Write each side "
            "to its own directory."
        )


def _registered(scenarios: tuple[str, ...]) -> dict[str, ScenarioSpec]:
    """The selected registered scenarios, refusing an empty selection."""
    specs = select_scenarios(
        {spec.name: spec for spec in discover_scenarios()}, scenarios
    )
    if not specs:
        _no_scenarios("No scenario was selected, so none was recorded.")
    return specs


def _write(write_to: Path, scenarios: tuple[str, ...]) -> None:
    """Record one side and write its traces, pruning any stale run there."""
    specs = _registered(scenarios)
    # Pruned *before* the recording, not after: a pass that dies part-way
    # records nothing and would otherwise leave every earlier run in place,
    # which the comparison then reads as this side's current evidence. Clearing
    # them first makes a failed pass leave a side with nothing to compare,
    # which `read_runs` reports as an empty set rather than as no difference.
    for stale in prune_runs(write_to, keep=set(specs)):
        click.echo(f"Removed the stale run of {stale}")
    runs = _record(specs, "write")
    for run in runs.values():
        click.echo(f"Wrote {write_run(run, write_to)}")


def _written_pair(
    base_dir: Path, head_dir: Path, scenarios: tuple[str, ...]
) -> tuple[dict[str, ScenarioRun], dict[str, ScenarioRun]]:
    """Read two written sides, narrowed by an explicit ``--scenario`` only.

    A name is checked against what the pair holds rather than against the
    registry: narrowing by the registry would drop a scenario the head commit
    retired, which is a change the gate exists to show, and would refuse a
    ``--scenario`` naming it outright.
    """
    base, head = read_runs(base_dir), read_runs(head_dir)
    if not scenarios:
        return base, head
    unknown = sorted(set(scenarios) - set(base) - set(head))
    if unknown:
        raise click.BadParameter(
            f"not recorded on either side: {', '.join(unknown)}",
            param_hint="--scenario",
        )
    return (
        {n: run for n, run in base.items() if n in scenarios},
        {n: run for n, run in head.items() if n in scenarios},
    )


def _recorded_pair(
    scenarios: tuple[str, ...],
) -> tuple[dict[str, ScenarioRun], dict[str, ScenarioRun]]:
    """Record each selected scenario twice in this process."""
    specs = _registered(scenarios)
    return _record(specs, "first"), _record(specs, "second")


def _no_scenarios(what_happened: str) -> NoReturn:
    """Report an empty target set as this command's own distinct failure."""
    click.echo(
        f"{what_happened} A gate that reports an empty target set as success "
        "checks nothing (DEMOCI-11-062, DF-09-009).",
        err=True,
    )
    raise SystemExit(NO_SCENARIOS_EXIT_CODE)


def _report(
    comparisons: Sequence[ScenarioComparison], *, allow_difference: bool
) -> None:
    """Print each scenario's verdict and exit on an empty set or a difference."""
    if not comparisons:
        _no_scenarios("No scenario was compared.")
    different = [one for one in comparisons if one.differs]
    for one in different:
        click.echo(one.report())
    for one in comparisons:
        if not one.differs:
            click.echo(f"{one.scenario}: unchanged")
    if different:
        named = ", ".join(one.scenario for one in different)
        if allow_difference:
            # The differences are printed above either way, so the opt-out
            # shows what it admits (DEMOCI-11-064).
            click.echo(f"Differing scenarios admitted by request: {named}")
            return
        click.echo(f"Differing scenarios: {named}", err=True)
        raise SystemExit(DIFFERENT_EXIT_CODE)
    click.echo(f"{len(comparisons)} scenario(s) compared, none differ.")


if __name__ == "__main__":
    main()
