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

"""Shared scenario harness: run phases, always dump ledgers, then assert.

Every ``run_*_demo()`` used to end with a plain call to its
``_phase_dump_case_ledgers``. That made the forensic dump conditional on the
scenario succeeding: an assertion escaping any earlier phase — an unguarded
``wait_for_*`` timeout, say — skipped the dump, while ``main()``'s
``assert_demo_success()`` still failed the job. The demo therefore failed with
an empty ``devlogs/`` directory and the invariant-harness job died on artifact
download, reporting nothing about the protocol (ISSUE-2239).

:func:`scenario_harness` fixes the shape rather than the nine call sites. It
owns the order the whole demo suite needs (DEMOMA-23-001):

1. reset the failure accumulator,
2. run the phases,
3. **always** dump the ledgers — in a ``finally``, guarded so a dump error can
   never replace the exception that caused the failure,
4. assert success.

Usage from a scenario module::

    def run_rvv_demo(...) -> None:
        with scenario_harness("rvv") as harness:
            reporter, vendor, ..., case = _phase_report_submission(...)
            harness.dump_with(
                lambda: _phase_dump_case_ledgers(
                    reporter_client=reporter_client, ..., case=case
                )
            )
            _phase_sync_verification(...)
            ...

The dump is registered as a callable the moment the case exists, so any later
phase can die and the harness still has something to dump. Before that point
the harness writes a manifest-only artifact, which is enough for the invariant
harness to distinguish "the demo produced no ledgers" from "the demo never
ran".

**Step marks.** A scenario also reports reaching each step of its declared
path (``@scenario(path=...)``) with :meth:`ScenarioHarness.reach_step`, at the
point where it makes that decision.  The harness checks the step is the next
one declared and records the canonical ledger's tail there: how many entries
the case had when the decision was made.  The marks are written beside the
dump manifest on the way out, however the scenario ends, and the recorder
commits them with each recording so the shared-prefix check knows where each
branch point falls (DEMOCI-11-017, ``notes/demo-scenario-tree.md``)::

    with scenario_harness("rv") as harness:
        harness.reach_step("reporter-whom-to-tell", "vendor")
        ..., case = _phase_report_submission(...)
        harness.follow_ledger(case_actor_client, case.id_)
        ...
        harness.reach_step("vendor-after-answer", "report-fix-ready")

A step that falls inside a phase function is reported with the module-level
:func:`reach_step` (and the ledger followed with :func:`follow_ledger`), which
go to the harness of the scenario running now, so a phase does not take the
harness as a parameter.  Outside a harness, a phase called directly by a test
for example, both do nothing: the marks belong to a scenario run, and the
recorder refuses a run whose marks do not cover its declared path.
"""

import json
import logging
import pathlib
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from vultron.demo.helpers.ledger_dump import (
    STEP_MARKS_FILENAME,
    LedgerDumpReport,
    case_ledger_length,
    ensure_dump_manifest,
    resolve_output_root,
    write_dump_manifest,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.scenario.tree import PathStep
from vultron.demo.utils import (
    DataLayerClient,
    _note_accumulated_failures,
    assert_demo_success,
    demo_step,
    reset_demo_failures,
)
from vultron.errors import DemoScenarioStepError

logger = logging.getLogger(__name__)

NO_CASE_REASON = (
    "The scenario failed before a case existed, so no participant ledgers "
    "could be exported."
)

DUMP_CRASHED_REASON = (
    "The case-ledger dump raised before it could record per-actor results."
)


@dataclass(frozen=True)
class StepMark:
    """Where one declared step of a scenario's path fell in its case ledger.

    Attributes:
        branch_point: The branch point decided at this step.
        choice: The choice the scenario takes there.
        ledger_tail: How many entries the canonical ledger held when the
            scenario reached the step; ``0`` before the case exists.
    """

    branch_point: str
    choice: str
    ledger_tail: int

    def as_json(self) -> dict[str, str | int]:
        """Return the mark in the camelCase shape the recordings use."""
        return {
            "branchPoint": self.branch_point,
            "choice": self.choice,
            "ledgerTail": self.ledger_tail,
        }


@dataclass
class ScenarioHarness:
    """Per-run state shared between a scenario body and its harness.

    Attributes:
        demo_name: Scenario name; the devlogs sub-directory the dump writes to.
        dump: Zero-argument callable that performs the ledger dump, or ``None``
            while the scenario has not reached a dumpable state yet.
        marks: The steps reached so far, in order (:meth:`reach_step`).
    """

    demo_name: str
    dump: Callable[[], None] | None = None
    marks: list[StepMark] = field(default_factory=list)
    _ledger: tuple[DataLayerClient, str] | None = field(
        default=None, init=False, repr=False
    )

    def dump_with(self, dump: Callable[[], None]) -> None:
        """Register the ledger dump to run when the scenario ends.

        Call this as soon as the case and its participants exist — before the
        phases that might fail — so a mid-scenario failure still yields the
        ledgers collected so far.

        Args:
            dump: Callable invoked by the harness on the way out, however the
                scenario ends.
        """
        self.dump = dump

    def follow_ledger(
        self, case_actor_client: DataLayerClient, case_id: str
    ) -> None:
        """Read step marks from this case's canonical ledger from now on.

        Call this as soon as the case exists, with the dedicated case-actor
        container's client, which holds the canonical ledger (DEMOMA-06-005).

        Args:
            case_actor_client: Client bound to the CaseActor.
            case_id: The case whose ledger tail each later step records.
        """
        self._ledger = (case_actor_client, case_id)

    def reach_step(self, branch_point: str, choice: str) -> None:
        """Report that the scenario is at a declared step of its path.

        Call it where the scenario makes the decision, before the choice's
        trigger and before any step of another role that runs between the two
        (DEMOCI-11-013).  The harness records the canonical ledger's tail as
        the step's mark.

        Args:
            branch_point: The branch point decided here.
            choice: The choice this scenario takes.

        Raises:
            DemoScenarioStepError: When ``(branch_point, choice)`` is not the
                next step of the scenario's declared path, or when a step
                after the first is reached before :meth:`follow_ledger`.
        """
        path = _declared_path(self.demo_name)
        index = len(self.marks)
        step = (branch_point, choice)
        if index >= len(path) or path[index] != step:
            expected = (
                f"step {index + 1} is {path[index]}"
                if index < len(path)
                else f"all {len(path)} steps were already reached"
            )
            raise DemoScenarioStepError(
                f"scenario {self.demo_name!r} reached {step}, but its declared "
                f"path says {expected}. Fix the reach_step() call or the "
                "@scenario path (DEMOCI-11-014)."
            )
        if self._ledger is None and index > 0:
            raise DemoScenarioStepError(
                f"scenario {self.demo_name!r} reached {step} before following "
                "a case ledger; call harness.follow_ledger() once the case "
                "exists, so the step's mark is its ledger tail."
            )
        tail = 0 if self._ledger is None else case_ledger_length(*self._ledger)
        self.marks.append(StepMark(branch_point, choice, tail))
        logger.info(
            "%s reached step %d %s:%s at ledger tail %d",
            self.demo_name,
            index + 1,
            branch_point,
            choice,
            tail,
        )


#: The harness of the scenario running now, set by :func:`scenario_harness`.
_ACTIVE: ContextVar["ScenarioHarness | None"] = ContextVar(
    "active_scenario_harness", default=None
)


def reach_step(branch_point: str, choice: str) -> None:
    """Report a declared step to the running scenario's harness.

    As :meth:`ScenarioHarness.reach_step`; does nothing outside
    :func:`scenario_harness`.
    """
    harness = _ACTIVE.get()
    if harness is None:
        logger.debug(
            "No scenario harness is running; step %s:%s is not recorded",
            branch_point,
            choice,
        )
        return
    harness.reach_step(branch_point, choice)


def follow_ledger(case_actor_client: DataLayerClient, case_id: str) -> None:
    """Have the running scenario's harness follow this case's ledger.

    As :meth:`ScenarioHarness.follow_ledger`; does nothing outside
    :func:`scenario_harness`.
    """
    harness = _ACTIVE.get()
    if harness is not None:
        harness.follow_ledger(case_actor_client, case_id)


def step_reporter(branch_point: str, choice: str) -> Callable[[], None]:
    """Return a callable that reports this step when a helper calls it.

    For a step that falls inside a shared helper, which cannot know the
    scenario's branch points: the scenario passes the callable as the
    helper's hook (``on_invited=step_reporter("vendor-join", "accept")``).
    """

    def report() -> None:
        reach_step(branch_point, choice)

    return report


def _declared_path(demo_name: str) -> tuple[PathStep, ...]:
    """Return the ``@scenario`` path of *demo_name*.

    Raises:
        DemoScenarioStepError: When no scenario of that name is registered.
    """
    for spec in registered_scenarios():
        if spec.name == demo_name:
            return spec.path
    raise DemoScenarioStepError(
        f"no registered scenario is named {demo_name!r}, so it has no "
        "declared path to reach a step on."
    )


def write_step_marks(
    demo_name: str,
    marks: list[StepMark],
    output_root: pathlib.Path | None = None,
) -> pathlib.Path:
    """Write *marks* to ``{output_root}/{demo_name}/step-marks.json``.

    Args:
        demo_name: Scenario name; the devlogs sub-directory.
        marks: The steps reached, in order.
        output_root: Devlogs root; defaults to ``DEVLOGS_DIR``.

    Returns:
        Path to the file written.
    """
    out_dir = resolve_output_root(output_root) / demo_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / STEP_MARKS_FILENAME
    path.write_text(
        json.dumps({"steps": [mark.as_json() for mark in marks]}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return path


def _record_marks(harness: ScenarioHarness) -> None:
    """Write the harness's step marks, never raising.

    Runs on the way out however the scenario ends, beside the dump, and for
    the same reason must not replace the scenario's own exception.
    """
    try:
        write_step_marks(harness.demo_name, harness.marks)
    except BaseException:
        logger.exception(
            "Could not write the step marks of the %s demo; reporting the "
            "scenario's own outcome instead",
            harness.demo_name,
        )


def _backstop_manifest(demo_name: str) -> None:
    """Write the fallback manifest for *demo_name*, swallowing any error.

    ``dump_case_ledgers`` writes its own manifest from a ``finally``, so this
    backstop only fires when the dump died before getting that far. Writing it
    unconditionally would stamp the "dump crashed" reason onto runs whose dump
    was fine.

    It must not raise: it runs while the dump's own exception is in flight, and
    an error here would replace that exception with a less informative one
    (DEMOCI-10-004).
    """
    try:
        ensure_dump_manifest(demo_name, DUMP_CRASHED_REASON)
    except BaseException:
        logger.exception(
            "Could not write the fallback dump manifest for the %s demo; "
            "reporting the dump's own failure instead",
            demo_name,
        )


def _run_dump(harness: ScenarioHarness) -> None:
    """Dump ledgers, guaranteeing a manifest and never raising.

    The dump runs inside ``demo_step``, which records the failure and continues
    (DEMOCI-01-003). That is what makes this safe to call from a ``finally``:
    the accumulated failure is still reported, but it cannot mask the exception
    that ended the scenario.

    Every path — including the manifest-only path taken when no dump was ever
    registered, and a ``BaseException`` that ``demo_step`` does not catch — is
    contained here. ``_run_dump`` never propagates, because its caller still
    has the scenario's own exception to re-raise (DEMOCI-10-004,
    DEMOMA-23-004).
    """
    try:
        if harness.dump is None:
            with demo_step(
                f"Recording the {harness.demo_name} dump manifest "
                "(no case to export)"
            ):
                write_dump_manifest(
                    LedgerDumpReport(
                        demo_name=harness.demo_name, reason=NO_CASE_REASON
                    )
                )
            return

        with demo_step(
            f"Dumping case ledgers for the {harness.demo_name} demo"
        ):
            try:
                harness.dump()
            except BaseException:
                _backstop_manifest(harness.demo_name)
                raise
    except BaseException:
        # ``demo_step`` already recorded anything deriving from ``Exception``;
        # this only catches what it lets through (``KeyboardInterrupt``,
        # ``SystemExit``). Either way the scenario's own outcome is the one
        # worth reporting, so the dump's failure stops here.
        logger.exception(
            "Case-ledger dump for the %s demo failed; reporting the "
            "scenario's own outcome instead",
            harness.demo_name,
        )


@contextmanager
def scenario_harness(
    demo_name: str,
) -> Generator[ScenarioHarness, None, None]:
    """Run a scenario body with an always-executed case-ledger dump.

    Args:
        demo_name: Scenario name, e.g. ``"rvv"``. Becomes the devlogs
            sub-directory the dump and manifest are written to.

    Yields:
        The :class:`ScenarioHarness` the body registers its dump with.

    Raises:
        DemoFailureError: When the body completed but ``demo_step`` or
            ``demo_check`` recorded failures.
        BaseException: Whatever the body raised, unchanged — the dump runs
            first but never substitutes its own error for the body's.
    """
    reset_demo_failures()
    harness = ScenarioHarness(demo_name=demo_name)
    token = _ACTIVE.set(harness)
    try:
        yield harness
    except BaseException as exc:
        logger.error(  # noqa: TRY400  # ruff-baseline #3353
            "%s demo failed mid-run; dumping case ledgers before propagating",
            demo_name,
        )
        _run_dump(harness)
        _record_marks(harness)
        _note_accumulated_failures(exc)
        raise
    finally:
        _ACTIVE.reset(token)
    _run_dump(harness)
    _record_marks(harness)
    assert_demo_success()
