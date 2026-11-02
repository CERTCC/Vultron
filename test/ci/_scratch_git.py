"""Scratch git repositories for the tests of the tag scripts.

The tag queries, the publish gate's tagging and the promote workflow all run
against a real clone of a bare ``origin``, so what git records (taggers,
dates, peeled commits) is what the scripts read.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from test.ci._scripts import load_script

# The identity the workflows tag as.
_TAGS = load_script("release_tags")
BOT_NAME: str = _TAGS.BOT_NAME
BOT_EMAIL: str = _TAGS.BOT_EMAIL


def isolate_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's git config (signing, identity) out of the tests."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(
    repo: Path,
    *args: str,
    name: str = "Some Person",
    email: str = "p@example.org",
    when: str = "",
) -> str:
    """Run git in *repo* as *name*; *when* (ISO 8601) fixes commit and tag dates."""
    env = dict(os.environ)
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(
        ["git", "-c", f"user.name={name}", "-c", f"user.email={email}", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def scratch_clone(tmp_path: Path) -> Path:
    """An empty clone of a new bare ``origin`` under *tmp_path*."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(
        ["git", "clone", "-q", str(origin), str(work)],
        check=True,
        capture_output=True,
    )
    return work


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD")


def commit(repo: Path, message: str, *, when: str = "") -> str:
    """Make an empty commit; return its id."""
    git(repo, "commit", "--allow-empty", "-q", "-m", message, when=when)
    return head(repo)


def tag_as_bot(
    repo: Path, name: str, target: str = "HEAD", *, when: str = ""
) -> None:
    """An annotated tag made as the workflows make theirs."""
    git(
        repo,
        "tag",
        "-a",
        name,
        target,
        "-m",
        "scheduled publish.",
        name=BOT_NAME,
        email=BOT_EMAIL,
        when=when,
    )
