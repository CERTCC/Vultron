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

Consumers: the marker-coverage guard (SR-05-005) and the
``missing_story_reference`` guard (MS-12-007) under ``test/architecture/``.
The planned ``verification_debt`` guard (#4200) is meant to reuse it. A guard
that must see both trees at once, rather than a set difference, uses
:func:`compare_with_base` directly: the kind-change marker guard (MS-12-011)
compares each ID's kind and marker at the base with the working tree.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess  # nosec B404 - runs fixed git commands only
import tarfile
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Set by GitHub Actions on ``pull_request`` runs to the base branch name.
BASE_REF_ENV = "GITHUB_BASE_REF"

#: Set to ``true`` by GitHub Actions; there a missing base fails, not skips.
CI_ENV = "GITHUB_ACTIONS"

#: The base branch when :data:`BASE_REF_ENV` is unset or empty.
DEFAULT_BASE_REF = "origin/main"

#: A per-item extractor: repository root in, the IDs of items in debt out.
Extractor = Callable[[Path], frozenset[str]]


class BaseUnavailableError(Exception):
    """The merge base with the base branch cannot be resolved or read."""


class BaseExtractionError(Exception):
    """The extractor failed on the tree materialized from the merge base."""


@dataclass(frozen=True)
class GrowthCheck:
    """Outcome of one :func:`added_since_base` evaluation.

    Attributes:
        base: The merge-base commit compared against, or ``None`` if skipped.
        added: Items in the working-tree set that were not in the base set.
        head_total: Size of the working-tree set (the live debt count), or
            ``None`` when only the changed files were read
            (:func:`compare_changed_with_base`).
        skipped: Why the comparison did not run, or ``None`` if it did.
    """

    base: str | None
    added: frozenset[str]
    head_total: int | None
    skipped: str | None = None

    def failure_message(self, what: str, remedy: str) -> str:
        """Name every added item, one per line, followed by *remedy*."""
        listing = "\n".join(f"  {item}" for item in sorted(self.added))
        base = self.base[:12] if self.base else "?"
        total = (
            ""
            if self.head_total is None
            else f" ({self.head_total} in the working tree)"
        )
        return (
            f"{len(self.added)} {what} added since the merge base {base}"
            f"{total}:\n{listing}\n{remedy}\n"
            f"If this lists items the branch did not touch, the local base "
            f"ref may be stale: run `git fetch origin` and retry."
        )


@dataclass(frozen=True)
class BaseComparison[T]:
    """What one reader saw at the merge base and in the working tree.

    Attributes:
        base: The merge-base commit read, or ``None`` if skipped.
        base_value: The reader's result on the base tree, or ``None`` if
            skipped.
        head_value: The reader's result on the working tree.
        skipped: Why the base was not read, or ``None`` if it was.
    """

    base: str | None
    base_value: T | None
    head_value: T
    skipped: str | None = None


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # nosec B603 B607 - fixed git argv
            ["git", *args], cwd=repo_root, capture_output=True, check=False
        )
    except FileNotFoundError as exc:
        raise BaseUnavailableError(f"git is not available: {exc}") from exc


def _stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
    detail = proc.stderr.decode(errors="replace").strip()
    return f": {detail}" if detail else ""


def running_in_ci(env: Mapping[str, str] | None = None) -> bool:
    """Whether :data:`CI_ENV` says this is a GitHub Actions run."""
    return (os.environ if env is None else env).get(CI_ENV, "") == "true"


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
            f"(fetch it, or check out with fetch-depth: 0){_stderr(ref)}"
        )
    mb = _git(repo_root, "merge-base", base_ref, "HEAD")
    if mb.returncode != 0:
        raise BaseUnavailableError(
            f"no merge base between {base_ref!r} and HEAD in {repo_root} "
            f"(shallow clone?){_stderr(mb)}"
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
    _extract_archive(repo_root, commit, present, dest)


def _extract_archive(
    repo_root: Path, commit: str, present: Sequence[str], dest: Path
) -> None:
    """Write *present*, paths that all exist at *commit*, under *dest*."""
    if not present:
        return
    archive = _git(
        repo_root, "archive", "--format=tar", commit, "--", *present
    )
    if archive.returncode != 0:
        raise BaseUnavailableError(
            f"git archive {commit} failed{_stderr(archive)}"
        )
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")


@dataclass(frozen=True)
class ChangedFiles:
    """The files under some paths that differ between a commit and the tree.

    Attributes:
        at_base: Changed files that exist at the commit.
        at_head: Changed files that exist in the working tree, untracked
            files that are not ignored included.
    """

    at_base: tuple[str, ...]
    at_head: tuple[str, ...]


def changed_files(
    repo_root: Path, commit: str, paths: Sequence[str]
) -> ChangedFiles:
    """The files under *paths* whose content differs from *commit*.

    Compares the working tree, staged or not, with *commit*. A rename is a
    deletion and an addition, so both names are listed. Ignored files are not
    listed: they are not part of either tree.

    Raises:
        BaseUnavailableError: git cannot compare the trees.
    """
    if not paths:
        return ChangedFiles((), ())
    diff = _git(
        repo_root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        commit,
        "--",
        *paths,
    )
    untracked = _git(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        *paths,
    )
    for proc in (diff, untracked):
        if proc.returncode != 0:
            raise BaseUnavailableError(
                f"git could not list the files changed since {commit[:12]}"
                f"{_stderr(proc)}"
            )
    fields = diff.stdout.decode("utf-8", "surrogateescape").split("\0")
    at_base: list[str] = []
    at_head: list[str] = []
    for status, path in zip(fields[0::2], fields[1::2], strict=False):
        if status != "A":
            at_base.append(path)
        if status != "D":
            at_head.append(path)
    listed = untracked.stdout.decode("utf-8", "surrogateescape")
    at_head.extend(p for p in listed.split("\0") if p)
    return ChangedFiles(tuple(at_base), tuple(at_head))


def _base_settings(
    base_ref: str | None, require_base: bool | None
) -> tuple[str, bool]:
    """The base ref to compare with, and whether a missing base must raise."""
    if require_base is None:
        require_base = running_in_ci()
    return base_ref or base_ref_name(), require_base


def _skip_reason(exc: BaseUnavailableError, require_base: bool) -> str:
    """Why the guard skips its base, logged; re-raises *exc* when required."""
    if require_base:
        raise exc
    reason = f"growth guard skipped: {exc}"
    logger.warning(reason)
    return reason


def compare_changed_with_base[T](
    read: Callable[[Path], T],
    *,
    repo_root: Path,
    paths: Sequence[str],
    base_ref: str | None = None,
    require_base: bool | None = None,
) -> BaseComparison[T]:
    """Run *read* on only the files that differ from the merge base.

    :func:`compare_with_base` for a *read* whose result for each file depends
    only on that file's path and text, as the PD-10 line extractors' does. A
    file the branch left alone gives the same result on both sides, so leaving
    it out of both changes no comparison of the two, and the work is the size
    of the change, not of the tree. The changed files are copied into two
    temporary trees, the base's from git and the working tree's from disk, so
    a path in an error names a copy. When the base is skipped, *read* runs on
    the whole working tree. Arguments and errors are as
    :func:`added_since_base` documents.
    """
    ref, require_base = _base_settings(base_ref, require_base)
    with tempfile.TemporaryDirectory(prefix="growth-guard-") as tmp:
        base_root, head_root = Path(tmp, "base"), Path(tmp, "head")
        try:
            base = resolve_merge_base(repo_root, ref)
            changed = changed_files(repo_root, base, paths)
            _extract_archive(repo_root, base, changed.at_base, base_root)
        except BaseUnavailableError as exc:
            reason = _skip_reason(exc, require_base)
            return BaseComparison(None, None, read(repo_root), skipped=reason)
        for rel in changed.at_head:
            if not (repo_root / rel).is_file():
                continue
            target = head_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo_root / rel, target)
        base_root.mkdir(exist_ok=True)
        head_root.mkdir(exist_ok=True)
        base_value = _read_base(read, base_root, base, ref)
        head_value = read(head_root)
    return BaseComparison(base, base_value, head_value)


def _read_base[T](
    read: Callable[[Path], T], base_root: Path, base: str, ref: str
) -> T:
    """*read* on the tree materialized from *base*, its errors attributed."""
    try:
        return read(base_root)
    except Exception as exc:
        raise BaseExtractionError(
            f"the growth guard could not read the merge base "
            f"{base[:12]} ({ref}): {exc}. That tree is materialized from "
            f"git and read with this branch's loaders, so a path in the "
            f"error names the base copy, not the working tree. If this "
            f"branch changes the format the extractor reads, make the "
            f"loader accept the old form as well, so it can read the base."
        ) from exc


def compare_with_base[T](
    read: Callable[[Path], T],
    *,
    repo_root: Path,
    paths: Sequence[str],
    base_ref: str | None = None,
    head: T | None = None,
    require_base: bool | None = None,
) -> BaseComparison[T]:
    """Run *read* on the merge-base tree and on the working tree.

    The shared machinery behind :func:`added_since_base`, for a guard that
    must compare the two results itself rather than take a set difference.
    Arguments, skipping and errors are as :func:`added_since_base` documents;
    *head* is the working-tree result, when the caller already computed it.

    When no file under *paths* differs from the merge base, the base tree is
    the working tree, so the working-tree result stands for both and the base
    is not read.
    """
    if head is None:
        head = read(repo_root)
    ref, require_base = _base_settings(base_ref, require_base)
    with tempfile.TemporaryDirectory(prefix="growth-guard-") as tmp:
        try:
            base = resolve_merge_base(repo_root, ref)
            changed = changed_files(repo_root, base, paths)
            if not (changed.at_base or changed.at_head):
                return BaseComparison(base, head, head)
            materialize_tree(repo_root, base, paths, Path(tmp))
        except BaseUnavailableError as exc:
            reason = _skip_reason(exc, require_base)
            return BaseComparison(None, None, head, skipped=reason)
        base_value = _read_base(read, Path(tmp), base, ref)
    return BaseComparison(base, base_value, head)


def added_since_base(
    extract: Extractor,
    *,
    repo_root: Path,
    paths: Sequence[str],
    base_ref: str | None = None,
    head: frozenset[str] | None = None,
    require_base: bool | None = None,
) -> GrowthCheck:
    """Items *extract* finds in the working tree but not at the merge base.

    Args:
        extract: Per-item set extractor, called with a repository root.
        repo_root: The working tree to evaluate (the "head" side).
        paths: Repository-relative paths *extract* reads; only these are
            materialized for the base side.
        base_ref: Base branch ref; defaults to :func:`base_ref_name`.
        head: The working-tree set, when the caller already computed it with
            *extract*'s own logic from an in-memory corpus (the shared
            architecture-test corpus); ``None`` calls ``extract(repo_root)``.
        require_base: Raise instead of skipping when the base cannot be
            resolved; defaults to :func:`running_in_ci`.

    Returns:
        A :class:`GrowthCheck`. When the base cannot be resolved it carries
        ``skipped`` (also logged at WARNING) and an empty ``added``.

    Raises:
        BaseUnavailableError: The base cannot be resolved and *require_base*
            holds.
        BaseExtractionError: *extract* failed on the merge-base tree. A guard
            that cannot compare must not read as a pass. An error from
            *extract* on the working tree propagates unchanged.
    """
    seen = compare_with_base(
        extract,
        repo_root=repo_root,
        paths=paths,
        base_ref=base_ref,
        head=head,
        require_base=require_base,
    )
    head_items = seen.head_value
    if seen.base_value is None:
        return GrowthCheck(
            None, frozenset(), len(head_items), skipped=seen.skipped
        )
    return GrowthCheck(
        seen.base, head_items - seen.base_value, len(head_items)
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
