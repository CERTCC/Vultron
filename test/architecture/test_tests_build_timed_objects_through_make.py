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
importing the model packages, so a renamed or new class is covered without an
edit here.  A direct call names one: a bare name imported from ``vultron`` or
``test``, a class the test file derives from one, or an attribute of a module
(``vocab.as_Note(...)``).

:data:`DIRECT_BUILD_EXEMPTIONS` is a pinned exemption set (ARCH-18-001): the
files that test a model's own time default, which must call it bare.

Spec: CS-13-002 (time enters at the act's edge), ARCH-18-001.
"""

import ast
import importlib
import pkgutil
import re
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path

import pytest
from pydantic import BaseModel

from test.architecture import _corpus
from test.support.objects import stamped_times

_TEST_ROOT = _corpus.REPO_ROOT / "test"
_FACTORY = "test/support/objects.py"
_MODEL_PACKAGES = ("vultron.core.models", "vultron.wire.as2.vocab")

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
def timed_names() -> frozenset[str]:
    """Every name a ``vultron`` module binds to a class ``make`` stamps."""
    for package_name in _MODEL_PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(
            package.__path__, package_name + "."
        ):
            importlib.import_module(info.name)
    return frozenset(
        name
        for module_name, module in list(sys.modules.items())
        if module_name.startswith("vultron")
        for name, value in list(vars(module).items())
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and stamped_times(value)
    )


def _base_name(node: ast.expr) -> str | None:
    return _corpus.callee_name(node)


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
                _base_name(base) in local | names for base in cls.bases
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
    the parse: ``Name(`` for a call, ``Name):`` for a local subclass."""
    return re.compile(
        r"\b(?:" + "|".join(map(re.escape, sorted(names))) + r")(?:\(|\):)"
    )


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


_EVERY_SHAPE = """
from vultron.core.models.case import VulnerabilityCase as Case
from vultron.wire.as2.vocab.objects import as_Note
from somewhere_else import CaseStatus


class Local(Case):
    pass


def test_x(vocab):
    Case(attributed_to="a")
    Local()
    vocab.as_Note(content="c")
    make(Case, attributed_to="a")
    CaseStatus()
    factory().as_Note()
    Case.model_validate({})
"""


@pytest.mark.spec("ARCH-18-001")
def test_the_finder_names_each_direct_build_and_nothing_else() -> None:
    tree = _corpus.parse_inline(_EVERY_SHAPE)

    lines = sorted(direct_builds_in(tree, timed_names()))

    assert lines == [12, 13, 14]


@pytest.mark.spec("ARCH-18-001")
@pytest.mark.parametrize(
    ("source", "scanned"),
    [
        ("VulnerabilityCase(attributed_to=a)", True),
        ("class Local(as_Note):", True),
        ("make(VulnerabilityCase, attributed_to=a)", False),
        ("isinstance(x, as_Note)", False),
    ],
)
def test_the_prefilter_keeps_every_file_that_may_hold_a_direct_build(
    source: str, scanned: bool
) -> None:
    assert bool(_spelling(timed_names()).search(source)) is scanned
