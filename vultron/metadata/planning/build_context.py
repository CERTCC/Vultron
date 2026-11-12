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
"""``build-context``: hand the context ``build`` loaded forward to pr-ship.

``build`` and ``bugfix`` load task context with ``orient-agent`` and
``deepen-context``; every later phase of the pipeline (the pre-push reviewer,
``pr-triage``, ``pr-execute``) is a fresh agent that would load it again. After
``deepen-context`` they write one file that lists what was loaded, and the later
phases load exactly that list instead of re-deriving it::

    build-context path [--branch B]          # print the file's path
    build-context write --manifest /tmp/spec-manifest-N.txt \
        --hint "wire layer" --note notes/wire-core-boundary.md \
        --glossary "Activity & Wire Format"
    build-context check                      # may a phase reuse the file?

The file is ``.claude/pr-context-<branch>.json`` in the worktree root, with the
branch percent-encoded the way ``prepush-delta.sh`` encodes it (``%`` as
``%25``, ``/`` as ``%2F``); ``.claude/pr-*.json`` gitignores it. It records
facts found — the branch, the head and base commits, the Spec manifest's loaded
IDs, the domain hints, and the notes and glossary sections read — and never the
author's reasoning, so a reviewer that loads it still reviews with a fresh eye
(PAD-07-001). :class:`BuildContext` forbids any other key.

The file is an optimization, never a precondition. ``check`` prints
``mode=reuse`` and exits 0 only when the file is present, valid, for the
current branch, and recorded at a commit that is still an ancestor of
``HEAD``. Otherwise it prints ``mode=fallback`` with a ``reason=`` and exits 3,
and the phase loads its context exactly as it would without the file. Write the
file before the branch's first commit: ``create-pr`` cherry-picks the branch
onto a newer base, which keeps a base commit an ancestor but not a branch
commit.

Exit codes: 0 = written / path printed / reuse; 3 = fallback;
2 = setup error (not in a git work tree, not on a branch, bad input).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from vultron.metadata.specs.backstop import GROUP_RE, REQ_RE, parse_manifest
from vultron.metadata.specs.registry import load_registry
from vultron.primitives import NonEmptyString

GLOSSARY = Path("docs/reference/glossary.md")


class SetupError(Exception):
    """The command cannot run here (exit 2)."""


class BuildContext(BaseModel):
    """The hand-forward file: what ``build`` loaded, as facts only.

    A plain ``BaseModel``: a local tooling record under ``vultron/metadata/``,
    never a protocol object.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    branch: NonEmptyString
    head_sha: NonEmptyString
    base_sha: NonEmptyString
    spec_ids: list[NonEmptyString] = []
    spec_groups: list[NonEmptyString] = []
    spec_topics: list[NonEmptyString] = []
    domain_hints: list[NonEmptyString]
    notes: list[NonEmptyString] = []
    glossary_sections: list[NonEmptyString] = []


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _toplevel() -> Path:
    result = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise SetupError("not in a git work tree")
    return Path(result.stdout.strip())


def _current_branch(root: Path) -> str:
    branch = _git(root, "branch", "--show-current").stdout.strip()
    if not branch:
        raise SetupError("not on a branch")
    return branch


def context_path(root: Path, branch: str) -> Path:
    """The file for *branch*, encoded as ``prepush-delta.sh`` encodes it."""
    name = branch.replace("%", "%25").replace("/", "%2F")
    return root / ".claude" / f"pr-context-{name}.json"


def _glossary_sections(root: Path) -> set[str]:
    try:
        text = (root / GLOSSARY).read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"cannot read {GLOSSARY}: {exc}") from exc
    return {
        line[3:].strip()
        for line in text.splitlines()
        if line.startswith("## ")
    }


def _spec_lists(
    root: Path, manifest: Path
) -> tuple[list[str], list[str], list[str]]:
    """The manifest's loaded IDs, split into requirements, groups, topics."""
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"cannot read manifest {manifest}: {exc}") from exc
    topics = {f.id for f in load_registry(root / "specs").files}
    loaded = parse_manifest(text, topics).loaded
    if not loaded:
        raise SetupError(f"manifest {manifest} lists no loaded spec ID")
    return (
        sorted(i for i in loaded if REQ_RE.match(i)),
        sorted(i for i in loaded if GROUP_RE.match(i)),
        sorted(i for i in loaded if i in topics),
    )


def build(args: argparse.Namespace, root: Path) -> BuildContext:
    """Collect the facts for the current branch and validate them."""
    missing = [n for n in args.note if not (root / n).is_file()]
    if missing:
        raise SetupError(f"no such note file: {', '.join(missing)}")
    known = _glossary_sections(root)
    unknown = [s for s in args.glossary if s not in known]
    if unknown:
        raise SetupError(f"no such glossary section: {', '.join(unknown)}")
    base = _git(root, "merge-base", args.base, "HEAD")
    if base.returncode != 0:
        raise SetupError(f"no merge base with {args.base}")
    ids, groups, topics = _spec_lists(root, Path(args.manifest))
    try:
        return BuildContext(
            branch=_current_branch(root),
            head_sha=_git(root, "rev-parse", "HEAD").stdout.strip(),
            base_sha=base.stdout.strip(),
            domain_hints=args.hint,
            notes=args.note,
            glossary_sections=args.glossary,
            spec_ids=ids,
            spec_groups=groups,
            spec_topics=topics,
        )
    except ValidationError as exc:
        raise SetupError(str(exc)) from exc


def _write(args: argparse.Namespace, root: Path) -> int:
    context = build(args, root)
    path = context_path(root, context.branch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(context.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


def _unusable(root: Path, path: Path, branch: str) -> str | BuildContext:
    """The reason the file at *path* cannot be reused, or the file itself."""
    if not path.is_file():
        return "no build context file"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return "build context is not valid JSON"
    try:
        context = BuildContext.model_validate(raw)
    except ValidationError as exc:
        return f"build context is malformed ({exc.error_count()} error(s))"
    if context.branch != branch:
        return f"build context is for branch {context.branch}, not {branch}"
    ancestor = _git(
        root, "merge-base", "--is-ancestor", context.head_sha, "HEAD"
    )
    if ancestor.returncode == 1:
        return f"recorded head {context.head_sha} is not an ancestor of HEAD"
    if ancestor.returncode != 0:
        return f"recorded head {context.head_sha} is not in the object store"
    return context


def _check(root: Path) -> int:
    branch = _current_branch(root)
    path = context_path(root, branch)
    print(f"context={path}")
    found = _unusable(root, path, branch)
    if isinstance(found, str):
        print("mode=fallback")
        print(f"reason={found}")
        return 3
    print("mode=reuse")
    print("reason=build context matches this branch")
    for key in ("spec_ids", "spec_groups", "spec_topics"):
        print(f"{key}={','.join(getattr(found, key))}")
    for prefix, values in (
        ("hint", found.domain_hints),
        ("note", found.notes),
        ("glossary", found.glossary_sections),
    ):
        for value in values:
            print(f"{prefix}={value}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build-context",
        description="Write or check the context file build hands to pr-ship.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    path = sub.add_parser("path", help="print the file's path")
    path.add_argument("--branch", help="default: the current branch")
    write = sub.add_parser("write", help="record what deepen-context loaded")
    write.add_argument("--manifest", required=True, help="Spec manifest file")
    write.add_argument(
        "--hint", action="append", required=True, help="a domain hint"
    )
    write.add_argument("--note", action="append", default=[], help="a note")
    write.add_argument(
        "--glossary", action="append", default=[], help="a glossary section"
    )
    write.add_argument("--base", default="origin/main", help="base ref")
    sub.add_parser("check", help="may this phase reuse the file?")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the exit code (see the module docstring)."""
    args = _parser().parse_args(argv)
    try:
        root = _toplevel()
        if args.command == "path":
            print(context_path(root, args.branch or _current_branch(root)))
            return 0
        if args.command == "write":
            return _write(args, root)
        return _check(root)
    except SetupError as exc:
        print(f"build-context: {exc}", file=sys.stderr)
        return 2


def cli() -> None:
    """Console-script wrapper: ``sys.exit(main())``."""
    sys.exit(main())


__all__ = ["BuildContext", "context_path", "main"]
