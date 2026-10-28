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

"""The ``export-demo-recordings`` command."""

import logging
from collections.abc import Sequence

import click

from vultron.demo.recordings import layout
from vultron.demo.recordings.runner import record_scenario
from vultron.demo.recordings.topology import load_topology
from vultron.demo.scenario.registry import discover_scenarios

#: The command that regenerates the recordings; named when ``--check`` finds a
#: layout problem.
REGENERATE_COMMAND = "uv run export-demo-recordings"

#: ``--report-changes`` exit status when a run changed a committed recording.
#: Distinct from 1, a failed run, so the scheduled workflow can tell a stale
#: recording (file a refresh Task) from a broken recorder (a CI failure).
CHANGED_EXIT_CODE = 3


@click.command(name="export-demo-recordings")
@click.option(
    "--scenario",
    "scenarios",
    multiple=True,
    help="Record only this scenario (repeatable). Default: every scenario.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Run nothing; fail when the set of recorded scenarios is not the "
    "registry's.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="ERROR",
    show_default=True,
    help="Log level of the scenario runs. Below ERROR, the in-process "
    "harness's known shared-store warnings are shown too.",
)
@click.option(
    "--report-changes",
    is_flag=True,
    help=f"Exit {CHANGED_EXIT_CODE} when the run changed a committed "
    "recording, after writing it; list the changed scenarios.",
)
def main(
    scenarios: tuple[str, ...],
    check: bool,
    log_level: str,
    report_changes: bool,
) -> None:
    """Record every registered demo scenario into ui/src/recordings/."""
    logging.basicConfig(level=log_level)
    specs = {spec.name: spec for spec in discover_scenarios()}
    if check:
        if scenarios:
            raise click.UsageError(
                "--check compares the whole recorded set with the registry; "
                "it takes no --scenario."
            )
        _check_layout(tuple(specs))
        return
    unknown = sorted(set(scenarios) - set(specs))
    if unknown:
        raise click.BadParameter(
            f"not registered: {', '.join(unknown)}", param_hint="--scenario"
        )
    changed = [] if scenarios else layout.remove_unregistered(set(specs))
    topology = load_topology()
    for name in scenarios or tuple(specs):
        recording = record_scenario(specs[name], topology)
        path = layout.recording_path(name)
        if not path.is_file() or path.read_text(encoding="utf-8") != recording:
            changed.append(name)
        layout.write_recording(name, recording)
        click.echo(f"Wrote {path.relative_to(layout.REPO_ROOT)}")
    if report_changes and changed:
        click.echo(f"Changed recordings: {', '.join(changed)}")
        raise SystemExit(CHANGED_EXIT_CODE)


def _check_layout(scenario_names: Sequence[str]) -> None:
    """Report each layout problem; exit 1 when there is one."""
    problems = layout.layout_problems(scenario_names)
    for problem in problems:
        click.echo(f"ui/src/recordings/{problem}", err=True)
    if problems:
        click.echo(f"Regenerate with: {REGENERATE_COMMAND}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
