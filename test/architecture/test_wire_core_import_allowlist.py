#!/usr/bin/env python

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
"""Architecture boundary test: the wire→core import allow-list.

``vultron/wire/`` MAY import the object model and the state definitions it
serializes.  It MUST NOT import anything else under ``vultron/core/``.

Spec: ARCH-22-001, ARCH-22-002, ARCH-22-003.  ADR-0099 detail 6.

Two properties this test exists to hold, both easy to lose in a rewrite:

1. **The rule attaches to the importing directory.**  "Nothing under
   ``vultron/wire/`` may import core behaviour" cannot be evaded by moving a
   file, the way a rule phrased as "only this blessed subdirectory may import
   core" can be.
2. **It is an allow-list, not a deny-list.**  A core package added tomorrow is
   forbidden until someone decides otherwise.  A deny-list would permit it
   until someone remembered to add it.

There is deliberately no ``KNOWN_VIOLATIONS`` set here.  This replaces the
ARCH-22 ratchet (a 20-entry violations list, two two-sided tests and an
``xfail(strict=True)`` goal test) that ADR-0099 repealed along with the rule it
enforced.  The lesson that ratchet taught is recorded in ARCH-22-003: a goal
test asserting an unreachable state invites an implementer to violate a MUST in
order to make it pass, which is worse than having no goal test.  The allow-list
below is satisfied by the tree as it stands, so it is an invariant rather than
a target, and needs no goal test at all.

Known limits, in descending order of how much they matter:

1. **A ``TYPE_CHECKING``-guarded import of a forbidden package passes.** The
   exemption is general rather than per-file, and is stated in ARCH-22-001
   itself: the import is erased at runtime, so it can only appear in an
   annotation and cannot create a runtime dependency.  The cost is that
   ``if TYPE_CHECKING: from vultron.core.behaviors import X`` is not caught here.
   Exempting generally rather than carving out the one file that needed it is
   deliberate — a one-entry exemption list is what ADR-0099 removed.
2. **Imports resolved from a string at runtime**
   (``importlib.import_module("vultron.core.behaviors")``) are invisible to an
   AST scan, as they were to the ratchet this replaces.
3. **A capability reached by duck-typing** rather than by import — the coupling
   ADR-0099 found the old rule had missed entirely.

ARCH-01-003 ("no domain logic in wire") is the requirement that covers 2 and 3;
this test covers imports.
"""

import ast

import pytest

from test.architecture import _corpus

_CORE_MODULE = "vultron.core"

_WIRE_ROOT = _corpus.REPO_ROOT / "vultron" / "wire"

# ---------------------------------------------------------------------------
# The allow-list (ADR-0099 detail 6).
#
# ``models/`` is the object model itself: AS2 is a serialization of those
# classes, so the message shapes in ``wire/`` necessarily name them.
# ``states/`` holds the protocol state enumerations and the transition and
# invariant declarations over them — data shapes that a wire representation has
# to be able to spell.
#
# Everything else under ``vultron/core/`` is forbidden *by omission*, which is
# the point: adding a package to ``vultron/core/`` does not silently widen what
# wire may reach for.
#
# AC-6 judgement calls, which ADR-0099 left undecided:
#
# * ``vultron/core/case_states/`` — FORBIDDEN.  Despite the name it is not a
#   set of state definitions.  ``hypercube.py`` builds a networkx DiGraph over
#   the CVD case-state model and walks it (random walks, path enumeration,
#   pandas/numpy scoring); ``validations.py`` is a family of decorators that
#   enforce pattern/state/history well-formedness; ``make_doc.py`` generates
#   documentation.  That is behaviour, and behaviour is what the allow-list
#   exists to keep out of wire.  The bare state enumerations wire could
#   legitimately need (``CS_vf``, ``CS_d``, ``pxa``, ``vfd``) live in
#   ``vultron/core/states/``, which is already allowed — so forbidding this
#   package costs wire nothing.
# * ``vultron/core/participants/`` — FORBIDDEN.  It is a service, not a data
#   shape: ``authority.py`` and ``_lookup.py`` take a ``CasePersistence`` port
#   and resolve participants and case-manager authority through it.  A wire
#   module reaching for that would be doing domain work.  ADR-0099 detail 6
#   already named ``participants/`` in its forbidden list; this confirms the
#   classification rather than revisiting it.
# ---------------------------------------------------------------------------
ALLOWED_CORE_PACKAGES: frozenset[str] = frozenset(
    {
        "vultron.core.models",
        "vultron.core.states",
    }
)


def _is_core(module: str) -> bool:
    """Return True if *module* names ``vultron.core`` or anything inside it."""
    return module == _CORE_MODULE or module.startswith(_CORE_MODULE + ".")


def _is_allowed(module: str) -> bool:
    """Return True if *module* falls inside an allow-listed core package."""
    return any(
        module == allowed or module.startswith(allowed + ".")
        for allowed in ALLOWED_CORE_PACKAGES
    )


def _is_type_checking_test(test: ast.expr) -> bool:
    """Return True if *test* is ``TYPE_CHECKING`` or ``<mod>.TYPE_CHECKING``."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _type_checking_import_nodes(tree: ast.AST) -> set[ast.stmt]:
    """Return the import nodes that sit inside an ``if TYPE_CHECKING:`` body.

    TYPE_CHECKING-only imports are exempt from the allow-list — generally, not
    by naming the one file that has one today.  The reasoning: such an import
    is erased at runtime, so it creates no dependency for the interpreter to
    resolve and nothing for wire to *call*.  It can only be used in an
    annotation, which means it cannot be a route around the rule: a wire module
    cannot invoke a core behaviour it imported under TYPE_CHECKING.  Wire stays
    replaceable as a unit, which is the property ADR-0009 rule 6 actually asks
    for.

    Exempting the one current case instead — ``vultron/wire/as2/rehydration.py``,
    whose ``DataLayer`` reference is TYPE_CHECKING-only — would have been a
    violation list with one entry, and ADR-0099 removed this test's violation
    list on purpose.

    The exemption is narrow in the way that matters: it is lexical, so moving
    the import out of the guard to use it at runtime makes the test fail again.
    """
    guarded: set[ast.stmt] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            for stmt in node.body:
                for inner in ast.walk(stmt):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        guarded.add(inner)
    return guarded


def _core_modules_imported(tree: ast.AST) -> set[str]:
    """Return the ``vultron.core.*`` module names *tree* imports at runtime.

    Walks the whole tree rather than only ``tree.body``, so a deferred import
    inside a function body is caught too — the evasion the ratchet this
    replaces also guarded against.  ``if TYPE_CHECKING:`` imports are excluded;
    see :func:`_type_checking_import_nodes`.
    """
    guarded = _type_checking_import_nodes(tree)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if node in guarded:
            continue
        if isinstance(node, ast.ImportFrom):
            # A relative import cannot escape ``vultron.wire`` into
            # ``vultron.core`` without also naming it, so level > 0 is never a
            # core import from a wire module.
            if node.level:
                continue
            module = node.module or ""
            if module in (_CORE_MODULE, "vultron"):
                # ``from vultron.core import models`` / ``from vultron import
                # core`` — the imported package is on the alias, not the
                # module.
                modules.update(
                    f"{module}.{alias.name}"
                    for alias in node.names
                    if _is_core(f"{module}.{alias.name}")
                )
            elif _is_core(module):
                modules.add(module)
        elif isinstance(node, ast.Import):
            modules.update(
                alias.name for alias in node.names if _is_core(alias.name)
            )
    return modules


def _collect_violations() -> list[str]:
    """Return ``path: imports module`` lines for every disallowed core import."""
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _CORE_MODULE, "vultron import core", under=_WIRE_ROOT
    ):
        rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
        for module in sorted(_core_modules_imported(tree)):
            if not _is_allowed(module):
                violations.append(f"{rel}: imports {module}")
    return violations


@pytest.mark.spec("ARCH-22-001")
@pytest.mark.spec("ARCH-22-002")
def test_wire_imports_only_allow_listed_core_packages() -> None:
    """No module under ``vultron/wire/`` may import outside the core allow-list.

    Spec: ARCH-22-001, ARCH-22-002.  ADR-0099 detail 6.
    """
    violations = _collect_violations()

    assert not violations, (
        "wire→core imports outside the ARCH-22-001 allow-list:\n"
        + "\n".join(f"  {v}" for v in sorted(violations))
        + "\n\nWire MAY import only: "
        + ", ".join(sorted(ALLOWED_CORE_PACKAGES))
        + ".\nEverything else under vultron/core/ is forbidden — including a "
        "package\nadded since this allow-list was written.  Widening the "
        "allow-list is an\narchitecture decision: amend ARCH-22-001 first.  "
        "A deferred import inside\na function body is the same violation as a "
        "top-level one."
    )


# ---------------------------------------------------------------------------
# Detector validation.  The assertion above passes on a clean tree, so these
# synthetic cases are what shows it would still fail on a dirty one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "from vultron.core.behaviors.case import nodes\n",
            id="top-level-from-import",
        ),
        pytest.param(
            "import vultron.core.dispatcher\n",
            id="top-level-plain-import",
        ),
        pytest.param(
            "from vultron.core import use_cases\n",
            id="package-on-the-alias",
        ),
        pytest.param(
            "def f():\n    from vultron.core.ports.datalayer import DataLayer\n",
            id="deferred-import-in-function-body",
        ),
        pytest.param(
            "from vultron.core.case_states.hypercube import CVDmodel\n",
            id="case-states-is-forbidden",
        ),
        pytest.param(
            "from vultron.core.participants.authority import x\n",
            id="participants-is-forbidden",
        ),
        pytest.param(
            "from vultron.core.not_yet_invented import thing\n",
            id="unknown-package-forbidden-by-default",
        ),
    ],
)
@pytest.mark.spec("ARCH-22-002")
def test_detector_flags_disallowed_import(source: str) -> None:
    """Each synthetic forbidden import is reported as a violation.

    Spec: ARCH-22-002.
    """
    tree = _corpus.parse_inline(source)
    modules = _core_modules_imported(tree)

    assert modules, f"detector saw no core import in:\n{source}"
    assert not any(_is_allowed(module) for module in modules)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "from vultron.core.models.case import VulnerabilityCase\n",
            id="models-allowed",
        ),
        pytest.param(
            "from vultron.core.states.cs import pxa\n",
            id="states-allowed",
        ),
        pytest.param(
            "from vultron.core import models\n",
            id="models-on-the-alias-allowed",
        ),
    ],
)
@pytest.mark.spec("ARCH-22-001")
def test_detector_permits_allow_listed_import(source: str) -> None:
    """Each synthetic allow-listed import is accepted.

    Spec: ARCH-22-001.
    """
    tree = _corpus.parse_inline(source)
    modules = _core_modules_imported(tree)

    assert modules, f"detector saw no core import in:\n{source}"
    assert all(_is_allowed(module) for module in modules)


@pytest.mark.spec("ARCH-22-001")
def test_detector_exempts_type_checking_only_import() -> None:
    """A TYPE_CHECKING-guarded core import is not a runtime dependency.

    Spec: ARCH-22-001.  See :func:`_type_checking_import_nodes` for why the
    exemption is general rather than a one-file carve-out.
    """
    guarded = _corpus.parse_inline(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from vultron.core.ports.datalayer import DataLayer\n"
    )
    assert _core_modules_imported(guarded) == set()

    # Lexical, not semantic: the same import outside the guard still fails.
    unguarded = _corpus.parse_inline(
        "from vultron.core.ports.datalayer import DataLayer\n"
    )
    assert _core_modules_imported(unguarded) == {
        "vultron.core.ports.datalayer"
    }
