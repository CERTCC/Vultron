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
"""Compare the upstream checkout with the pinned revision (CSAF-05-005)."""

from __future__ import annotations

import difflib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from vultron.metadata.csaf.corpus import TESTCASES_FILE, load_corpus_index
from vultron.metadata.csaf.draft_watch.fields import (
    READ_FIELDS,
    AffectedField,
    ReadField,
    affected_fields,
)
from vultron.metadata.csaf.draft_watch.schemas import SchemaSet
from vultron.metadata.csaf.pin import PINNED_COPY_DIR, CsafPin
from vultron.metadata.csaf.regenerate import render_models
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.generated_files import write_generated

#: The profile text of the CSAF 2.1 draft, in the upstream repository.
PROFILES_FILE = PurePosixPath("csaf_2.1/prose/edit/src/profiles.md")


#: The test group whose test IDs make up the list of mandatory tests.
MANDATORY_GROUP = "mandatory"


#: Generates the models package from a schema directory and its pin.
Renderer = Callable[[Path, CsafPin], Mapping[str, str]]


def _models_of(schemas: SchemaSet, render: Renderer) -> Mapping[str, str]:
    """Generate the models from *schemas*, written out to a staging directory."""
    with TemporaryDirectory(prefix="csaf-draft-watch-") as staging:
        for local, schema in schemas.files.items():
            write_generated(
                Path(staging) / local, json.dumps(schema, indent=2)
            )
        return render(Path(staging), schemas.pin)


def _diff(before: str, after: str, name: str) -> list[str]:
    return list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            f"pinned/{name}",
            f"upstream/{name}",
            lineterm="",
        )
    )


def model_diff(
    baseline: Mapping[str, str], upstream: Mapping[str, str]
) -> tuple[list[str], list[str]]:
    """Return the modules that differ and a unified diff of them."""
    changed = sorted(
        name
        for name in set(baseline) | set(upstream)
        if baseline.get(name) != upstream.get(name)
    )
    lines = [
        line
        for name in changed
        for line in _diff(baseline.get(name, ""), upstream.get(name, ""), name)
    ]
    return changed, lines


@dataclass(frozen=True)
class DraftChange:
    """What upstream changes, of what this codebase depends on."""

    problems: tuple[str, ...] = ()
    changed_modules: tuple[str, ...] = ()
    model_diff: tuple[str, ...] = ()
    fields: tuple[AffectedField, ...] = ()
    profiles_diff: tuple[str, ...] = ()
    tests_added: tuple[str, ...] = ()
    tests_removed: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Whether anything the models, profiles or test list depend on changed."""
        return bool(
            self.problems
            or self.changed_modules
            or self.fields
            or self.profiles_diff
            or self.tests_added
            or self.tests_removed
        )


def compare_schemas(
    pin: CsafPin,
    upstream: Path,
    *,
    pinned: Path = PINNED_COPY_DIR,
    read_fields: Sequence[ReadField] = READ_FIELDS,
    render: Renderer = render_models,
) -> DraftChange:
    """Compare the models from *upstream*'s schemas with the pinned ones.

    The models are generated only when the two schema sets differ once
    annotations are dropped: equal inputs generate equal models.
    """
    before = SchemaSet.read(pin, pinned, frozen=pinned)
    if before.problems:
        raise ValueError(
            f"the pinned local copy is incomplete: {list(before.problems)}"
        )
    after = SchemaSet.read(pin, upstream, frozen=pinned)
    fields = tuple(affected_fields(before, after, read_fields))
    if after.problems:
        return DraftChange(problems=after.problems, fields=fields)
    if after.files == before.files:
        return DraftChange(fields=fields)
    changed, lines = model_diff(
        _models_of(before, render), _models_of(after, render)
    )
    return DraftChange(
        changed_modules=tuple(changed), model_diff=tuple(lines), fields=fields
    )


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def compare_profiles(baseline: Path, upstream: Path) -> tuple[list[str], str]:
    """Return a diff of the profile text, and a problem when upstream lost it.

    A profile text upstream that is gone or not UTF-8 is a problem to report.

    Raises:
        FileNotFoundError: *baseline*, the pinned checkout, has no profiles.
    """
    before = _read_text(baseline / PROFILES_FILE)
    if before is None:
        raise FileNotFoundError(baseline / PROFILES_FILE)
    try:
        after = _read_text(upstream / PROFILES_FILE)
    except UnicodeDecodeError:
        return [], f"`{PROFILES_FILE}` is not UTF-8 upstream"
    if after is None:
        return [], f"`{PROFILES_FILE}` is gone upstream"
    lines = [line.rstrip() for line in before.splitlines()]
    new_lines = [line.rstrip() for line in after.splitlines()]
    if lines == new_lines:
        return [], ""
    return (
        _diff("\n".join(lines), "\n".join(new_lines), str(PROFILES_FILE)),
        "",
    )


def mandatory_tests(clone: Path) -> set[str]:
    """Return the IDs of the mandatory tests in *clone*'s test-case index."""
    return {
        case.id
        for case in load_corpus_index(clone).tests
        if case.group == MANDATORY_GROUP
    }


def compare_tests(
    baseline: Path, upstream: Path
) -> tuple[list[str], list[str], str]:
    """Return the mandatory tests added and removed, and any upstream problem.

    Raises:
        FileNotFoundError, MetadataLoadError: the pinned checkout's index is
            missing or malformed, which is a fault of the run, not a change.
    """
    before = mandatory_tests(baseline)
    try:
        after = mandatory_tests(upstream)
    except FileNotFoundError:
        return [], [], f"`{TESTCASES_FILE}` is gone upstream"
    except MetadataLoadError as exc:
        return [], [], f"`{TESTCASES_FILE}` no longer reads upstream: {exc}"
    return (
        sorted(after - before, key=_test_order),
        sorted(before - after, key=_test_order),
        "",
    )


def _test_order(test_id: str) -> tuple[tuple[int, str], ...]:
    """Order test IDs such as ``6.1.9`` before ``6.1.10``."""
    return tuple(
        (int(part), "") if part.isdigit() else (-1, part)
        for part in test_id.split(".")
    )


def compare(
    pin: CsafPin,
    baseline: Path,
    upstream: Path,
    *,
    pinned: Path = PINNED_COPY_DIR,
    read_fields: Sequence[ReadField] = READ_FIELDS,
    render: Renderer = render_models,
) -> DraftChange:
    """Compare the upstream checkout with the pinned checkout and local copy."""
    schemas = compare_schemas(
        pin, upstream, pinned=pinned, read_fields=read_fields, render=render
    )
    profiles, profiles_problem = compare_profiles(baseline, upstream)
    added, removed, tests_problem = compare_tests(baseline, upstream)
    problems = schemas.problems + tuple(
        p for p in (profiles_problem, tests_problem) if p
    )
    return DraftChange(
        problems=problems,
        changed_modules=schemas.changed_modules,
        model_diff=schemas.model_diff,
        fields=schemas.fields,
        profiles_diff=tuple(profiles),
        tests_added=tuple(added),
        tests_removed=tuple(removed),
    )
