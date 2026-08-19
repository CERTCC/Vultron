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

    def run_fvv_demo(...) -> None:
        with scenario_harness("fvv") as harness:
            finder, vendor, ..., case = _phase_report_submission(...)
            harness.dump_with(
                lambda: _phase_dump_case_ledgers(
                    finder_client=finder_client, ..., case=case
                )
            )
            _phase_sync_verification(...)
            ...

The dump is registered as a callable the moment the case exists, so any later
phase can die and the harness still has something to dump. Before that point
the harness writes a manifest-only artifact, which is enough for the invariant
harness to distinguish "the demo produced no ledgers" from "the demo never
ran".
"""

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Generator

from vultron.demo.helpers.ledger_dump import (
    LedgerDumpReport,
    ensure_dump_manifest,
    write_dump_manifest,
)
from vultron.demo.utils import (
    _note_accumulated_failures,
    assert_demo_success,
    demo_step,
    reset_demo_failures,
)

logger = logging.getLogger(__name__)

NO_CASE_REASON = (
    "The scenario failed before a case existed, so no participant ledgers "
    "could be exported."
)

DUMP_CRASHED_REASON = (
    "The case-ledger dump raised before it could record per-actor results."
)


@dataclass
class ScenarioHarness:
    """Per-run state shared between a scenario body and its harness.

    Attributes:
        demo_name: Scenario name; the devlogs sub-directory the dump writes to.
        dump: Zero-argument callable that performs the ledger dump, or ``None``
            while the scenario has not reached a dumpable state yet.
    """

    demo_name: str
    dump: Callable[[], None] | None = None

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
        demo_name: Scenario name, e.g. ``"fvv"``. Becomes the devlogs
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
    try:
        yield harness
    except BaseException as exc:
        logger.error(
            "%s demo failed mid-run; dumping case ledgers before propagating",
            demo_name,
        )
        _run_dump(harness)
        _note_accumulated_failures(exc)
        raise
    _run_dump(harness)
    assert_demo_success()
