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
"""Architecture ratchet: a test builds a timed object through ``make``.

A core object, a wire object, a case status and an embargo carry their
author's time, which a core model takes from the act and never reads from the
clock (ADR-0176).  A test states that time in one place,
``test/support/objects.py``'s ``make``, so this test fails on a direct call of
such a class anywhere else under ``test/``.

A *timed class* is any model ``make`` stamps (``stamped_times``), found by
importing every ``vultron`` module, so a renamed or new class is covered
without an edit here.  A direct call names one: a bare name imported from
``vultron`` or ``test`` (aliased or not), a class the test file derives from
one, or an attribute of a module (``vocab.as_Note(...)``).  A class held in a
variable (``cls(...)``) is beyond a static read; such a test calls
``make(cls, ...)`` by the same rule.

:data:`DIRECT_BUILD_EXEMPTIONS` is a pinned exemption set (ARCH-18-001): the
files that test a model's own time default, which must call it bare.

Spec: CS-13-002 (time enters at the act's edge), ARCH-18-001.
"""

import ast
import importlib
import pkgutil
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from pydantic import BaseModel

import vultron
from test.architecture import _corpus
from test.support.objects import AUTHOR_TIMES, stamped_times
from vultron.core.models._helpers.clock import now_utc

_TEST_ROOT = _corpus.REPO_ROOT / "test"
_FACTORY = "test/support/objects.py"

# Pinned exemption set: files that test what a model does with a time its
# caller leaves out, so they build it without ``make`` on purpose.
# permanent: ADR-0176 (the default under test goes when the time is required,
# #5758)
DIRECT_BUILD_EXEMPTIONS: frozenset[str] = frozenset(
    {
        "test/core/models/test_case_status.py",
    }
)


@cache
def _models() -> tuple[tuple[str, type[BaseModel]], ...]:
    """Every ``(name, model)`` binding in every ``vultron`` module.

    Every module is imported, so the result never depends on what the
    session happened to import before this test ran.
    """
    modules = [vultron] + [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(vultron.__path__, "vultron.")
    ]
    return tuple(
        (name, value)
        for module in modules
        for name, value in vars(module).items()
        if isinstance(value, type) and issubclass(value, BaseModel)
    )


@cache
def timed_names() -> frozenset[str]:
    """Every name a ``vultron`` module binds to a class ``make`` stamps."""
    return frozenset(name for name, model in _models() if stamped_times(model))


def _timed_in_file(tree: ast.AST, names: frozenset[str]) -> set[str]:
    """The names *tree* binds to a timed class: imports and local subclasses."""
    local = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.split(".")[0] in {"vultron", "test"}
        for alias in node.names
        if alias.name in names
    }
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    grew = True
    while grew:
        grew = False
        for cls in classes:
            if cls.name not in local and any(
                _corpus.callee_name(base) in local | names
                for base in cls.bases
            ):
                local.add(cls.name)
                grew = True
    return local


def direct_builds_in(tree: ast.AST, names: frozenset[str]) -> Iterator[int]:
    """Line numbers of the direct builds in *tree*; see the module docstring."""
    local = _timed_in_file(tree, names)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id in local) or (
            isinstance(func, ast.Attribute)
            and func.attr in names
            and not isinstance(func.value, ast.Call)
        ):
            yield node.lineno


def _spelling(names: frozenset[str]) -> re.Pattern[str]:
    """What a file must contain to hold a direct build, so most files skip
    the parse: ``Name(`` for a call, ``Name as`` for an aliased import, and a
    ``class`` statement naming one among its bases, on one line or several.
    """
    timed = r"\b(?:" + "|".join(map(re.escape, sorted(names))) + r")"
    return re.compile(
        rf"{timed}(?:\(|\s+as\s+\w)|^\s*class\s+\w+\([^)]*{timed}\b",
        re.MULTILINE,
    )


def direct_builds_in_source(source: str, names: frozenset[str]) -> list[int]:
    """The direct builds in *source*, through the same prefilter the scan
    uses, so a shape the prefilter drops fails the inline test."""
    if not _spelling(names).search(source):
        return []
    return sorted(direct_builds_in(_corpus.parse_inline(source), names))


def _direct_builds() -> dict[str, list[int]]:
    names = timed_names()
    spelled = _spelling(names)
    found: dict[str, list[int]] = {}
    for path, source in _corpus.all_sources(_TEST_ROOT):
        if not spelled.search(source):
            continue
        tree = _corpus.tree_of(path)
        rel = Path(path).relative_to(_corpus.REPO_ROOT).as_posix()
        if rel == _FACTORY:
            continue
        lines = sorted(direct_builds_in(tree, names))
        if lines:
            found[rel] = lines
    return found


@pytest.mark.spec("CS-13-002")
@pytest.mark.spec("ARCH-18-001")
def test_tests_build_timed_objects_through_make() -> None:
    found = _direct_builds()

    new = {
        p: ls for p, ls in found.items() if p not in DIRECT_BUILD_EXEMPTIONS
    }
    stale = DIRECT_BUILD_EXEMPTIONS - found.keys()
    assert not new, (
        "A test builds an object that carries its author's time without"
        " stating the time (ADR-0176).  Build it with"
        " make(cls, **fields) from test/support/objects.py:\n"
        + "\n".join(
            f"  {p}:{line}" for p, ls in sorted(new.items()) for line in ls
        )
    )
    assert not stale, (
        "Exempt files with no direct build left; delete them from"
        f" DIRECT_BUILD_EXEMPTIONS (ARCH-18-002): {sorted(stale)}"
    )


@pytest.mark.spec("CS-13-002")
def test_every_clock_defaulted_author_time_is_one_make_stamps() -> None:
    """An author's time defaulted through another callable than ``now_utc``
    would escape both ``make`` and this ratchet, which key on it."""
    other = sorted(
        {
            f"{model.__module__}.{model.__qualname__}.{field}"
            for _, model in _models()
            for field in AUTHOR_TIMES
            if field in model.model_fields
            and model.model_fields[field].default_factory
            not in (None, now_utc)
        }
    )

    assert other == []


@pytest.mark.spec("ARCH-18-001")
def test_the_timed_names_cover_core_wire_status_and_embargo() -> None:
    """The name set is found, not listed, so check it is not empty."""
    assert {
        "VulnerabilityCase",
        "as_VulnerabilityCase",
        "as_Note",
        "CaseStatus",
        "EmbargoEvent",
    } <= timed_names()


_SHAPES = """
from vultron.core.models.case import VulnerabilityCase
from vultron.wire.as2.vocab.objects import as_Note


def test_x(vocab):
    VulnerabilityCase(attributed_to="a")
    vocab.as_Note(content="c")
"""

_ALIASED = """
from vultron.core.models.case import VulnerabilityCase as Zq


def test_x():
    Zq(attributed_to="a")
"""

_SUBCLASSED = """
from vultron.wire.as2.vocab.objects import as_Note


class Local(
    Mixin,
    as_Note,
):
    pass


def test_x():
    Local()
"""

_NOT_DIRECT = """
from vultron.core.models.case import VulnerabilityCase as Zq
from somewhere_else import CaseStatus


def test_x():
    make(Zq, attributed_to="a")
    CaseStatus()
    factory().as_Note()
    Zq.model_validate({})
"""


@pytest.mark.spec("ARCH-18-001")
@pytest.mark.parametrize(
    ("source", "lines"),
    [
        (_SHAPES, [7, 8]),
        (_ALIASED, [6]),
        (_SUBCLASSED, [13]),
        (_NOT_DIRECT, []),
    ],
    ids=["imported-and-module-attribute", "aliased", "subclassed", "none"],
)
def test_the_scan_names_each_direct_build_and_nothing_else(
    source: str, lines: list[int]
) -> None:
    """Through the prefilter, as the scan reads a file."""
    assert direct_builds_in_source(source, timed_names()) == lines


@pytest.mark.spec("ARCH-18-001")
@pytest.mark.parametrize(
    ("source", "scanned"),
    [
        ("VulnerabilityCase(attributed_to=a)", True),
        ("class Local(as_Note):", True),
        ("class Local(\n    Mixin,\n    as_Note,\n):", True),
        ("from x import VulnerabilityCase as Zq", True),
        ("make(VulnerabilityCase, attributed_to=a)", False),
        ("isinstance(x, as_Note)", False),
    ],
)
def test_the_prefilter_keeps_every_file_that_may_hold_a_direct_build(
    source: str, scanned: bool
) -> None:
    assert bool(_spelling(timed_names()).search(source)) is scanned
