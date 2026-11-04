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

"""A patch on a split story package must name the submodule (#5592 AC-3).

``coordinated_story``, ``vendor_story``, ``story`` and
``owner_decision_story`` are packages whose ``__init__`` only re-exports
names (CS-18-003).  A fragment looks each collaborator up in
the globals of the submodule that defines it, so a ``patch.object`` against
the package replaces a name no fragment reads: the test runs the real
collaborator, against a ``MagicMock`` client, and may still pass.  This area
has lost a patch that way three times (#5534, #5536).

Two guards close it:

* The package holds nothing but its submodules and its ``__all__``, so a
  patch on a collaborator the package never re-exports raises
  ``AttributeError`` instead of passing over nothing.
* Every patch in ``test/`` that targets one of the packages is read from the
  source: its target must be a submodule, and that submodule must look the
  name up inside one of its functions.  That catches the case the first guard
  cannot — a patch on a re-exported public name, such as
  ``open_coordinated_cast``, which the package does hold.

``rcvcv_demo`` is a module, and the fragments only it tells live in
``helpers/rcvcv_story.py``.  A patch on either flat module is held to the
second rule too, so one left on ``rcvcv_demo`` for a name only
``rcvcv_story`` looks up is reported.
"""

import ast
import functools
import importlib
import pathlib
from types import ModuleType
from unittest.mock import patch

import pytest

from test.demo._helpers import modules_resolving_names
from vultron.demo.helpers import (
    coordinated_story,
    owner_decision_story,
    rcvcv_story,
    story,
    vendor_story,
)
from vultron.demo.scenario import rcvcv_demo

#: The packages a module split produced, by dotted name.
_PACKAGES: tuple[ModuleType, ...] = (
    coordinated_story,
    vendor_story,
    story,
    owner_decision_story,
)

#: The flat modules a split left in place, or moved fragments into: a patch
#: on one must name a name it looks up.
_FLAT_MODULES: tuple[ModuleType, ...] = (rcvcv_demo, rcvcv_story)

#: Calls whose first two arguments are a module and a name to replace, by the
#: last two parts of the called name, so ``patch.object``,
#: ``mock.patch.object`` and ``unittest.mock.patch.object`` all match.
_OBJECT_PATCHERS = frozenset(
    {"patch.object", "monkeypatch.setattr", "patch_chain_shared"}
)

#: Calls whose first argument is a dotted ``"module.name"`` target.
_DOTTED_PATCHERS = frozenset({"patch", "mock.patch", "monkeypatch.setattr"})

#: ``patch.multiple``'s own keywords; every other keyword names an attribute.
_MULTIPLE_OPTIONS = frozenset(
    {"spec", "create", "spec_set", "autospec", "new_callable"}
)

_TEST_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _submodules(package: ModuleType) -> dict[str, ModuleType]:
    """Each module below *package*, by its dotted name relative to it."""
    prefix = f"{package.__name__}."
    return {
        module.__name__.removeprefix(prefix): module
        for module in modules_resolving_names(package)
    }


def _looked_up_in_a_function(module: ModuleType, name: str) -> bool:
    """Whether a function body of *module* reads *name* from its globals.

    A default argument is evaluated once, when the module is imported, so a
    patch applied later never reaches it: defaults are left out.
    """
    return name in _names_read_in_function_bodies(module.__file__ or "")


@functools.cache
def _names_read_in_function_bodies(path: str) -> frozenset[str]:
    tree = ast.parse(pathlib.Path(path).read_text())
    return frozenset(
        node.id
        for func in ast.walk(tree)
        if isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef)
        for statement in func.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    )


def _module_bindings(tree: ast.Module) -> dict[str, str]:
    """Each local name an import binds, by the dotted path it stands for."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bound[alias.asname] = alias.name
                else:
                    top = alias.name.partition(".")[0]
                    bound[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bound[alias.asname or alias.name] = (
                    f"{node.module}.{alias.name}"
                )
    return bound


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """Each module-level name bound to a string literal, by its value."""
    constants: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign | ast.AnnAssign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            targets = (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            for target in targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    return constants


def _dotted(expr: ast.expr, bound: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Name):
        return bound.get(expr.id)
    if isinstance(expr, ast.Attribute):
        head = _dotted(expr.value, bound)
        return None if head is None else f"{head}.{expr.attr}"
    return None


def _string(expr: ast.expr | None, constants: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        return constants.get(expr.id)
    return None


def _argument(call: ast.Call, position: int, keyword: str) -> ast.expr | None:
    if len(call.args) > position:
        return call.args[position]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def _patch_targets(source: str) -> list[tuple[int, str, str]]:
    """``(line, module, name)`` for every patch in *source*.

    Reads ``patch.object(module, "name")`` and its kin, positional or by
    keyword; the dotted-string form ``patch("package.module.name")``, also as
    ``monkeypatch.setattr("package.module.name", value)`` and through a
    module-level string constant; and ``patch.multiple(module, name=...)``.
    A module held in a local variable is not followed: name the module
    directly in the patch.
    """
    tree = ast.parse(source)
    bound = _module_bindings(tree)
    constants = _string_constants(tree)
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = ".".join(ast.unparse(node.func).split(".")[-2:])
        first = _argument(node, 0, "target")
        dotted = _string(first, constants)
        if called in _DOTTED_PATCHERS and dotted is not None:
            dotted_module, _, dotted_name = dotted.rpartition(".")
            found.append((node.lineno, dotted_module, dotted_name))
        elif called in _OBJECT_PATCHERS and first is not None:
            target = _dotted(first, bound)
            attribute = _string(
                _argument(node, 1, "attribute") or _argument(node, 1, "name"),
                constants,
            )
            if target is not None and attribute is not None:
                found.append((node.lineno, target, attribute))
        elif called == "patch.multiple" and first is not None:
            several = _dotted(first, bound) or dotted
            if several is not None:
                found.extend(
                    (node.lineno, several, k.arg)
                    for k in node.keywords
                    if k.arg is not None and k.arg not in _MULTIPLE_OPTIONS
                )
    return found


def _misdirected(source: str, where: str) -> list[str]:
    """Every patch in *source* that reaches no fragment of a split package.

    A floor, not proof that a patch reaches the fragment a test runs: a name
    several submodules look up (``demo_check``,
    ``wait_for_case_participants``) passes on any of them, and only the test
    itself, run against a patch on the wrong one, can tell.
    """
    problems: list[str] = []
    for line, module, name in _patch_targets(source):
        for flat in _FLAT_MODULES:
            if module == flat.__name__ and not _looked_up_in_a_function(
                flat, name
            ):
                problems.append(
                    f"{where}:{line}: patches {name!r} on {module}, which "
                    "never looks it up, so the patch intercepts nothing"
                )
        for package in _PACKAGES:
            if module == package.__name__:
                problems.append(
                    f"{where}:{line}: patches {name!r} on the package "
                    f"{module}; patch the submodule that looks it up"
                )
                continue
            prefix = f"{package.__name__}."
            if not module.startswith(prefix):
                continue
            submodule = _submodules(package).get(module.removeprefix(prefix))
            if submodule is None:
                continue
            if not _looked_up_in_a_function(submodule, name):
                problems.append(
                    f"{where}:{line}: patches {name!r} on {module}, which "
                    "never looks it up, so the patch intercepts nothing"
                )
    return problems


@pytest.mark.parametrize("package", _PACKAGES, ids=lambda p: p.__name__)
def test_the_package_holds_only_its_submodules_and_its_public_names(
    package: ModuleType,
) -> None:
    """Nothing else, so a patch on a collaborator here raises.

    A collaborator a fragment imports — a poll, a trigger, a banner — is
    never an attribute of the package, so ``patch.object`` refuses it
    instead of creating an attribute no fragment reads.
    """
    held = {name for name in vars(package) if not name.startswith("__")}
    top_level = {name.partition(".")[0] for name in _submodules(package)}

    assert held == set(package.__all__) | top_level


@pytest.mark.parametrize(
    ("package", "name"),
    [
        (coordinated_story, "wait_for_case_participants"),
        (coordinated_story, "run_case_invite_chain"),
        (vendor_story, "seed_containers"),
        (vendor_story, "verify_publicly_disclosed"),
    ],
    ids=lambda v: getattr(v, "__name__", v),
)
def test_a_patch_on_the_package_is_refused(
    package: ModuleType, name: str
) -> None:
    """The loud case: the package has no such attribute to replace."""
    patcher = patch.object(package, name)

    with pytest.raises(AttributeError):
        patcher.start()


@pytest.mark.parametrize(
    "line",
    [
        "patch.object(coordinated_story, 'open_coordinated_cast')",
        "patch.object(target=coordinated_story, attribute='close_the_case')",
        "patch('vultron.demo.helpers.vendor_story.open_vendor_cast')",
        "mock.patch(target='vultron.demo.helpers.vendor_story.vendor_seats')",
        "patch(_TARGET)",
        "monkeypatch.setattr('vultron.demo.helpers.vendor_story.VENDOR', 1)",
        "monkeypatch.setattr(coordinated_story, 'REPORTER', 'x')",
        "patch.multiple(coordinated_story, everyone_closes=None)",
        "patch.object(vultron.demo.helpers.coordinated_story, 'COORDINATOR')",
        "patch.object(vendor_cast, 'verify_publicly_disclosed')",
    ],
)
def test_the_scan_flags_each_misdirected_form(line: str) -> None:
    """Each form a patch on the package, or on a submodule that never looks
    the name up, can take is reported."""
    source = (
        "import vultron.demo.helpers.coordinated_story\n"
        "from unittest import mock\n"
        "from vultron.demo.helpers import coordinated_story\n"
        "from vultron.demo.helpers.vendor_story import cast as vendor_cast\n"
        "_TARGET = 'vultron.demo.helpers.coordinated_story.everyone_closes'\n"
        f"{line}\n"
    )

    problems = _misdirected(source, "example.py")

    assert [p.split(":")[1] for p in problems] == ["6"], problems


@pytest.mark.parametrize(
    "line",
    [
        "patch.object(vendor_cast, 'seed_containers')",
        "patch('vultron.demo.helpers.vendor_story.cast.seed_containers')",
        "patch.object(target=vendor_cast, attribute='seed_containers')",
    ],
)
def test_the_scan_passes_a_patch_on_the_resolving_submodule(
    line: str,
) -> None:
    """The check is not vacuous the other way: a right patch is let through."""
    source = (
        "from vultron.demo.helpers.vendor_story import cast as vendor_cast\n"
        f"{line}\n"
    )

    assert _misdirected(source, "example.py") == []


def test_a_default_argument_is_not_a_look_up(tmp_path: pathlib.Path) -> None:
    """A default is read once at import, so a later patch never reaches it."""
    path = tmp_path / "example.py"
    path.write_text("def f(x=CONSTANT):\n    return x\n")
    module = ModuleType("example")
    module.__file__ = str(path)

    assert not _looked_up_in_a_function(module, "CONSTANT")


def test_every_patch_on_a_split_package_names_the_resolving_submodule() -> (
    None
):
    """Read over the whole test tree, so a new patch is checked too.

    The count guards the scan itself: a reader that stopped recognising the
    tree's patches would report no problem and pass over every one.
    """
    # A file that never names a package cannot import or patch it, so only
    # the files that do are parsed.
    package_names = tuple(
        p.__name__.rpartition(".")[2] for p in _PACKAGES + _FLAT_MODULES
    )
    texts = {
        str(path.relative_to(_TEST_ROOT.parent)): path.read_text()
        for path in sorted(_TEST_ROOT.rglob("*.py"))
    }
    sources = {
        where: text
        for where, text in texts.items()
        if any(name in text for name in package_names)
    }
    on_a_package = [
        target
        for source in sources.values()
        for target in _patch_targets(source)
        if target[1].startswith(tuple(p.__name__ for p in _PACKAGES))
    ]
    problems = [
        problem
        for where, source in sources.items()
        for problem in _misdirected(source, where)
    ]

    assert len(on_a_package) > 100, len(on_a_package)
    assert not problems, "\n".join(problems)


def test_a_nested_subpackage_is_read_too(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A submodule split into a package of its own is still walked."""
    root = tmp_path / "story_pkg_5592"
    (root / "inner").mkdir(parents=True)
    for init in (root / "__init__.py", root / "inner" / "__init__.py"):
        init.write_text("")
    (root / "flat.py").write_text("")
    (root / "inner" / "deep.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    package = importlib.import_module("story_pkg_5592")

    names = sorted(m.__name__ for m in modules_resolving_names(package))

    assert names == ["story_pkg_5592.flat", "story_pkg_5592.inner.deep"]


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ("patch.object(demo, 'wait_for_participant_vf_state')", True),
        (
            "patch('vultron.demo.scenario.rcvcv_demo."
            "wait_for_participant_vf_state')",
            True,
        ),
        ("patch.object(rcvcv_story, 'wait_for_participant_vf_state')", False),
        ("patch.object(demo, 'dump_story_ledgers')", False),
    ],
)
def test_a_patch_on_a_flat_module_must_name_a_name_it_looks_up(
    line: str, flagged: bool
) -> None:
    """A fragment that moved to ``rcvcv_story`` is no longer patched through
    ``rcvcv_demo``, and a name ``rcvcv_demo`` still reads is let through."""
    source = (
        "import vultron.demo.scenario.rcvcv_demo as demo\n"
        "from vultron.demo.helpers import rcvcv_story\n"
        f"{line}\n"
    )

    problems = _misdirected(source, "example.py")

    assert bool(problems) is flagged, problems
