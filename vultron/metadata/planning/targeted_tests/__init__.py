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
"""The local test gate for a pushed Pull Request (``targeted-tests``).

CI is the full-suite authority (ADR-0126, ADR-0138, ADR-0179); every local
test gate is a *targeted* set derived from a diff. This command derives that
set for the branch diff, derives the narrower gate after a conflict merge,
and answers the "did the base touch my files?" question that decides whether
the merger refreshes the Pull Request on GitHub before merging it::

    targeted-tests                     # the file list
    targeted-tests --pytest            # the pytest command line to run
    targeted-tests --json
    targeted-tests --overlap           # files changed on both sides
    targeted-tests --paths F [F ...]   # the gate after a conflict merge

Output contract (stable; pipeline skills parse it):

- **Selection mode** (default) exits 0 and prints the targeted set, one path
  per line (``test/architecture/`` and ``test/metadata/`` are always among
  them). ``--pytest`` prints instead a single runnable command line; it
  carries ``-m ""`` to override the ``-m 'not integration'`` default in
  ``addopts``, so integration-marked tests among the selected files still
  run (PAD-18-011), and it always carries the selected paths. ``--json``
  prints ``{"tests", "unbounded", "unmapped", "pytest"}``.
- **Overlap mode** (``--overlap``) prints the paths the base changed since
  the merge base that this branch also changes, one per line, and exits 1
  when there are any and 0 when there are none (PAD-18-009). ``--json``
  prints ``{"base", "merge_base", "overlap"}``.
- **Paths mode** (``--paths``) prints the same selection output for the
  named files instead of the branch diff: the gate after resolving a merge
  conflict, run on the conflicted files (PAD-18-015). Each file counts as
  wholly changed, since both sides edited it. ``--base`` is not read. A
  conflicted non-Python file under ``test/`` (a data file) maps to no test
  and is named on stderr like any other unmapped path.
- Exit 2 is a setup error (not a repository, unknown base ref).

Changed paths no rule maps to a test (a docs page, a script outside
``vultron/``, a module nothing imports) are named on stderr, so an empty set
is never mistaken for a clean one. The command does not fetch: run
``git fetch origin`` first so ``--base`` is current.

**The branch diff is the key**: the merge base with ``--base`` against the
working tree, so a fix commit landing on top of an earlier change is gated
by both, and uncommitted and untracked work counts. Overlap mode reads the
same branch side on purpose: the gate runs before a push, so work not yet
committed is about to be part of the PR.

**No path escalates the gate** (PAD-18-003). A local run of the full unit and
integration suites takes longer than CI's run of both, which GitHub requires
before the merge, so there is nothing to gain by waiting for the slower of
two runs that give the same answer. Shared test infrastructure —
``conftest.py``, ``pyproject.toml``, ``uv.lock``, ``vultron/__init__.py``,
and the test fixtures, factories, helpers and data files outside the
always-selected directories — is the one path shape no targeted set bounds,
because tests reach it by fixture name, by file path or by every run reading
it. Such a path is *reported* on stderr and in ``unbounded``, and the gate
still runs the set it can select plus the always-selected directories
(PAD-18-012). A change to an integration-bearing layer
(``vultron/core/behaviors/``, ``vultron/adapters/``, …) is gated by its
importers like any other change, integration-marked ones included
(ADR-0143). The docker-driven scripts under ``integration_tests/`` are not
pytest tests and stay CI's to run.

**Hub and monolith demotion do not apply.** ``spec-backstop`` demotes a symbol
imported by more than ``HUB_THRESHOLD`` test files, and a test file marking
more than ``MONOLITH_GROUP_SPAN`` spec groups, because there they would put
nearly every spec group in the blocking tier — a *precision* problem in
choosing what to read. Test selection has the opposite failure mode: a test
left out is a regression the gate cannot see, and a widely imported symbol is
exactly the change most likely to break many tests. So every importer of a
changed symbol is selected, however many there are, and spec markers play no
part. The cost of a large set is run time, which the full suite bounds.

**What "imports" means.** A test imports what its own file imports, plus
what every test-side module it imports (a ``test/support`` helper, another
test module) imports in turn, so a change reached through a helper still
selects the test, and a changed helper or test module selects its
importers. Imports *inside* ``vultron`` are not followed: a test of
``vultron.b`` is not selected for a change to ``vultron.a`` that ``b`` calls,
unless it imports ``a`` too. That reach is CI's (ADR-0126). Changed symbols
are read from both sides of the diff, so a deleted or renamed function
selects the tests that imported its old name.

PAD-18-013 — a CI failure in a test the targeted set does not
include joins the gate — is the caller's to apply: this command cannot see CI.

Requirements: specs/parallel-development.yaml PAD-18-002, PAD-18-003,
PAD-18-004, PAD-18-009, PAD-18-011 to PAD-18-015, PAD-18-019.

Submodules, by concern: ``index`` (the source-to-test import index),
``selection`` (the targeted set, the unbounded-path report and the pytest
command) and ``cli`` (the command line).
"""

from vultron.metadata.planning.targeted_tests.cli import main
from vultron.metadata.planning.targeted_tests.index import (
    build_index,
    widen_index,
)
from vultron.metadata.planning.targeted_tests.selection import (
    ALWAYS_SELECTED,
    GATE_CEILING,
    METADATA_TESTS,
    branch_overlap,
    overlap,
    pytest_argv,
    select_tests,
    shared_infrastructure,
)

__all__ = [
    "ALWAYS_SELECTED",
    "GATE_CEILING",
    "METADATA_TESTS",
    "branch_overlap",
    "build_index",
    "main",
    "overlap",
    "pytest_argv",
    "select_tests",
    "shared_infrastructure",
    "widen_index",
]
