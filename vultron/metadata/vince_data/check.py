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
synthetic or cleared (ADR-0189 rules 3 and 4, VSD-02-001 to VSD-02-005).

Every tracked ``.json``, ``.jsonl`` and ``.ndjson`` file is read, and each
VINCE-shaped one (:mod:`.shape`) must

1. lie in :data:`~.marker.FIXTURE_DIR`, and
2. either carry the synthetic marker of a producer that vouches for it
   (:data:`PRODUCER_VERIFIERS`), or have a case id on the cleared-case list
   (:mod:`.cleared`).

The generator's own fixtures must also be current, and the target set must
not be empty: a check that read nothing would pass while checking nothing.
A file the check cannot parse is refused, since it cannot be ruled out.

Usage::

    uv run vince-data check       # exit 1 naming every refused file
    uv run vince-data generate    # rewrite the generator's fixtures
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.generated_files import (
    read_committed,
    stale_paths,
    write_generated,
)
from vultron.metadata.git_runner import GitError, git_runner
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
    JSON_SUFFIXES,
    UnreadableJson,
    find_vince_shape,
    read_documents,
)

#: Each tool that may mark a file synthetic, and how it vouches for one.
#: ``None`` reserves the name for a tool not built yet: the sanitizer
#: (#6348) replaces its entry with a verifier, and until then a file marked
#: as its output is refused.
PRODUCER_VERIFIERS: Mapping[str, ProducerVerifier | None] = {
    GENERATOR: verify_generated,
    SANITIZER: None,
}


def _in_fixture_dir(path: str) -> bool:
    return path.startswith(f"{FIXTURE_DIR}/")


def _case_id(document: object) -> str | None:
    """The VINCE case id a document is about, when it names one.

    A raw case or note response names it as ``vuid``; a per-case bundle
    names it as ``reads.case.vuid``.
    """
    if not isinstance(document, dict):
        return None
    reads = document.get("reads")
    named: dict[str, object] = document
    if isinstance(reads, dict) and isinstance(reads.get("case"), dict):
        named = reads["case"]
    vuid = named.get("vuid")
    return vuid if isinstance(vuid, str) else None


def _producer_fault(
    producer: str,
    path: str,
    text: str,
    verifiers: Mapping[str, ProducerVerifier | None],
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


def _document_fault(
    document: object,
    path: str,
    text: str,
    cleared: frozenset[str],
    verifiers: Mapping[str, ProducerVerifier | None],
) -> str | None:
    """Why one VINCE-shaped document inside the fixture directory is refused."""
    try:
        marker = read_marker(document)
    except MarkerError as exc:
        return f"has a malformed synthetic marker: {exc}"
    if marker is not None:
        return _producer_fault(marker.producer, path, text, verifiers)
    case_id = _case_id(document)
    if case_id is None:
        return (
            "carries no synthetic marker and names no case id (a top-level "
            "`vuid`, or `reads.case.vuid`) the cleared-case list could clear"
        )
    if case_id not in cleared:
        return (
            f"carries no synthetic marker, and case {case_id} is not on the "
            f"cleared-case list {CLEARED_CASES_PATH} (VSD-02-001); a Coding "
            "Agent may ask a maintainer to clear it, never add it "
            "(VSD-02-004)"
        )
    return None


def file_faults(
    path: str,
    text: str,
    cleared: frozenset[str],
    verifiers: Mapping[str, ProducerVerifier | None] = PRODUCER_VERIFIERS,
) -> list[str]:
    """Every reason the file at repository-relative *path* is refused."""
    try:
        documents = read_documents(path, text)
    except UnreadableJson as exc:
        return [
            f"{path}: does not parse as JSON, so it cannot be ruled out as "
            f"VINCE data: {exc}"
        ]
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


def tracked_json_files(root: Path) -> list[str]:
    """Every tracked file the check reads, repository-relative."""
    run = git_runner(root)
    patterns = [f"*{suffix}" for suffix in JSON_SUFFIXES]
    listed = run(["ls-files", "-z", "--", *patterns]).split("\0")
    return sorted(p for p in listed if p and (root / p).is_file())


def check(root: Path, paths: Iterable[str]) -> list[str]:
    """Every fault of the files at *paths*, the list and the fixtures."""
    targets = list(paths)
    if not targets:
        return [
            "no JSON file to check: an empty target set checks nothing, so "
            "it fails (VSD-02-001)"
        ]
    try:
        cleared = load_cleared_cases(root / CLEARED_CASES_PATH, root)
    except MetadataLoadError as exc:
        return [str(exc)]
    except FileNotFoundError:
        return [f"{CLEARED_CASES_PATH}: the cleared-case list is missing"]
    faults = [
        f"{path}: the generator's fixture is missing or stale; run "
        "`uv run vince-data generate`"
        for path in stale_paths(root, generated_fixtures())
    ]
    for path in targets:
        text = read_committed(root / path)
        if text is not None:
            faults.extend(file_faults(path, text, cleared.case_ids()))
    return faults


def generate(root: Path) -> list[str]:
    """Write every stale generator fixture under *root*; return their paths."""
    desired = generated_fixtures()
    written = list(stale_paths(root, desired))
    for path in written:
        write_generated(root / path, desired[path])
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """``vince-data generate`` or ``vince-data check``."""
    parser = argparse.ArgumentParser(
        prog="vince-data",
        description="Write the synthetic VINCE fixtures, or check that no "
        "VINCE API data is committed unless synthetic or cleared.",
    )
    parser.add_argument("command", choices=("generate", "check"))
    args = parser.parse_args(argv)
    root = repo_root()
    if args.command == "generate":
        for path in generate(root):
            print(f"wrote {path}")
        return 0
    try:
        targets = tracked_json_files(root)
    except GitError as exc:
        print(f"vince-data: {exc}", file=sys.stderr)
        return 1
    faults = check(root, targets)
    for fault in faults:
        print(fault, file=sys.stderr)
    if faults:
        return 1
    print(f"vince-data: {len(targets)} JSON files checked, none refused")
    return 0


__all__ = [
    "PRODUCER_VERIFIERS",
    "check",
    "file_faults",
    "generate",
    "main",
    "tracked_json_files",
]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
