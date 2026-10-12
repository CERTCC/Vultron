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
on the base exactly as it runs on the working tree.

The base branch is ``origin/$GITHUB_BASE_REF`` when that variable is set (a
GitHub Actions ``pull_request`` run) and ``origin/main`` otherwise. When the
base cannot be resolved — no such ref, or a shallow clone with no common
history — the check is **skipped with a logged reason**, never passed: the
result carries ``skipped`` and the caller reports it (``pytest.skip``). CI
checks out with ``fetch-depth: 0`` so the base resolves there.

Consumers: the protocol-coverage guard (SR-05-005) and the
``missing_story_reference`` guard (MS-12-007) under ``test/architecture/``;
the ``verification_debt`` guard (#4200) is built on the same function.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess  # nosec B404 - runs fixed git commands only
import tarfile
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Set by GitHub Actions on ``pull_request`` runs to the base branch name.
BASE_REF_ENV = "GITHUB_BASE_REF"

#: The base branch when :data:`BASE_REF_ENV` is unset or empty.
DEFAULT_BASE_REF = "origin/main"

#: A per-item extractor: repository root in, the IDs of items in debt out.
Extractor = Callable[[Path], frozenset[str]]


class BaseUnavailableError(Exception):
    """The merge base with the base branch cannot be resolved or read."""


@dataclass(frozen=True)
class GrowthCheck:
    """Outcome of one :func:`added_since_base` evaluation.

    Attributes:
        base: The merge-base commit compared against, or ``None`` if skipped.
        added: Items in the working-tree set that were not in the base set.
        head_total: Size of the working-tree set (the live debt count).
        skipped: Why the comparison did not run, or ``None`` if it did.
    """

    base: str | None
    added: frozenset[str]
    head_total: int
    skipped: str | None = None

    def failure_message(self, what: str, remedy: str) -> str:
        """Name every added item, one per line, followed by *remedy*."""
        listing = "\n".join(f"  {item}" for item in sorted(self.added))
        base = self.base[:12] if self.base else "?"
        return (
            f"{len(self.added)} {what} added since the merge base {base} "
            f"({self.head_total} in the working tree):\n{listing}\n{remedy}"
        )


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # nosec B603 B607 - fixed git argv
        ["git", *args], cwd=repo_root, capture_output=True, check=False
    )


def base_ref_name(env: Mapping[str, str] | None = None) -> str:
    """The base branch ref: ``origin/$GITHUB_BASE_REF``, else ``origin/main``."""
    value = (os.environ if env is None else env).get(BASE_REF_ENV, "").strip()
    return f"origin/{value}" if value else DEFAULT_BASE_REF


def resolve_merge_base(repo_root: Path, base_ref: str) -> str:
    """Return the merge-base commit of *base_ref* and ``HEAD``.

    Raises:
        BaseUnavailableError: *base_ref* names no commit here, or it shares
            no history with ``HEAD`` (typically a shallow clone).
    """
    ref = _git(
        repo_root, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"
    )
    if ref.returncode != 0:
        raise BaseUnavailableError(
            f"base ref {base_ref!r} is not a commit in {repo_root} "
            f"(fetch it, or check out with fetch-depth: 0)"
        )
    mb = _git(repo_root, "merge-base", base_ref, "HEAD")
    if mb.returncode != 0:
        detail = mb.stderr.decode(errors="replace").strip()
        raise BaseUnavailableError(
            f"no merge base between {base_ref!r} and HEAD in {repo_root} "
            f"(shallow clone?){': ' + detail if detail else ''}"
        )
    return mb.stdout.decode().strip()


def materialize_tree(
    repo_root: Path, commit: str, paths: Sequence[str], dest: Path
) -> None:
    """Write *paths* as they are at *commit* under *dest*.

    A path absent at *commit* is skipped rather than an error, so a guard
    whose input directory is new on the branch sees an empty base.
    """
    present = [
        p
        for p in paths
        if _git(repo_root, "cat-file", "-e", f"{commit}:{p}").returncode == 0
    ]
    if not present:
        return
    archive = _git(
        repo_root, "archive", "--format=tar", commit, "--", *present
    )
    if archive.returncode != 0:
        detail = archive.stderr.decode(errors="replace").strip()
        raise BaseUnavailableError(f"git archive {commit} failed: {detail}")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")


def added_since_base(
    extract: Extractor,
    *,
    repo_root: Path,
    paths: Sequence[str],
    base_ref: str | None = None,
) -> GrowthCheck:
    """Items *extract* finds in the working tree but not at the merge base.

    Args:
        extract: Per-item set extractor, called with a repository root.
        repo_root: The working tree to evaluate (the "head" side).
        paths: Repository-relative paths *extract* reads; only these are
            materialized for the base side.
        base_ref: Base branch ref; defaults to :func:`base_ref_name`.

    Returns:
        A :class:`GrowthCheck`. When the base cannot be resolved, or the
        base tree raises ``ValueError`` in *extract* (a branch that migrates
        the schema), it carries ``skipped`` (also logged at WARNING) and an
        empty ``added``. *extract* raising on the working tree propagates.
    """
    head = extract(repo_root)
    ref = base_ref or base_ref_name()
    with tempfile.TemporaryDirectory(prefix="growth-guard-") as tmp:
        try:
            base = resolve_merge_base(repo_root, ref)
            materialize_tree(repo_root, base, paths, Path(tmp))
        except BaseUnavailableError as exc:
            reason = f"growth guard skipped: {exc}"
            logger.warning(reason)
            return GrowthCheck(None, frozenset(), len(head), skipped=reason)
        try:
            base_items = extract(Path(tmp))
        except ValueError as exc:
            # The HEAD extractor reads the base tree with HEAD's loaders; a
            # branch that changes the schema and migrates every file can
            # leave the base unreadable to them. The head side was already
            # evaluated above, so a malformed head still fails loudly.
            reason = (
                f"growth guard skipped: the base tree at {base[:12]} cannot "
                f"be read by this branch's extractor: {exc}"
            )
            logger.warning(reason)
            return GrowthCheck(None, frozenset(), len(head), skipped=reason)
    return GrowthCheck(base, head - base_items, len(head))


__all__ = [
    "BASE_REF_ENV",
    "BaseUnavailableError",
    "DEFAULT_BASE_REF",
    "Extractor",
    "GrowthCheck",
    "added_since_base",
    "base_ref_name",
    "materialize_tree",
    "resolve_merge_base",
]
