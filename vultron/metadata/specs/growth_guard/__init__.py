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
"""PR-only growth guard over a per-item set (SR-05-005, MS-12-007).

A committed count of debt items races every concurrent PR that moves it
(``notes/testing-pitfalls.md`` § "A Two-Sided Count Pin Races Every Concurrent
PR"), and a one-sided ceiling collects silent slack instead (#3959). This
module holds back growth without committing a number: it evaluates one
*extractor* — a function from a repository tree to the set of item IDs that
are in debt — at the merge base with the base branch and at the working tree,
and returns only the items the branch **added**. Items that leave the set, or
that were already in it at the base, are not this branch's doing and never
fail it.

The base tree is materialized from git (``git archive``) into a temporary
directory holding only the *paths* the extractor reads, so the extractor runs
on the base exactly as it runs on the working tree. An extractor whose result
for each file depends on that file alone can skip the files the branch left
alone on both sides (:func:`compare_changed_with_base`), so its cost follows
the size of the change rather than of the tree.

The base branch is ``origin/$GITHUB_BASE_REF`` when that variable is set (a
GitHub Actions ``pull_request`` run) and ``origin/main`` otherwise. When the
base cannot be resolved — no such ref, or a shallow clone with no common
history — the check is **skipped with a logged reason**, never passed: the
result carries ``skipped`` and the caller reports it (``pytest.skip``). CI
checks out with ``fetch-depth: 0`` so the base resolves there, and under GitHub
Actions (``GITHUB_ACTIONS=true``) a missing base raises instead of skipping, so
a checkout that loses its history cannot turn the guard into a green skip.

An *extractor* error on the base tree is not a skip either: it is re-raised as
:class:`BaseExtractionError`, naming the merge base, because the failing tree
is the one materialized from git, not the working tree.

Consumers: the marker-coverage guard (SR-05-005), the
``missing_story_reference`` guard (MS-12-007), the compound-statement guard
(MS-03-007) and the ``verification_debt`` guard (MS-10-016) under
``test/architecture/``. A guard that must see both trees at once, rather than
a set difference, uses :func:`compare_with_base` directly: the kind-change
marker guard (MS-12-011) compares each ID's kind and marker at the base with
the working tree.

Submodules, by concern: ``base_tree`` (resolving the merge base, the changed
files and materializing the base tree from git) and ``compare`` (running an
extractor on both trees and reporting what the branch added).
"""

from vultron.metadata.specs.growth_guard.base_tree import (
    BASE_REF_ENV,
    CI_ENV,
    DEFAULT_BASE_REF,
    BaseUnavailableError,
    ChangedFiles,
    base_ref_name,
    changed_files,
    materialize_tree,
    resolve_merge_base,
    running_in_ci,
)
from vultron.metadata.specs.growth_guard.compare import (
    BaseComparison,
    BaseExtractionError,
    Extractor,
    GrowthCheck,
    added_since_base,
    compare_changed_with_base,
    compare_with_base,
)

__all__ = [
    "BASE_REF_ENV",
    "BaseComparison",
    "BaseExtractionError",
    "BaseUnavailableError",
    "CI_ENV",
    "ChangedFiles",
    "DEFAULT_BASE_REF",
    "Extractor",
    "GrowthCheck",
    "added_since_base",
    "base_ref_name",
    "changed_files",
    "compare_changed_with_base",
    "compare_with_base",
    "materialize_tree",
    "resolve_merge_base",
    "running_in_ci",
]
