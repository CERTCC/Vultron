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
    assert_demo_success,
    demo_step,
    reset_demo_failures,
)
from vultron.errors import DemoFailureError

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


def _run_dump(harness: ScenarioHarness) -> None:
    """Dump ledgers, guaranteeing a manifest and never raising.

    The dump runs inside ``demo_step``, which records the failure and continues
    (DEMOCI-01-003). That is what makes this safe to call from a ``finally``:
    the accumulated failure is still reported, but it cannot mask the exception
    that ended the scenario.
    """
    if harness.dump is None:
        write_dump_manifest(
            LedgerDumpReport(
                demo_name=harness.demo_name, reason=NO_CASE_REASON
            )
        )
        return

    with demo_step(f"Dumping case ledgers for the {harness.demo_name} demo"):
        try:
            harness.dump()
        except BaseException:
            # ``dump_case_ledgers`` writes its own manifest from a ``finally``,
            # so this backstop only fires when the dump died before getting
            # that far. Writing it unconditionally would stamp the "dump
            # crashed" reason onto runs whose dump was fine.
            ensure_dump_manifest(harness.demo_name, DUMP_CRASHED_REASON)
            raise


def _note_accumulated_failures(exc: BaseException) -> None:
    """Attach any accumulated demo failures to *exc* as notes.

    On the failing path the harness lets the original exception propagate
    rather than calling ``assert_demo_success()``, which would replace the real
    cause with a generic ``DemoFailureError``. The accumulated soft failures
    are still worth reporting, so they ride along as exception notes.
    """
    try:
        assert_demo_success()
    except DemoFailureError as accumulated:
        for failure in accumulated.failures:
            exc.add_note(failure)


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
