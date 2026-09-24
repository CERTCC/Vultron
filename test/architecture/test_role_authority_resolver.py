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
"""Architecture ratchet: single neutral role-authority resolver (ARCH-24-001..004).

Verifies the ADR-0088 invariant that ``resolve_case_manager_id`` is defined in
exactly one module (``vultron.core.participants.authority``), that neither
``vultron.core.behaviors`` nor ``vultron.core.use_cases`` contains a twin
definition, and that exactly one authority condition node
(``CheckIsCaseManagerNode``) exists — with the old Service-based nodes removed.

Also ratchets the *negative* half of the ADR.  ARCH-24-004 names **two** retired
signals and both are covered here:

- the ``case-actor`` name/URL shape — the retired ``is_case_actor_identity``
  predicate, the URL substring, the segment constant, and equality against the
  identity ``case_actor_identity()`` builds;
- ``Service``-hosting location — a store scan for ``Service`` objects combined
  with a test of the hosted case ``context``, which is the resolver ADR-0088
  deleted and the one with the reachable bootstrap-window bug (CM-02-012).

Holding a literal is fine; *testing* one to decide authority, recognition, or
routing is the violation, so the scanners flag comparisons, shape-test calls and
``match`` patterns rather than mere occurrences.  Each scanner has a self-test
that fires it on a known-bad snippet, because a scanner bug would otherwise read
as a clean repo.

Spec: ARCH-24-001, ARCH-24-002, ARCH-24-003, ARCH-24-004, CM-02-012, CM-02-013.
"""

import ast

from test.architecture import _corpus

_RESOLVER_NAME = "resolve_case_manager_id"
#: Both spellings of the resolver.  The twin actually deleted from
#: ``use_cases/_helpers.py`` was the underscore-prefixed one, so matching only
#: the bare name would let the very duplicate these ratchets name come back.
_RESOLVER_NAMES = frozenset({_RESOLVER_NAME, f"_{_RESOLVER_NAME}"})
_NEUTRAL_MODULE = "vultron/core/participants/authority.py"
_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"
_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"
_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"

_AUTHORITY_NODE_NAME = "CheckIsCaseManagerNode"
_REMOVED_NODE_NAMES = ["CheckIsOwnCaseActorNode", "CheckIsNotOwnCaseActorNode"]

#: The retired URL-shape predicate.  Deleted by ADR-0088; must not come back.
_SHAPE_PREDICATE = "is_case_actor_identity"

#: The URL substring that carries no protocol meaning (CM-02-013).
_COSMETIC_SUBSTRING = "case-actor"

#: Protocol logic, for ARCH-24-004's purposes.  ``vultron/demo/`` and
#: ``vultron/config/`` are excluded on purpose: provisioning a container at a
#: readable ``case-actor`` URL is exactly the cosmetic convenience ADR-0088 §7
#: preserves.  ``vultron/semantic_registry/`` is *included* — it maps inbound
#: semantics to use cases, which is recognition and routing, the two words
#: ARCH-24-004 uses.  ``vultron/bt/`` is the legacy simulator and models no
#: federated identity at all.
_PROTOCOL_ROOTS = [
    _corpus.REPO_ROOT / "vultron" / "core",
    _corpus.REPO_ROOT / "vultron" / "wire",
    _corpus.REPO_ROOT / "vultron" / "adapters",
    _corpus.REPO_ROOT / "vultron" / "semantic_registry",
]

#: Functions that may legitimately *build* the provisioned identity.  The
#: exemption is scoped to the function, not its file: a whole-file exemption let
#: a renamed but verbatim copy of the deleted predicate sit beside
#: ``case_actor_identity`` and pass every check here.
_PROVISIONING_FUNCTIONS = {
    "vultron/core/behaviors/case/case_actor_identity.py": {
        "case_actor_identity",
    },
}

#: String methods that turn a literal into a branch on identity shape.  Includes
#: the splitters and strippers: ``partition``/``split``/``removesuffix`` test the
#: shape just as surely as ``endswith`` does, and ``re`` match methods do it
#: through a compiled pattern.
_SHAPE_TEST_METHODS = {
    "startswith",
    "endswith",
    "find",
    "index",
    "count",
    "split",
    "rsplit",
    "partition",
    "rpartition",
    "removesuffix",
    "removeprefix",
    "strip",
    "rstrip",
    "lstrip",
    "match",
    "fullmatch",
    "search",
}

#: Callables that return the provisioned ``case-actor`` identity.  Comparing an
#: actor id against one of these is the deleted predicate rewritten — and it
#: names no literal, so a literal-only prefilter never opens the file.  The
#: glossary forbids it explicitly: "code MUST NOT compare ``actor_id`` against a
#: computed ``case_actor_id`` to decide authority" (ADR-0088).
_IDENTITY_BUILDERS = frozenset({"case_actor_identity"})


def _defines_function(tree: ast.AST, *names: str) -> bool:
    """Return True if *tree* defines a ``def`` or ``async def`` named in *names*.

    ``AsyncFunctionDef`` is a distinct AST type, so a ``FunctionDef``-only walk
    lets ``async def is_case_actor_identity(...)`` through every check here.
    """
    wanted = set(names)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in wanted
        ):
            return True
    return False


def _defines_class(tree: ast.AST, name: str) -> bool:
    """Return True if *tree* contains a ``class name(...)`` definition."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return True
    return False


def _collect_defining_modules() -> set[str]:
    """Return repo-relative paths of all modules defining either resolver spelling."""
    found: set[str] = set()
    for py_file, tree in _corpus.files_mentioning(
        _RESOLVER_NAME, under=_VULTRON_ROOT
    ):
        if _defines_function(tree, *_RESOLVER_NAMES):
            found.add(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    return found


def test_exactly_one_resolver_module():
    """Only ``vultron/core/participants/authority.py`` may define resolve_case_manager_id.

    Spec: ARCH-24-001
    """
    defining = _collect_defining_modules()
    assert defining == {_NEUTRAL_MODULE}, (
        f"Expected exactly one definition of '{_RESOLVER_NAME}' in"
        f" '{_NEUTRAL_MODULE}'.\n"
        f"Actual defining modules: {sorted(defining)}"
    )


def test_behaviors_does_not_define_resolver():
    """vultron/core/behaviors/ must not define its own resolve_case_manager_id twin.

    Spec: ARCH-24-002, BTND-04-003
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _RESOLVER_NAME, under=_BEHAVIORS_ROOT
    ):
        if _defines_function(tree, *_RESOLVER_NAMES):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"behaviors/ must not define '{_RESOLVER_NAME}'; found in:"
        f" {violations}"
    )


def test_use_cases_does_not_define_resolver():
    """vultron/core/use_cases/ must not define its own _resolve_case_manager_id twin.

    Spec: ARCH-24-001
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _RESOLVER_NAME, under=_USE_CASES_ROOT
    ):
        if _defines_function(tree, *_RESOLVER_NAMES):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"use_cases/ must not define '{_RESOLVER_NAME}'; found in:"
        f" {violations}"
    )


def test_removed_authority_nodes_are_not_defined():
    """ARCH-24-003: CheckIsOwnCaseActorNode and CheckIsNotOwnCaseActorNode must not be defined.

    These Service-scan nodes were retired by ADR-0088 in favour of the single
    role-based ``CheckIsCaseManagerNode``.  Any re-introduction is a spec
    violation.

    Spec: ARCH-24-003
    """
    violations: list[str] = []
    for node_name in _REMOVED_NODE_NAMES:
        for py_file, tree in _corpus.files_mentioning(
            node_name, under=_VULTRON_ROOT
        ):
            if _defines_class(tree, node_name):
                violations.append(
                    f"{py_file.relative_to(_corpus.REPO_ROOT).as_posix()}:"
                    f" {node_name}"
                )
    assert not violations, (
        "Retired Service-scan authority nodes must not be defined anywhere:\n"
        + "\n".join(violations)
    )


def test_exactly_one_authority_condition_node():
    """ARCH-24-003: CheckIsCaseManagerNode is defined in exactly one module.

    Spec: ARCH-24-003
    """
    defining: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _AUTHORITY_NODE_NAME, under=_VULTRON_ROOT
    ):
        if _defines_class(tree, _AUTHORITY_NODE_NAME):
            defining.append(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    assert len(defining) == 1, (
        f"Expected exactly one definition of '{_AUTHORITY_NODE_NAME}'.\n"
        f"Actual: {sorted(defining)}"
    )


# ---------------------------------------------------------------------------
# ARCH-24-004 / CM-02-013 — the name and URL shape carry no protocol meaning
# ---------------------------------------------------------------------------


def test_shape_predicate_is_not_defined_anywhere():
    """ARCH-24-004: ``is_case_actor_identity`` must not exist.

    ADR-0088 deleted it.  Authority derives from the ``CVDRole.CASE_MANAGER``
    role alone, so a predicate whose whole job is testing a URL suffix has no
    correct caller.

    Spec: ARCH-24-004, CM-02-013
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _SHAPE_PREDICATE, under=_VULTRON_ROOT
    ):
        if _defines_function(tree, _SHAPE_PREDICATE):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"'{_SHAPE_PREDICATE}' was retired by ADR-0088 and must not be"
        f" redefined; found in: {violations}"
    )


def _references_name(tree: ast.AST, name: str) -> bool:
    """Return True if *tree* imports or references *name* in executable code."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == name for alias in node.names):
                return True
    return False


def test_shape_predicate_has_no_callers():
    """ARCH-24-004: nothing under ``vultron/`` may import or call the shape predicate.

    Catches a re-introduction that lands the definition outside ``vultron/``
    (a test helper, say) and imports it into protocol logic.

    Spec: ARCH-24-004, CM-02-013
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _SHAPE_PREDICATE, under=_VULTRON_ROOT
    ):
        if _references_name(tree, _SHAPE_PREDICATE):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"'{_SHAPE_PREDICATE}' must have no callers; referenced in:"
        f" {violations}"
    )


#: Names that stand in for the literal.  A module that imports
#: ``CASE_ACTOR_SEGMENT`` (or binds its own constant) and then tests a suffix
#: built from it never contains the string `case-actor`, so matching only on the
#: literal would miss verbatim the body of the deleted ``is_case_actor_identity``.
_SEGMENT_ALIASES = frozenset({"CASE_ACTOR_SEGMENT", "CASE_ACTOR_SLUG"})


def _iter_binding_targets(node: ast.AST) -> list[str]:
    """Return the plain names a binding statement writes to.

    Handles the three shapes an assignment can take.  ``ast.Assign`` with a
    plain ``Name`` target is the obvious one; the other two each defeated an
    earlier version of this scanner:

    - ``ast.AnnAssign`` — ``_SUFFIX: str = "/actors/case-actor"``.  Adding a type
      annotation changes the node type, so an ``Assign``-only walk missed it.
    - tuple targets — ``_SUFFIX, _OTHER = "/actors/case-actor", None``, where
      ``targets[0]`` is a ``Tuple`` rather than a ``Name``.
    """
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        return []

    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(
                el.id for el in target.elts if isinstance(el, ast.Name)
            )
    return names


def _binds_the_segment(tree: ast.AST) -> set[str]:
    """Return local names bound to a ``case-actor`` literal or a known alias.

    Catches the indirection that defeats a literal-only scan::

        SUFFIX = "/actors/case-actor"      # or: from ... import CASE_ACTOR_SEGMENT
        if actor_id.endswith(SUFFIX):      # no `case-actor` literal in sight

    Also binds the *name of a function* that returns the segment, so a helper
    cannot launder it::

        def _suffix(): return "/actors/case-actor"
        if actor_id.endswith(_suffix()):   # `_suffix` is a segment name
    """
    names = set(_SEGMENT_ALIASES)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _SEGMENT_ALIASES:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None or not _mentions_segment(value, names):
                continue
            names.update(_iter_binding_targets(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A function whose *return* mentions the segment is a stand-in for
            # it.  Only returns count — a docstring naming the retired signal
            # must not make the whole function a segment name.
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Return)
                    and sub.value is not None
                    and _mentions_segment(sub.value, names)
                ):
                    names.add(node.name)
                    break
    return names


def _mentions_segment(node: ast.AST, names: frozenset[str] | set[str]) -> bool:
    """True if *node*'s subtree holds a ``case-actor`` literal or a bound alias.

    Docstrings need no exemption here: this is only ever called on a ``Compare``
    subtree, a call argument, or a ``match`` subject/pattern, and a docstring
    ``Constant`` is a statement in a body — it can never appear inside any of
    those. An earlier version threaded a ``skip`` set of docstring node ids
    through this function; it was unreachable by construction and has been
    removed rather than left to imply a guarantee it was not providing.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant):
            if (
                isinstance(sub.value, str)
                and _COSMETIC_SUBSTRING in sub.value.lower()
            ):
                return True
        elif isinstance(sub, ast.Name) and sub.id in names:
            return True
        elif isinstance(sub, ast.Attribute) and sub.attr in names:
            return True
    return False


def _builder_call_names(tree: ast.AST) -> set[str]:
    """Return names bound *directly* to an identity-builder call, plus the builders.

    Single-hop only, and deliberately so.  ``case_actor_identity()`` legitimately
    feeds provisioning writes, so propagating through arbitrary assignments would
    mark every downstream value — an earlier attempt did exactly that and flagged
    six ``if case_actor_id is None:`` configuration checks plus an unrelated
    ``link.case_id is None``, because ``link`` had been built from the id.
    """
    names = set(_IDENTITY_BUILDERS)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _IDENTITY_BUILDERS:
                    names.add(alias.asname or alias.name)
    direct: set[str] = set(names)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in names
        ):
            direct.update(_iter_binding_targets(node))
    return direct


def _identity_comparisons(tree: ast.AST) -> list[str]:
    """Return equality comparisons against the *built* provisioning identity.

    ``actor_id == case_actor_identity()`` rebuilds the deleted predicate out of
    supported API and names no literal, so nothing else here would see it.  The
    glossary forbids it in as many words: "code MUST NOT compare ``actor_id``
    against a computed ``case_actor_id`` to decide authority" (ADR-0088).

    Restricted to ``==``/``!=`` and to comparisons where no operand is ``None``.
    ``if case_actor_id is None:`` asks whether provisioning is *configured*,
    which is not a branch on anybody's identity.
    """
    names = _builder_call_names(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not all(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        if any(
            isinstance(o, ast.Constant) and o.value is None for o in operands
        ):
            continue
        mentions = False
        for operand in operands:
            for sub in ast.walk(operand):
                if isinstance(sub, ast.Name) and sub.id in names:
                    mentions = True
                elif isinstance(sub, ast.Attribute) and sub.attr in names:
                    mentions = True
        if mentions:
            found.append(
                f"line {node.lineno}: equality test against the built"
                " case-actor identity"
            )
    return found


def _exempt_line_ranges(tree: ast.AST, rel_path: str) -> list[range]:
    """Return line ranges of provisioning functions exempt in *rel_path*.

    Scoped to the function body rather than the whole file, so a renamed copy of
    the deleted predicate sitting next to ``case_actor_identity`` is still
    flagged.
    """
    exempt_names = _PROVISIONING_FUNCTIONS.get(rel_path)
    if not exempt_names:
        return []
    ranges: list[range] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in exempt_names
        ):
            end = getattr(node, "end_lineno", None) or node.lineno
            ranges.append(range(node.lineno, end + 1))
    return ranges


def _describe_shape_node(
    node: ast.AST, names: frozenset[str] | set[str]
) -> str | None:
    """Describe *node* if it tests the ``case-actor`` shape, else ``None``.

    One node, one verdict — kept separate from :func:`_shape_branches` so the
    walk stays flat and each recognised form reads on its own.
    """
    # `x == "...case-actor"`, `"case-actor" in x`, `x == SUFFIX`, etc.
    if isinstance(node, ast.Compare) and _mentions_segment(node, names):
        return "comparison on the case-actor shape"

    # `x.endswith("...case-actor")` / `x.endswith(SUFFIX)` and friends,
    # including the splitters and `re` match methods.
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SHAPE_TEST_METHODS
        and any(_mentions_segment(arg, names) for arg in node.args)
    ):
        return f".{node.func.attr}() on the case-actor shape"

    # `match actor_id.rsplit("/", 1)[-1]: case "case-actor": ...` — `MatchValue`
    # is not a `Compare`, so a match statement laundered the branch entirely.
    if isinstance(node, ast.Match) and any(
        isinstance(sub, ast.MatchValue) and _mentions_segment(sub.value, names)
        for case in node.cases
        for sub in ast.walk(case.pattern)
    ):
        return "match/case on the case-actor shape"

    return None


def _shape_branches(
    tree: ast.AST, exempt: list[range] | None = None
) -> list[str]:
    """Return descriptions of branches taken on the ``case-actor`` identity shape."""
    names = _binds_the_segment(tree)
    exempt = exempt or []

    def _is_exempt(lineno: int) -> bool:
        return any(lineno in r for r in exempt)

    found: list[str] = [
        hit
        for hit in _identity_comparisons(tree)
        if not _is_exempt(int(hit.split()[1].rstrip(":")))
    ]
    for node in ast.walk(tree):
        description = _describe_shape_node(node, names)
        if description is None:
            continue
        lineno = getattr(node, "lineno", 0)
        if not _is_exempt(lineno):
            found.append(f"line {lineno}: {description}")
    return found


def test_no_protocol_logic_branches_on_the_case_actor_url():
    """ARCH-24-004: no protocol-logic module may branch on the ``case-actor`` URL.

    The string is a provisioning convenience with no protocol meaning
    (CM-02-013).  Holding a literal is fine — example URIs and the provisioned
    identity segment both do — but *testing* one to decide authority,
    recognition, or routing is the violation, so this ratchet flags comparisons
    and shape-test calls rather than mere occurrences.

    Spec: ARCH-24-004, CM-02-013
    """
    violations: list[str] = []
    for root in _PROTOCOL_ROOTS:
        # The alias fragments matter as much as the literal: a module that
        # imports `CASE_ACTOR_SEGMENT` and builds the suffix from it holds no
        # `case-actor` string, so a literal-only prefilter would never open it.
        for py_file, tree in _corpus.files_mentioning(
            _COSMETIC_SUBSTRING,
            *_SEGMENT_ALIASES,
            *_IDENTITY_BUILDERS,
            under=root,
        ):
            rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            violations.extend(
                f"{rel}:{hit}"
                for hit in _shape_branches(
                    tree, _exempt_line_ranges(tree, rel)
                )
            )
    assert not violations, (
        "Protocol logic must not branch on the cosmetic 'case-actor' URL"
        " (ARCH-24-004); authority is the CVDRole.CASE_MANAGER role:\n"
        + "\n".join(violations)
    )


#: Store-enumeration calls that can pull every ``Service`` object out of a
#: DataLayer.  A ``Service``-hosting resolver is always this call plus a test on
#: the object's ``context``.
_STORE_SCAN_METHODS = {"list_objects", "by_type"}

#: The field ADR-0041 wrote the hosted case id into.  Testing it is what made
#: hosting location look like evidence of authority.
_HOSTING_FIELD = "context"


def _service_hosting_scans(tree: ast.AST) -> list[str]:
    """Return descriptions of ``Service``-hosting resolutions in *tree*.

    A hosting resolver has two halves and needs both to be one:

    1. ``dl.list_objects("Service")`` / ``dl.by_type("Service")`` — enumerate the
       store's ``Service`` objects.
    2. a test of ``context`` on the result — ``getattr(service, "context", None)
       == case_id`` or ``service.context == case_id``.

    Requiring both keeps legitimate ``Service`` handling (provisioning a record,
    rendering one) out of the result while catching the resolver shape.
    """
    scans = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _STORE_SCAN_METHODS
        and any(
            isinstance(a, ast.Constant) and a.value == "Service"
            for a in node.args
        )
    ]
    if not scans:
        return []

    tests_context = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == _HOSTING_FIELD:
            tests_context = True
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and any(
                isinstance(a, ast.Constant) and a.value == _HOSTING_FIELD
                for a in node.args
            )
        ):
            tests_context = True
    if not tests_context:
        return []

    return [
        f"line {scan.lineno}: Service-hosting scan combined with a"
        f" '{_HOSTING_FIELD}' test"
        for scan in scans
    ]


def test_no_protocol_logic_resolves_authority_by_service_hosting():
    """ARCH-24-004: hosting location is not evidence of authority either.

    ARCH-24-004 forbids branching on the ``case-actor`` name/URL shape **or on
    ``Service``-hosting location**.  Only the first half was ratcheted, so the
    ``Service``-``context`` resolver ADR-0088 deleted could be restored verbatim
    and every test in this file stayed green — the literal-based prefilter never
    opens a file that mentions neither ``case-actor`` nor ``CASE_ACTOR_SEGMENT``.

    That resolver is also the one with the reachable bug: under ADR-0041 the
    ``Service`` object is written before the case exists, so it carries no
    ``context`` and the real authority failed its own hosting test (CM-02-012).

    Spec: ARCH-24-004, CM-02-012, CM-02-013
    """
    violations: list[str] = []
    for root in _PROTOCOL_ROOTS:
        for py_file, tree in _corpus.files_mentioning("Service", under=root):
            rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            violations.extend(
                f"{rel}:{hit}" for hit in _service_hosting_scans(tree)
            )
    assert not violations, (
        "Protocol logic must not resolve the case authority by scanning for a"
        " hosting 'Service' object (ARCH-24-004); authority is the"
        " CVDRole.CASE_MANAGER role:\n" + "\n".join(violations)
    )


def test_service_hosting_ratchet_detects_the_deleted_resolver():
    """The Service-hosting scanner fires on the helper ADR-0088 deleted.

    The body below is ``_find_case_actor`` as it stood on ``main``, reduced to
    its resolving core.  Without this, the ratchet added above could silently
    match nothing.  Spec: ARCH-24-004
    """
    deleted_resolver = _corpus.parse_inline(
        "def find_case_actor(dl, case_id):\n"
        '    for service in dl.list_objects("Service"):\n'
        '        if getattr(service, "context", None) == case_id:\n'
        "            return service\n"
        "    return None\n"
    )
    assert _service_hosting_scans(
        deleted_resolver
    ), "scanner missed the deleted Service-hosting resolver"

    attribute_form = _corpus.parse_inline(
        "def f(dl, case_id):\n"
        '    return [s for s in dl.by_type("Service") if s.context == case_id]\n'
    )
    assert _service_hosting_scans(
        attribute_form
    ), "scanner missed the attribute-access form of the context test"

    # Handling a Service without testing where it hosts is not a violation.
    benign = _corpus.parse_inline(
        "def f(dl):\n"
        '    return [s.id_ for s in dl.list_objects("Service")]\n'
    )
    assert not _service_hosting_scans(
        benign
    ), "scanner flagged Service enumeration with no hosting test"


def test_ratchet_detects_a_shape_branch():
    """The ARCH-24-004 scanner must actually fire on a violating pattern.

    Without this, a scanner bug would read as a clean repo.  Spec: ARCH-24-004
    """
    offending = _corpus.parse_inline(
        "def f(actor_id):\n"
        '    """Docstring naming /actors/case-actor must not count."""\n'
        '    return actor_id.endswith("/actors/case-actor")\n'
    )
    assert _shape_branches(offending), "scanner missed an endswith() branch"

    compare = _corpus.parse_inline(
        'x = a == "https://e.org/actors/case-actor"\n'
    )
    assert _shape_branches(compare), "scanner missed a comparison branch"

    benign = _corpus.parse_inline(
        'CASE_ACTOR_URI = "https://example.org/actors/case-actor"\n'
    )
    assert not _shape_branches(benign), "scanner flagged a plain literal"

    # Modules that *explain* the retired signal must stay clean.  This holds by
    # construction — only Compare subtrees, call arguments and match patterns are
    # inspected, and a docstring is a statement in a body, so it can never appear
    # inside any of them.  Pinned anyway: if the scanner is ever widened to raw
    # Constants, this is the assertion that catches the resulting false positive.
    docstring_only = _corpus.parse_inline(
        '"""Explains why .../actors/case-actor is cosmetic."""\n'
    )
    assert not _shape_branches(
        docstring_only
    ), "scanner flagged a docstring mention"


def test_ratchet_is_not_evaded_by_binding_the_literal_to_a_name():
    """Indirection must not launder the branch. Spec: ARCH-24-004

    A literal-only matcher is defeated two ways, and both reconstruct the body
    of the deleted ``is_case_actor_identity`` without ever writing
    ``case-actor``: import the segment constant, or bind a local one.
    """
    via_import = _corpus.parse_inline(
        "from vultron.core.behaviors.case.case_actor_identity import (\n"
        "    CASE_ACTOR_SEGMENT,\n"
        ")\n"
        "def f(actor_id):\n"
        '    return actor_id.rstrip("/").endswith(\n'
        '        f"/actors/{CASE_ACTOR_SEGMENT}"\n'
        "    )\n"
    )
    assert _shape_branches(
        via_import
    ), "scanner missed a branch built from the imported segment constant"

    via_local_constant = _corpus.parse_inline(
        'SUFFIX = "/actors/case-actor"\n'
        "def f(actor_id):\n"
        "    return actor_id.endswith(SUFFIX)\n"
    )
    assert _shape_branches(
        via_local_constant
    ), "scanner missed a branch built from a locally bound constant"

    aliased_import = _corpus.parse_inline(
        "from x import CASE_ACTOR_SEGMENT as SEG\n"
        "def f(a):\n"
        "    return a == SEG\n"
    )
    assert _shape_branches(
        aliased_import
    ), "scanner missed a branch on an as-renamed segment import"


def test_ratchet_is_not_evaded_by_the_annotated_or_tuple_binding():
    """A type annotation must not launder the branch. Spec: ARCH-24-004

    ``_binds_the_segment`` originally walked ``ast.Assign`` only, so adding
    ``: str`` to the constant defeated the test above — the one written
    specifically to close binding indirection. Tuple targets did the same, by
    making ``targets[0]`` a ``Tuple`` rather than a ``Name``.
    """
    annotated = _corpus.parse_inline(
        '_SUFFIX: str = "/actors/case-actor"\n'
        "def f(actor_id):\n"
        '    return actor_id.rstrip("/").endswith(_SUFFIX)\n'
    )
    assert _shape_branches(
        annotated
    ), "scanner missed a branch built from an annotated constant"

    tuple_target = _corpus.parse_inline(
        '_SUFFIX, _OTHER = "/actors/case-actor", None\n'
        "def f(actor_id):\n"
        "    return actor_id.endswith(_SUFFIX)\n"
    )
    assert _shape_branches(
        tuple_target
    ), "scanner missed a branch built from a tuple-bound constant"


def test_ratchet_is_not_evaded_by_comparing_against_the_built_identity():
    """The likeliest re-introduction names no literal at all. Spec: ARCH-24-004

    ``case_actor_identity()`` survives ADR-0088 as a provisioning helper, so
    comparing an actor id against its return value rebuilds the deleted
    predicate using only supported API — and contains neither ``case-actor`` nor
    ``CASE_ACTOR_SEGMENT``, so a literal-only prefilter never even opens the
    file. The glossary forbids exactly this: "code MUST NOT compare ``actor_id``
    against a computed ``case_actor_id`` to decide authority".
    """
    via_builder = _corpus.parse_inline(
        "from vultron.core.behaviors.case.case_actor_identity import (\n"
        "    case_actor_identity,\n"
        ")\n"
        "def is_the_authority(actor_id):\n"
        "    return actor_id == case_actor_identity()\n"
    )
    assert _shape_branches(
        via_builder
    ), "scanner missed a comparison against the built provisioning identity"


def test_ratchet_is_not_evaded_by_a_helper_or_a_match_statement():
    """Splitters, helper returns and ``match`` are all shape tests. Spec: ARCH-24-004"""
    via_helper = _corpus.parse_inline(
        'def _suffix():\n    return "/actors/case-actor"\n'
        "def f(actor_id):\n"
        "    return actor_id.endswith(_suffix())\n"
    )
    assert _shape_branches(
        via_helper
    ), "scanner missed a branch built from a helper that returns the suffix"

    via_partition = _corpus.parse_inline(
        "def f(actor_id):\n"
        '    _, sep, _ = actor_id.partition("/actors/case-actor")\n'
        "    return bool(sep)\n"
    )
    assert _shape_branches(
        via_partition
    ), "scanner missed a partition()-as-shape-test"

    via_match = _corpus.parse_inline(
        "def f(actor_id):\n"
        '    match actor_id.rsplit("/", 1)[-1]:\n'
        '        case "case-actor":\n'
        "            return True\n"
        "        case _:\n"
        "            return False\n"
    )
    assert _shape_branches(
        via_match
    ), "scanner missed a match/case on the case-actor shape"


def test_provisioning_exemption_is_scoped_to_the_function_not_the_file():
    """A renamed copy of the predicate must not ride the exemption. Spec: ARCH-24-004

    The exemption exists so ``case_actor_identity`` can *build* the provisioned
    URL. It was previously whole-file, which let a verbatim copy of the deleted
    predicate under any other name sit in the same module and pass.
    """
    rel = "vultron/core/behaviors/case/case_actor_identity.py"
    tree = _corpus.parse_inline(
        'CASE_ACTOR_SEGMENT = "case-actor"\n'
        "def case_actor_identity(base):\n"
        '    suffix = f"/actors/{CASE_ACTOR_SEGMENT}"\n'
        "    if base.endswith(suffix):\n"
        "        return base\n"
        "    return base + suffix\n"
        "def actor_is_the_authority(actor_id):\n"
        '    return actor_id.rstrip("/").endswith(\n'
        '        f"/actors/{CASE_ACTOR_SEGMENT}"\n'
        "    )\n"
    )
    hits = _shape_branches(tree, _exempt_line_ranges(tree, rel))
    assert hits, (
        "the renamed predicate outside case_actor_identity() must be flagged"
        " even though its module holds the provisioning exemption"
    )
    assert all(
        "line 4" not in hit for hit in hits
    ), f"the exempt builder's own suffix test must not be flagged: {hits}"
