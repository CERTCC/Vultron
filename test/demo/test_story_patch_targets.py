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

``coordinated_story`` and ``vendor_story`` are packages whose ``__init__``
only re-exports names (CS-18-003).  A fragment looks each collaborator up in
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
"""

import ast
import importlib
import pathlib
import pkgutil
from types import ModuleType
from unittest.mock import patch

import pytest

from vultron.demo.helpers import coordinated_story, vendor_story

#: The packages a module split produced, by dotted name.
_PACKAGES: tuple[ModuleType, ...] = (coordinated_story, vendor_story)

#: The calls whose first two arguments are a module and a name to replace.
_PATCHERS = frozenset(
    {
        "patch.object",
        "mock.patch.object",
        "monkeypatch.setattr",
        "patch_chain_shared",
    }
)

_TEST_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _submodules(package: ModuleType) -> dict[str, ModuleType]:
    return {
        info.name: importlib.import_module(f"{package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(package.__path__)
    }


def _looked_up_in_a_function(module: ModuleType, name: str) -> bool:
    """Whether a function of *module* reads *name* from the module globals."""
    tree = ast.parse(pathlib.Path(module.__file__ or "").read_text())
    return any(
        isinstance(node, ast.Name)
        and node.id == name
        and isinstance(node.ctx, ast.Load)
        for func in ast.walk(tree)
        if isinstance(func, ast.FunctionDef)
        for node in ast.walk(func)
    )


def _module_bindings(tree: ast.Module) -> dict[str, str]:
    """Each local name an import binds to a module, by its dotted path."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bound[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bound[alias.asname or alias.name] = (
                    f"{node.module}.{alias.name}"
                )
    return bound


def _dotted(expr: ast.expr, bound: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Name):
        return bound.get(expr.id)
    if isinstance(expr, ast.Attribute):
        head = _dotted(expr.value, bound)
        return None if head is None else f"{head}.{expr.attr}"
    return None


def _patch_targets(source: str) -> list[tuple[int, str, str]]:
    """``(line, module, name)`` for every patch in *source*.

    Covers ``patch.object(module, "name")`` and its kin (:data:`_PATCHERS`)
    and the dotted-string form ``patch("package.module.name")``.
    """
    tree = ast.parse(source)
    bound = _module_bindings(tree)
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = ast.unparse(node.func)
        if (
            func in _PATCHERS
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            module = _dotted(node.args[0], bound)
            if module is not None:
                found.append((node.lineno, module, node.args[1].value))
        elif (
            func in {"patch", "mock.patch"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            module, _, name = node.args[0].value.rpartition(".")
            found.append((node.lineno, module, name))
    return found


def _misdirected(source: str, where: str) -> list[str]:
    """Every patch in *source* that reaches no fragment of a split package."""
    problems: list[str] = []
    for line, module, name in _patch_targets(source):
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

    assert held == set(package.__all__) | set(_submodules(package))


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


def test_the_scan_flags_a_patch_pointed_at_the_package() -> None:
    """The guard below fails for each form a misdirected patch takes."""
    source = (
        "from vultron.demo.helpers import coordinated_story\n"
        "from vultron.demo.helpers.vendor_story import cast as vendor_cast\n"
        "patch.object(coordinated_story, 'open_coordinated_cast')\n"
        "patch('vultron.demo.helpers.vendor_story.open_vendor_cast')\n"
        "patch.object(vendor_cast, 'verify_publicly_disclosed')\n"
        "patch.object(vendor_cast, 'seed_containers')\n"
    )

    problems = _misdirected(source, "example.py")

    assert [p.split(":")[1] for p in problems] == ["3", "4", "5"], problems


def test_every_patch_on_a_split_package_names_the_resolving_submodule() -> (
    None
):
    """Read over the whole test tree, so a new patch is checked too."""
    problems = [
        problem
        for path in sorted(_TEST_ROOT.rglob("*.py"))
        for problem in _misdirected(
            path.read_text(), str(path.relative_to(_TEST_ROOT.parent))
        )
    ]

    assert not problems, "\n".join(problems)
