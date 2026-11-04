"""Demo failure accumulator and the step/check/gate context managers (DEMOCI-01)."""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from collections.abc import Generator
from contextlib import contextmanager

from vultron.errors import DemoFailureError

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


# Module-level failure accumulator.  reset_demo_failures() clears it at the
# start of each scenario; assert_demo_success() raises DemoFailureError if
# any failures were recorded.  See specs/demo-ci.yaml DEMOCI-01-003.
_demo_failures: list[str] = []


def reset_demo_failures() -> None:
    """Clear the demo failure accumulator.

    Call at the start of each scenario entry point to ensure failures from a
    previous run do not pollute the current one.  See DEMOCI-01-003.
    """
    _demo_failures.clear()


def demo_failures() -> tuple[str, ...]:
    """The failures ``demo_step``, ``demo_check`` and ``demo_gate`` recorded.

    A read-only view, for the one caller that must know whether the run has
    already failed before it does work that depends on an act that may not
    have happened: a step mark whose role is read from the case cannot be
    checked when the act that granted the role failed
    (:func:`~vultron.demo.helpers.story.run_story`).  It is not a way to
    branch on failure elsewhere — a demo helper records and skips through
    ``demo_gate``, which keeps the first failure as the headline
    (DEMOCI-01-003).
    """
    return tuple(_demo_failures)


def assert_demo_success() -> None:
    """Raise DemoFailureError if any demo step or check failures were recorded.

    Call at the end of each scenario entry point.  Raises with the full list
    of accumulated failure messages so that ``docker compose --exit-code-from``
    can surface the non-zero exit to CI.  See DEMOCI-01-001, DEMOCI-01-003.
    """
    if _demo_failures:
        raise DemoFailureError(
            f"{len(_demo_failures)} demo failure(s)",
            failures=list(_demo_failures),
        )


def _note_accumulated_failures(exc: BaseException) -> None:
    """Attach any accumulated demo failures to *exc* as notes.

    On the failing path the caller lets the original exception propagate
    rather than calling ``assert_demo_success()``, which would replace the
    real cause with a generic ``DemoFailureError``.  The accumulated soft
    failures are still worth reporting, so they ride along as exception notes.
    """
    try:
        assert_demo_success()
    except DemoFailureError as accumulated:
        for failure in accumulated.failures:
            exc.add_note(failure)


@contextmanager
def _demo_accumulate(
    description: str,
    start: str,
    on_pass: str,
    on_fail: str,
    prefix: str,
) -> Generator[None, None, None]:
    """Shared try/except/log backbone for demo context managers.

    Logs *start* on entry, *on_pass* on clean exit, *on_fail* + exc on
    exception.  Exceptions are caught, logged, appended to
    ``_demo_failures`` as ``"<prefix>: <description> — <exc>"``, and
    suppressed so callers continue after the block.
    """
    logger.info("%s %s", start, description)
    try:
        yield
        logger.info("%s %s", on_pass, description)
    except Exception as exc:
        logger.exception("%s %s", on_fail, description)
        _demo_failures.append(f"{prefix}: {description} — {exc}")


@contextmanager
def demo_step(description: str) -> Generator[None, None, None]:
    """Context manager for declaring workflow steps in demo logs.

    Logs 🚥 at INFO on entry, 🟢 at INFO on clean exit, 🔴 at ERROR on
    exception.  On exception the failure is appended to the module-level
    ``_demo_failures`` accumulator and execution continues (no re-raise).
    Call ``assert_demo_success()`` at the end of the scenario to surface
    accumulated failures.  See DEMOCI-01-003, DEMOCI-01-004.
    """
    with _demo_accumulate(description, "🚥", "🟢", "🔴", "STEP FAILED"):
        yield


@contextmanager
def demo_check(description: str) -> Generator[None, None, None]:
    """Context manager for declaring side-effect checks in demo logs.

    Logs 📋 at INFO on entry, ✅ at INFO on clean exit, ❌ at ERROR on
    exception.  On exception the failure is appended to the module-level
    ``_demo_failures`` accumulator and execution continues (no re-raise).
    Call ``assert_demo_success()`` at the end of the scenario to surface
    accumulated failures.  See DEMOCI-01-003, DEMOCI-01-004.
    """
    with _demo_accumulate(description, "📋", "✅", "❌", "CHECK FAILED"):
        yield


@contextmanager
def demo_gate(description: str) -> Generator[None, None, None]:
    """Context manager for causal preconditions in demo scripts.

    Place the precondition check **and the steps that depend on it** inside
    this block.  If the precondition raises, Python immediately exits the
    ``with`` body — the remaining dependent steps are skipped.  The failure
    is recorded in the accumulator exactly as ``demo_check`` does
    (DEMOCI-01-003 is preserved), and the exception is suppressed so that
    execution continues *after* the block.

    **Scoping model — nested block**:

    Put the gating assertion at the top of the body, followed directly by
    the dependent steps:

    ```python
    with demo_gate("vendor has reached RM.VALID"):
        assert vendor_rm_state == "VALID"    # precondition: raises on fail
        with demo_step("5. Engage case"):    # skipped when gate fails
            engage_case(...)
        with demo_step("6. Do next thing"):  # also skipped when gate fails
            do_next(...)
    # code here always runs — gate accumulates and suppresses the failure
    ```

    Use ``demo_check`` for a standalone verification assertion that should
    *not* block subsequent steps.  Use ``demo_gate`` when continuing after a
    failed precondition would produce meaningless secondary failures that bury
    the real cause.

    See DEMOCI-01-007, EDF-06-005, ADR-0058.
    """
    with _demo_accumulate(description, "🚧", "🔓", "🔒", "GATE FAILED"):
        yield
