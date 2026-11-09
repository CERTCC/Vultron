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
"""Run the CSAF models over a local clone's test documents (CSAF-05-004).

The CSAF Technical Committee keeps test documents for its mandatory,
recommended and informative tests in its repository. They are governed by the
OASIS IPR policy and change with the draft, so the test suite never reads
them. This optional script does, when the pin moves: point it at a clone of
``oasis-tcs/csaf`` checked out at the pinned commit (or at a candidate one).

For each test group it counts the documents listed as valid and as failing a
test, and how many of each the models accept. The models check the schema
alone, so they are expected to accept every valid document and most failing
ones: a failing document usually breaks a rule the schema cannot state.

Usage::

    uv run csaf-corpus --clone ../csaf
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, ValidationError

from vultron.metadata.file_loading import (
    MetadataLoadError,
    display_path,
    read_utf8,
    validate,
)
from vultron.wire.csaf.models import CommonSecurityAdvisoryFramework

#: Where the CSAF Technical Committee keeps its test documents in its repository.
TEST_DATA_DIR = PurePosixPath("csaf_2.1/test/validator/data")
#: The index of those documents, by test and group.
TESTCASES_FILE = TEST_DATA_DIR / "testcases.json"


class _Document(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str


class _TestCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    group: str
    failures: list[_Document] = []
    valid: list[_Document] = []


class _TestCases(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tests: list[_TestCase]


class GroupCounts(BaseModel):
    """How the models judged one test group's documents."""

    model_config = ConfigDict(extra="forbid")

    valid_accepted: int = 0
    valid_rejected: int = 0
    failing_accepted: int = 0
    failing_rejected: int = 0
    missing: int = 0

    def __add__(self, other: GroupCounts) -> GroupCounts:
        return GroupCounts(
            **{
                name: getattr(self, name) + getattr(other, name)
                for name in GroupCounts.model_fields
            }
        )


def _accepts(path: Path, model: type[BaseModel]) -> bool:
    try:
        model.model_validate_json(path.read_bytes())
    except ValidationError:
        return False
    return True


def _count(
    counts: GroupCounts,
    documents: Iterable[_Document],
    data_dir: Path,
    model: type[BaseModel],
    *,
    valid: bool,
) -> None:
    for document in documents:
        path = data_dir / document.name
        if not path.is_file():
            counts.missing += 1
        elif _accepts(path, model):
            if valid:
                counts.valid_accepted += 1
            else:
                counts.failing_accepted += 1
        elif valid:
            counts.valid_rejected += 1
        else:
            counts.failing_rejected += 1


def run_corpus(
    clone: Path,
    model: type[BaseModel] = CommonSecurityAdvisoryFramework,
) -> dict[str, GroupCounts]:
    """Return per-group counts of *model*'s verdicts on *clone*'s test documents.

    Raises:
        FileNotFoundError: *clone* has no test-case index.
        MetadataLoadError: the index does not parse or does not have the
            expected shape; the error names the file.
    """
    index = clone / TESTCASES_FILE
    shown = display_path(index, clone)
    try:
        data = json.loads(read_utf8(index, shown))
    except json.JSONDecodeError as exc:
        raise MetadataLoadError(
            f"JSON parse error: {exc.msg}",
            path=shown,
            line=exc.lineno,
            column=exc.colno,
        ) from exc
    cases = validate(_TestCases, data, path=index, root=clone)
    data_dir = clone / TEST_DATA_DIR
    counts: dict[str, GroupCounts] = {}
    for case in cases.tests:
        group = counts.setdefault(case.group, GroupCounts())
        _count(group, case.valid, data_dir, model, valid=True)
        _count(group, case.failures, data_dir, model, valid=False)
    return dict(sorted(counts.items()))


def format_report(counts: dict[str, GroupCounts]) -> str:
    """Render *counts* as one line per group plus a total."""
    total = sum(counts.values(), GroupCounts())
    lines = [_line(group, c) for group, c in counts.items()]
    lines.append(_line("total", total))
    return "\n".join(lines)


def _line(group: str, c: GroupCounts) -> str:
    valid = c.valid_accepted + c.valid_rejected
    failing = c.failing_accepted + c.failing_rejected
    line = (
        f"{group}: valid {c.valid_accepted}/{valid} accepted, "
        f"failing {c.failing_rejected}/{failing} rejected"
    )
    return f"{line}, {c.missing} missing" if c.missing else line


def main(argv: Sequence[str] | None = None) -> int:
    """Print the per-group report for ``--clone``; exit 2 when it has no index."""
    parser = argparse.ArgumentParser(
        prog="csaf-corpus", description=(__doc__ or "").split("\n\n")[0]
    )
    parser.add_argument(
        "--clone",
        type=Path,
        required=True,
        help="a local clone of the oasis-tcs/csaf repository",
    )
    args = parser.parse_args(argv)
    if not (args.clone / TESTCASES_FILE).is_file():
        print(f"no {TESTCASES_FILE} under {args.clone}", file=sys.stderr)
        return 2
    print(format_report(run_corpus(args.clone)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
