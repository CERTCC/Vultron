"""ADR lifecycle epochs and the checks built on them (ADR-0120).

Requirements: specs/meta-specifications.yaml MS-14-007 through MS-14-010,
MS-14-012, MS-14-019 through MS-14-022, MS-14-024 through MS-14-026,
MS-14-029 and MS-14-030.

An ADR's ``status`` tracks how settled the decision is. Two timers measured
from the last *material* edit (``updated``) and one event decide its epoch:

- epoch 1, ``proposed``: until day 14, or until the first test-verified
  dependent, whichever comes first
- epoch 2, ``accepted-provisional``: from then until day 28
- epoch 3, ``accepted``: day 28 on

A test-verified dependent is a spec requirement that cites the ADR in ``adr:``
and whose ``verification:`` names a ``test/`` file that exists, counted in the
tree being checked (the pull request's head, or ``main`` for the scheduled
report). A material edit restarts the timers but not the dependency. ``updated``
is a date, so the boundaries are counted in whole days.

The computed epoch is a floor: a status ahead of it stands, and a status only
moves forward (MS-14-012). A human may hold a status off its epoch with
``status_override: <reason>``. Retired and rejected ADRs have no epoch.

The clock alone never fails a merge-blocking check: nothing in the repository
changes when an ADR crosses an epoch boundary, so a check that reads today's
date would turn ``main`` red with no commit to blame. Two checks live here:

- :func:`check_change` compares the working tree with a base commit. It
  refuses the edits the epochs forbid (:func:`edit_faults`): a material edit
  (``updated`` moved, or a new ADR) that leaves ``status`` off its epoch on
  that date, a promotion ahead of the epoch without a new
  ``status_override:``, and a changed decision section of an epoch-3 ADR
  without an Amendment. It also refuses a change that gives a ``proposed`` ADR
  its first test-verified dependent without flipping it to
  ``accepted-provisional`` (:func:`first_dependent_faults`), whether or not
  the change touches the ADR. It runs as a pull-request job, and as the
  ``adr-lifecycle-check`` pre-commit hook when a commit stages an ADR, so a
  first dependent added through ``specs/`` or ``test/`` alone is caught by
  the pull-request job.
- :func:`epoch_drift` lists every ADR whose ``status`` is behind today's
  epoch. It only reports, through the scheduled ``adr-status-drift`` workflow.

Submodules, by concern: ``epochs`` (epochs and status faults), ``edits``
(judging one ADR edit), ``git_reads`` (reading texts from git),
``dependents`` (the verified specs depending on each ADR) and ``cli`` (the
branch check and the command line).
"""

from vultron.metadata.adr.lifecycle.cli import check_change, check_paths, main
from vultron.metadata.adr.lifecycle.dependents import (
    Dependents,
    dependents_at,
    epoch_drift,
    tree_dependents,
    unflipped_adrs,
    verified_dependents,
)
from vultron.metadata.adr.lifecycle.edits import edit_faults
from vultron.metadata.adr.lifecycle.epochs import (
    EPOCH_STATUS,
    AdrEpoch,
    epoch_for,
    status_behind_fault,
    status_epoch_fault,
    today_utc,
)
from vultron.metadata.adr.lifecycle.git_reads import edited_adrs

__all__ = [
    "AdrEpoch",
    "Dependents",
    "EPOCH_STATUS",
    "check_change",
    "check_paths",
    "dependents_at",
    "edit_faults",
    "edited_adrs",
    "epoch_drift",
    "epoch_for",
    "main",
    "status_behind_fault",
    "status_epoch_fault",
    "today_utc",
    "tree_dependents",
    "unflipped_adrs",
    "verified_dependents",
]
