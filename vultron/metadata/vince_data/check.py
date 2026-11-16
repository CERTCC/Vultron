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
"""The committed-data check: no VINCE API data reaches a commit unless it is
synthetic or cleared (VSD-02-001 to VSD-02-005, ADR-0189).

Every tracked file with a JSON suffix (:data:`~.shape.JSON_SUFFIXES`) is read,
and each VINCE-shaped document (:mod:`.shape`) must

1. lie in :data:`~.marker.FIXTURE_DIR`, and
2. either carry the synthetic marker of a producer that vouches for it
   (:data:`PRODUCER_VERIFIERS`), or name only case ids on the cleared-case
   list (:mod:`.cleared`).

A document names a case id in a ``vuid`` value, or in the ``VU#<id>.<n>``
name of a vul (a vul's ``name``, a vendor status's ``vulnerability``). A
per-case read with neither, such as a bare ``posts/`` or ``vendors/`` list,
can be cleared only inside a per-case bundle, whose ``reads.case`` names
the case (:mod:`.generator` shows the form).

The generator's own fixtures must also be current, and the target set must
not be empty: a check that read nothing would pass while checking nothing.
A file the check cannot read is refused, since it cannot be ruled out.

``--history BASE`` also reads every file each commit in ``BASE..HEAD`` added
or changed, because git keeps a commit's content after a later commit
deletes it. A generator-marked file at a path the generator writes is
accepted there without the byte comparison, since an earlier commit may
hold an earlier generator's output; the head's tree gets the full check.

Usage::

    uv run vince-data check                     # the tracked tree
    uv run vince-data check --history origin/main   # and each branch commit
    uv run vince-data generate                  # rewrite the fixtures
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.generated_files import stale_paths, write_generated
from vultron.metadata.git_runner import GitError, GitRunner, git_runner
from vultron.metadata.vince_data.cleared import load_cleared_cases
from vultron.metadata.vince_data.generator import (
    generated_fixtures,
    verify_generated,
)
from vultron.metadata.vince_data.marker import (
    CLEARED_CASES_PATH,
    FIXTURE_DIR,
    GENERATOR,
    SANITIZER,
    MarkerError,
    ProducerVerifier,
    read_marker,
)
from vultron.metadata.vince_data.shape import (
    UnreadableJson,
    find_vince_shape,
    is_json_path,
    read_documents,
    walk_objects,
)

#: Each tool that may mark a file synthetic, and how it vouches for one.
#: ``None`` reserves the name for a tool not built yet: the sanitizer
#: (#6348) replaces its entry with a verifier, and until then a file marked
#: as its output is refused.
PRODUCER_VERIFIERS: Mapping[str, ProducerVerifier | None] = {
    GENERATOR: verify_generated,
    SANITIZER: None,
}

Verifiers = Mapping[str, ProducerVerifier | None]

#: A vul's name, ``VU#<case id>.<n>``, which names its case.
_VUL_NAME = re.compile(r"VU#(\d+)\.\d+")

#: The fields that hold a vul's name.
_VUL_NAME_KEYS = ("name", "vulnerability")


def _in_fixture_dir(path: str) -> bool:
    return path.startswith(f"{FIXTURE_DIR}/")


def _ids_of(obj: Mapping[str, object]) -> Iterator[str]:
    vuid = obj.get("vuid")
    if isinstance(vuid, str):
        yield vuid
    for key in _VUL_NAME_KEYS:
        value = obj.get(key)
        if isinstance(value, str):
            match = _VUL_NAME.fullmatch(value)
            if match:
                yield match.group(1)


def case_ids(document: object) -> frozenset[str]:
    """Every VINCE case id *document* names, anywhere in it."""
    return frozenset(
        case_id
        for obj, _ in walk_objects(document)
        for case_id in _ids_of(obj)
    )


def _producer_fault(
    producer: str, path: str, text: str, verifiers: Verifiers
) -> str | None:
    if producer not in verifiers:
        known = ", ".join(sorted(verifiers))
        return (
            f"marked synthetic by {producer!r}, which is not a tool that "
            f"may mark VINCE data synthetic ({known}; VSD-02-005)"
        )
    verifier = verifiers[producer]
    if verifier is None:
        return (
            f"marked synthetic by {producer!r}, which cannot vouch for a "
            "file yet, so the marker proves nothing (VSD-02-005)"
        )
    fault = verifier(path, text)
    if fault is None:
        return None
    return f"marked synthetic by {producer!r}, but {fault} (VSD-02-005)"


def _clearance_fault(document: object, cleared: frozenset[str]) -> str | None:
    named = case_ids(document)
    if not named:
        return (
            "carries no synthetic marker and names no case id the "
            "cleared-case list could clear; a per-case list read is "
            "cleared only inside a bundle whose `reads.case.vuid` names it"
        )
    uncleared = sorted(named - cleared)
    if uncleared:
        return (
            f"carries no synthetic marker, and case {', '.join(uncleared)} "
            f"is not on the cleared-case list {CLEARED_CASES_PATH} "
            "(VSD-02-001); a Coding Agent may ask a maintainer to clear "
            "it, never add it (VSD-02-004)"
        )
    return None


def _document_fault(
    document: object,
    path: str,
    text: str,
    cleared: frozenset[str],
    verifiers: Verifiers,
) -> str | None:
    """Why one VINCE-shaped document inside the fixture directory is refused."""
    try:
        marker = read_marker(document)
    except MarkerError as exc:
        return f"has a malformed synthetic marker: {exc}"
    if marker is None:
        return _clearance_fault(document, cleared)
    return _producer_fault(marker.producer, path, text, verifiers)


def file_faults(
    path: str,
    text: str,
    cleared: frozenset[str],
    verifiers: Verifiers = PRODUCER_VERIFIERS,
) -> list[str]:
    """Every reason the file at repository-relative *path* is refused."""
    try:
        documents = read_documents(path, text)
    except UnreadableJson as exc:
        return [_unreadable(path, str(exc))]
    faults = []
    for document in documents:
        match = find_vince_shape(document)
        if match is None:
            continue
        if not _in_fixture_dir(path):
            faults.append(
                f"{path}: holds {match.describe()}; VINCE API data may be "
                f"committed only in {FIXTURE_DIR}/, synthetic or cleared "
                "(VSD-02-001)"
            )
            continue
        fault = _document_fault(document, path, text, cleared, verifiers)
        if fault is not None:
            faults.append(f"{path}: holds {match.describe()}, but {fault}")
    return faults


def _unreadable(path: str, why: str) -> str:
    return (
        f"{path}: cannot be read as JSON, so it cannot be ruled out as "
        f"VINCE data: {why}"
    )


def _decoded_faults(
    path: str,
    data: bytes,
    cleared: frozenset[str],
    verifiers: Verifiers,
) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [_unreadable(path, f"not valid UTF-8: {exc}")]
    return file_faults(path, text, cleared, verifiers)


def tracked_json_files(root: Path) -> list[str]:
    """Every tracked file the check reads that exists, repository-relative.

    An entry staged for deletion, or deleted but not yet staged, is left
    out: there is nothing on disk to read.
    """
    listed = git_runner(root)(["ls-files", "-z"]).split("\0")
    return sorted(
        p for p in listed if p and is_json_path(p) and (root / p).is_file()
    )


def _cleared_ids(root: Path) -> tuple[frozenset[str], list[str]]:
    """The cleared case ids, and the list's fault when it has one.

    A faulty list clears nothing, and the check goes on, so its other
    faults are reported in the same run.
    """
    try:
        return load_cleared_cases(
            root / CLEARED_CASES_PATH, root
        ).case_ids(), []
    except MetadataLoadError as exc:
        return frozenset(), [str(exc)]
    except FileNotFoundError:
        return frozenset(), [
            f"{CLEARED_CASES_PATH}: the cleared-case list is missing"
        ]


def check(root: Path, paths: Iterable[str]) -> list[str]:
    """Every fault of the files at *paths*, the list and the fixtures."""
    targets = list(paths)
    if not targets:
        return [
            "no JSON file to check: an empty target set checks nothing, so "
            "it fails (VSD-02-001)"
        ]
    cleared, faults = _cleared_ids(root)
    faults += [
        f"{path}: the generator's fixture is missing or stale; run "
        "`uv run vince-data generate`"
        for path in stale_paths(root, generated_fixtures())
    ]
    for path in targets:
        target = root / path
        if target.is_file():
            faults += _decoded_faults(
                path, target.read_bytes(), cleared, PRODUCER_VERIFIERS
            )
    return faults


def _owned_by_generator(path: str, text: str) -> str | None:
    if path in generated_fixtures():
        return None
    return verify_generated(path, text)


#: The verifiers an earlier commit's files are judged by: see the module
#: docstring on ``--history``.
HISTORY_VERIFIERS: Verifiers = {
    **PRODUCER_VERIFIERS,
    GENERATOR: _owned_by_generator,
}


def _changed_in(run: GitRunner, commit: str) -> list[str]:
    out = run(
        [
            "diff-tree",
            "--no-commit-id",
            "-r",
            "-z",
            "--name-only",
            "--diff-filter=AM",
            "--root",
            commit,
        ]
    )
    return [p for p in out.split("\0") if p and is_json_path(p)]


def history_faults(root: Path, base: str) -> list[str]:
    """Every fault of a file a non-merge commit in ``base..HEAD`` added or
    changed, named with the commit."""
    run = git_runner(root)
    cleared, _ = _cleared_ids(root)
    commits = run(["rev-list", "--no-merges", f"{base}..HEAD"]).split()
    faults = []
    for commit in commits:
        for path in _changed_in(run, commit):
            blob = run(["cat-file", "blob", f"{commit}:{path}"])
            faults += [
                f"{commit[:12]} {fault}"
                for fault in _decoded_faults(
                    path, blob.encode("utf-8"), cleared, HISTORY_VERIFIERS
                )
            ]
    return faults


def generate(root: Path) -> list[str]:
    """Write every stale generator fixture under *root*; return their paths."""
    desired = generated_fixtures()
    written = list(stale_paths(root, desired))
    for path in written:
        write_generated(root / path, desired[path])
    return written


def _run_check(root: Path, history: str | None) -> int:
    try:
        targets = tracked_json_files(root)
        faults = check(root, targets)
        if history is not None:
            faults += history_faults(root, history)
    except GitError as exc:
        print(f"vince-data: {exc}", file=sys.stderr)
        return 1
    for fault in faults:
        print(fault, file=sys.stderr)
    if faults:
        return 1
    print(f"vince-data: {len(targets)} JSON files checked, none refused")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """``vince-data generate`` or ``vince-data check [--history BASE]``."""
    parser = argparse.ArgumentParser(
        prog="vince-data",
        description="Write the synthetic VINCE fixtures, or check that no "
        "VINCE API data is committed unless synthetic or cleared.",
    )
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument(
        "--history",
        metavar="BASE",
        help="also check every file each commit in BASE..HEAD added or "
        "changed",
    )
    args = parser.parse_args(argv)
    root = repo_root()
    if args.command == "generate":
        for path in generate(root):
            print(f"wrote {path}")
        return 0
    return _run_check(root, args.history)


__all__ = [
    "HISTORY_VERIFIERS",
    "PRODUCER_VERIFIERS",
    "case_ids",
    "check",
    "file_faults",
    "generate",
    "history_faults",
    "main",
    "tracked_json_files",
]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
