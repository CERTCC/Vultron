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
"""The merge base for the growth guard: resolving it, listing changed files and
materializing its tree from git.
"""

from __future__ import annotations

import io
import os
import subprocess  # nosec B404 - runs fixed git commands only
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

#: Set by GitHub Actions on ``pull_request`` runs to the base branch name.
BASE_REF_ENV = "GITHUB_BASE_REF"

#: Set to ``true`` by GitHub Actions; there a missing base fails, not skips.
CI_ENV = "GITHUB_ACTIONS"

#: The base branch when :data:`BASE_REF_ENV` is unset or empty.
DEFAULT_BASE_REF = "origin/main"


class BaseUnavailableError(Exception):
    """The merge base with the base branch cannot be resolved or read."""


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
