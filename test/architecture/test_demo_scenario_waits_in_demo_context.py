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

"""Architecture invariant (DEMOCI-01-011): scenario-level demo code must not
call a raising ``wait_for_*`` helper outside a demo accumulation context.

Every ``wait_for_*`` / ``find_*`` polling helper in
``vultron/demo/helpers/polling.py`` raises ``AssertionError`` on timeout — the
correct contract for the unit tests that assert the timeout, but fatal inside a
scenario: ``scenario_harness`` re-raises, so a bare call crashes the whole run
at the first failure and buries every co-occurring failure (violating the
accumulation model, DEMOCI-01-003/004).

Scenario-level code has two shapes while the scenarios migrate to composed
stories (#5533, #5534, #5537):

* a ``_phase_*`` function in a hand-written scenario module;
* a **story fragment** — a module-level function taking a
  :class:`~vultron.demo.helpers.story.StoryState`, which is one step of a
  story (``vultron/demo/helpers/story.py``).  A fragment is scenario-level
  wherever it is written: a composed scenario keeps the fragments only it
  tells in its own module, and the shared ones live in
  ``helpers/coordinated_story.py`` and
  ``helpers/coordinated_embargo_story.py``.

Both shapes run under ``scenario_harness`` and both own their wrap, so the
check follows the subject rather than the directory: it scans every module
under ``vultron/demo/`` and takes its subjects from the two shapes.
:func:`test_the_check_has_subjects_of_both_shapes` fails if either shape stops
being found, so retiring the ``_phase_*`` arm when the migration finishes is a
deliberate edit rather than a gate quietly left with nothing to check
(``notes/documentation-strategy.md`` § "A gate that resolves zero targets must
fail").

A raising wait invoked from scenario-level code MUST therefore sit inside a
``demo_step`` / ``demo_check`` / ``demo_gate`` block, OR be invoked through a
shared helper that performs that wrap internally so every caller inherits it
(``wait_for_participants_on_replicas`` in ``polling.py`` and
``wait_for_replica_ledger_coverage`` in ``helpers/sync.py`` are such helpers;
the latter is also governed by DEMOMA-23-005/006 and its own ratchet).

The raising / wrapping classification is derived from ``polling.py`` and
``sync.py`` themselves, so a new raising helper in either module is covered
automatically and a new self-wrapping helper is recognised as safe without
editing this test.  A demo context is a literal ``demo_step`` / ``demo_check`` /
``demo_gate`` call, or a call to a local name bound only to those (for example
``context = demo_gate if causal else demo_check``).

Source: CONCERN-3384 (#3406), generalising the #1772/#1802 ledger-coverage fix;
widened to story fragments by #5534.
Spec: ``specs/demo-ci.yaml`` DEMOCI-01-011.
"""

import ast
from collections import Counter
from pathlib import Path

import pytest

from test.architecture import _corpus

_DEMO_DIR = _corpus.REPO_ROOT / "vultron" / "demo"
_HELPERS_DIR = _DEMO_DIR / "helpers"
_POLLING = _HELPERS_DIR / "polling.py"
_SYNC = _HELPERS_DIR / "sync.py"

#: The helper modules whose ``wait_for_*`` / ``find_*`` functions are classified.
_HELPER_MODULES = (_POLLING, _SYNC)

#: The demo failure-accumulation context managers (DEMOCI-01-004).
_DEMO_CONTEXTS = frozenset({"demo_step", "demo_check", "demo_gate"})

#: Prefixes of the polling-helper family in the helper modules that block on a
#: side effect and raise on timeout.
_WAIT_PREFIXES = ("wait_for_", "find_")


def _callee_name(call: ast.Call) -> str:
    """Return the called name for ``foo(...)`` or ``obj.foo(...)``."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


#: Names whose call raises on timeout: the low-level poll primitives plus the
#: whole ``wait_for_*`` / ``find_*`` polling family (they bottom out in one of
#: the primitives).  A helper that routes a call to any of these *outside* a
#: demo context can still crash a bare caller, so it is not "wrapping".
_POLL_PRIMITIVES = frozenset({"_poll_until", "_poll_datalayer_for"})


def _is_raising_callee(name: str) -> bool:
    return name in _POLL_PRIMITIVES or name.startswith(("wait_for_", "find_"))


def _parent_map(node: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(node):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _is_demo_context_value(expr: ast.expr) -> bool:
    """True if *expr* evaluates to a demo context manager factory.

    Either a bare ``demo_step`` / ``demo_check`` / ``demo_gate`` name, or a
    conditional expression whose branches are all such values.
    """
    if isinstance(expr, ast.Name):
        return expr.id in _DEMO_CONTEXTS
    if isinstance(expr, ast.IfExp):
        return _is_demo_context_value(expr.body) and _is_demo_context_value(
            expr.orelse
        )
    return False


def _plain_assignments(scope: ast.AST) -> list[tuple[str, ast.expr | None]]:
    """Return ``(name, value)`` for each plain ``name = value`` in *scope*."""
    found: list[tuple[str, ast.expr | None]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            found.extend(
                (t.id, node.value)
                for t in node.targets
                if isinstance(t, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            found.append((node.target.id, node.value))
    return found


def _other_bindings(node: ast.AST) -> list[str]:
    """Return the names *node* binds other than by ``Name`` store context.

    Covers parameters, imports, ``def`` / ``class`` names, ``except ... as``,
    ``match`` captures, and ``global`` / ``nonlocal`` declarations (which let
    another scope rebind the name).
    """
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(node, ast.alias):
        return [node.asname or node.name.split(".")[0]]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.ExceptHandler) and node.name:
        return [node.name]
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
        return [node.name]
    if isinstance(node, ast.MatchMapping) and node.rest:
        return [node.rest]
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return list(node.names)
    return []


def _demo_context_names(scope: ast.AST) -> frozenset[str]:
    """Return local names in *scope* bound only to demo context factories.

    A name qualifies when every binding of it is a plain assignment of a demo
    context (``_is_demo_context_value``).  Any other binding — a parameter, a
    loop or ``with`` target, an augmented or walrus assignment, a tuple unpack,
    an import, a ``def`` / ``class``, an ``except ... as`` or ``match`` capture,
    a ``global`` / ``nonlocal`` declaration — disqualifies it, since the name
    may then hold something that is not a demo context.  The analysis is
    flow-insensitive and per function: it does
    not order bindings against uses, and a name bound in an outer function or
    at module level is not resolved (both fail toward flagging the call).
    """
    assignments = _plain_assignments(scope)
    plain_count = Counter(name for name, _ in assignments)
    bindings = Counter(
        node.id
        for node in ast.walk(scope)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )
    bindings.update(
        name for node in ast.walk(scope) for name in _other_bindings(node)
    )
    bad = {
        name
        for name, value in assignments
        if value is None or not _is_demo_context_value(value)
    }
    return frozenset(
        name
        for name, count in plain_count.items()
        if bindings[name] == count and name not in bad
    )


def _enclosing_scope(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> ast.AST:
    """Return the nearest enclosing function of *node*, else the tree root."""
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return cur


def _is_demo_with(node: ast.With, parents: dict[ast.AST, ast.AST]) -> bool:
    """True if *node* is a ``with`` entering a demo context.

    The context expression is a call to ``demo_step`` / ``demo_check`` /
    ``demo_gate``, or to a local name bound only to those (see
    ``_demo_context_names``).
    """
    local: frozenset[str] | None = None
    for item in node.items:
        ce = item.context_expr
        if not isinstance(ce, ast.Call):
            continue
        if _callee_name(ce) in _DEMO_CONTEXTS:
            return True
        if isinstance(ce.func, ast.Name):
            if local is None:
                local = _demo_context_names(_enclosing_scope(node, parents))
            if ce.func.id in local:
                return True
    return False


def _call_in_demo_context(
    call: ast.AST, parents: dict[ast.AST, ast.AST]
) -> bool:
    """True if *call* has an ancestor ``with`` entering a demo context.

    The search stops at a function or lambda boundary: a call deferred inside a
    closure may run outside the ``with`` that lexically encloses the closure.
    """
    cur = parents.get(call)
    while cur is not None and not isinstance(cur, _SCOPE_NODES):
        if isinstance(cur, ast.With) and _is_demo_with(cur, parents):
            return True
        cur = parents.get(cur)
    return False


def _has_unwrapped_raising_call(fn: ast.AST) -> bool:
    """True if *fn* calls a raising poll helper outside any demo context.

    A helper is only safe to call bare from a scenario when *every* raising call
    it makes is inside a demo context.  A partial wrap — one raising call in a
    ``demo_check`` and another left bare — must still be treated as raising, or
    the DEMOCI-01-011 invariant silently stops being enforced for its callers.
    """
    parents = _parent_map(fn)
    for call in ast.walk(fn):
        if (
            isinstance(call, ast.Call)
            and _is_raising_callee(_callee_name(call))
            and not _call_in_demo_context(call, parents)
        ):
            return True
    return False


def _wraps_in_demo_context(node: ast.AST) -> bool:
    """True if *node* contains a ``with`` entering a demo context."""
    parents = _parent_map(node)
    return any(
        isinstance(inner, ast.With) and _is_demo_with(inner, parents)
        for inner in ast.walk(node)
    )


def _helper_trees() -> list[ast.Module]:
    """Return the parsed ASTs of every helper module from the shared corpus."""
    found: dict[Path, ast.Module] = {}
    for path, tree in _corpus.files_mentioning(
        "def wait_for_", "def find_", under=_HELPERS_DIR
    ):
        if path in _HELPER_MODULES:
            assert isinstance(tree, ast.Module)
            found[path] = tree
    missing = [p for p in _HELPER_MODULES if p not in found]
    assert not missing, f"{missing} not found in the source corpus"
    return [found[p] for p in _HELPER_MODULES]


def _classify_polling_helpers(
    trees: list[ast.Module] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(raising, wrapping)`` helper-name sets from the helper modules.

    Classifies ``polling.py`` and ``sync.py`` (or the given *trees*).

    A ``wait_for_*`` / ``find_*`` function is a *wrapping* helper when it
    contains a demo context AND makes no raising poll call outside one —
    it neutralises the raise for every caller.  Otherwise it is a *raising*
    helper.  Bare raising helpers are the ones a scenario must not call outside
    a demo context; bare calls to wrapping helpers are safe.  Both ``def`` and
    ``async def`` at any nesting level are considered, so an async or
    conditionally-defined helper cannot slip through unclassified.
    """
    raising: set[str] = set()
    wrapping: set[str] = set()
    for tree in _helper_trees() if trees is None else trees:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith(_WAIT_PREFIXES):
                continue
            if _wraps_in_demo_context(
                node
            ) and not _has_unwrapped_raising_call(node):
                wrapping.add(node.name)
            else:
                raising.add(node.name)
    return frozenset(raising), frozenset(wrapping)


_RAISING_WAITS, _WRAPPING_WAITS = _classify_polling_helpers()

#: The annotation that marks a story fragment's state parameter: one step of a
#: story is ``Callable[[StoryState], None]`` (``helpers/story.py``).
_STORY_STATE = "StoryState"

#: The name prefix of a hand-written scenario phase function.
_PHASE_PREFIX = "_phase_"

#: The two shapes of scenario-level code, as the report and the scope
#: assertion name them.
_PHASE, _FRAGMENT = "phase function", "story fragment"

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _annotates_story_state(annotation: ast.expr | None) -> bool:
    """True if *annotation* names ``StoryState``.

    Matched on the trailing name so the import form a module happens to use —
    bare ``StoryState``, dotted ``story.StoryState``, or a quoted forward
    reference — does not decide whether its fragments are checked.
    """
    if isinstance(annotation, ast.Name):
        return annotation.id == _STORY_STATE
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == _STORY_STATE
    if isinstance(annotation, ast.Constant) and isinstance(
        annotation.value, str
    ):
        return annotation.value.rsplit(".", 1)[-1] == _STORY_STATE
    return False


def _takes_story_state(fn: _FunctionNode) -> bool:
    """True if any parameter of *fn* is annotated ``StoryState``.

    Every parameter position is considered, not just the first: a shared
    fragment helper takes the state plus the cast name it acts for
    (``report_fix_ready(state, name, label)``), and a keyword-only or
    starred state parameter would be the same subject written differently.
    """
    args = fn.args
    return any(
        arg is not None and _annotates_story_state(arg.annotation)
        for arg in (
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
            args.vararg,
            args.kwarg,
        )
    )


def _scenario_level_functions(
    tree: ast.AST,
) -> list[tuple[str, _FunctionNode]]:
    """Return ``(shape, fn)`` for each scenario-level function in *tree*.

    A ``_phase_*`` function counts wherever it is defined, as it always has.
    A story fragment counts only at module level: that is where a story's
    items are declared and where :func:`~vultron.demo.helpers.story.run_story`
    calls them, whereas a nested function taking the state is a closure the
    enclosing subject already covers.  A module-level ``_phase_*`` that also
    takes the state is reported once, under ``_phase_*``.
    """
    found: list[tuple[str, _FunctionNode]] = [
        (_PHASE, node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith(_PHASE_PREFIX)
    ]
    if isinstance(tree, ast.Module):
        found.extend(
            (_FRAGMENT, node)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith(_PHASE_PREFIX)
            and _takes_story_state(node)
        )
    return found


def _scanned_trees() -> tuple[dict[Path, ast.AST], Counter[str]]:
    """Return the trees holding scenario-level code and the shapes found.

    Narrowing the parametrisation to the files that actually hold a subject
    keeps the per-file test and its id meaningful, and makes the emptiness
    assertion a real one: ``polling.py`` mentions ``wait_for_`` on every line
    and holds no scenario-level code at all.
    """
    trees: dict[Path, ast.AST] = {}
    shapes: Counter[str] = Counter()
    for path, tree in _corpus.files_mentioning(
        *_WAIT_PREFIXES, under=_DEMO_DIR
    ):
        if path.name == "__init__.py":
            continue
        found = Counter(shape for shape, _ in _scenario_level_functions(tree))
        if found:
            trees[path] = tree
            shapes.update(found)
    return trees, shapes


_SCANNED_TREES, _SHAPES_FOUND = _scanned_trees()


def _bare_wait_violations(
    tree: ast.AST, raising: frozenset[str]
) -> list[tuple[int, str, str]]:
    """Return ``(line, function, callee)`` for bare raising waits.

    A call is a violation when its callee is a known raising helper, it is
    lexically inside a scenario-level function (:func:`_scenario_level_functions`),
    and no ancestor of the call is a ``with demo_*`` block.
    """
    parents = _parent_map(tree)
    violations: list[tuple[int, str, str]] = []
    for _, node in _scenario_level_functions(tree):
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and _callee_name(call) in raising
                and not _call_in_demo_context(call, parents)
            ):
                violations.append((call.lineno, node.name, _callee_name(call)))
    return violations


def test_polling_module_has_raising_and_wrapping_helpers():
    """Sanity: the classifier finds real helpers of each kind.

    Guards against a silently-empty ``_RAISING_WAITS`` (which would make the
    per-scenario check vacuous) and confirms the known self-wrapping helper is
    recognised, so ``_WRAPPING_WAITS`` is a real classification and not an
    empty set that happens to satisfy every subset check.
    """
    assert "wait_for_case_participants" in _RAISING_WAITS
    assert "wait_for_participants_on_replicas" in _WRAPPING_WAITS, (
        "wait_for_participants_on_replicas must wrap its raising poll "
        f"internally (DEMOCI-01-011); got {_WRAPPING_WAITS}"
    )
    assert "wait_for_replica_ledger_coverage" in _WRAPPING_WAITS, (
        "wait_for_replica_ledger_coverage must wrap its raising poll "
        "internally through its variable-bound demo context "
        f"(DEMOCI-01-011); got {_WRAPPING_WAITS}"
    )
    assert _WRAPPING_WAITS, "at least one real wrapping helper must exist"


def test_the_check_has_subjects_of_both_shapes():
    """The scan must resolve files, and a subject of each shape.

    A gate that resolves no target passes while checking nothing, and its
    false clean signal suppresses the review it replaced
    (``notes/documentation-strategy.md`` § "A gate that resolves zero targets
    must fail").  Both arms are asserted separately because the scenarios are
    mid-migration from ``_phase_*`` functions to composed stories: a rewrite
    that leaves a scenario with no phases must not quietly take its checking
    with it, and the last phase function going away is the signal to retire
    that arm here on purpose.
    """
    assert _SCANNED_TREES, (
        "no module under vultron/demo/ holds scenario-level code, so"
        " DEMOCI-01-011 is unchecked; the scan looks for _phase_* functions"
        f" and for module-level functions taking a {_STORY_STATE}"
    )
    assert _SHAPES_FOUND[_FRAGMENT], (
        f"no {_FRAGMENT} was found under vultron/demo/, so the composed"
        " scenarios (#5533, #5534, #5537) are unchecked; a fragment is a"
        f" module-level function taking a {_STORY_STATE}"
    )
    assert _SHAPES_FOUND[_PHASE], (
        f"no {_PHASE} was found under vultron/demo/: if the story migration"
        " (#5533, #5534, #5537) has converted the last scenario, delete the"
        f" {_PHASE_PREFIX}* arm of this check and this assertion with it,"
        " rather than leaving an arm that can no longer fail"
    )


@pytest.mark.parametrize(
    "scenario", sorted(_SCANNED_TREES), ids=lambda p: p.name
)
def test_scenario_level_code_wraps_raising_waits(scenario: Path):
    """No scenario-level call of a raising ``wait_for_*`` outside a demo context.

    Wrap the call in ``demo_step`` / ``demo_check`` / ``demo_gate``, or route it
    through a shared helper that wraps internally (e.g.
    ``wait_for_participants_on_replicas``).  A bare raising wait crashes the
    whole run at the first timeout (DEMOCI-01-011).
    """
    violations = _bare_wait_violations(
        _SCANNED_TREES[scenario], _RAISING_WAITS
    )
    assert not violations, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} calls raising wait helpers"
        " outside a demo context in scenario-level code (a _phase_* function"
        f" or a story fragment): {violations}. Wrap each in"
        " demo_step/demo_check/demo_gate, or route it through a shared helper"
        " that wraps internally (DEMOCI-01-011)."
    )


def test_the_check_can_actually_fail():
    """Guard: the detector must flag a genuine bare raising wait."""
    sample = _corpus.parse_inline(
        "def _phase_demo(client, case):\n"
        "    wait_for_case_participants(\n"
        "        vendor_client=client,\n"
        "        case_id=case.id_,\n"
        "        expected_actor_ids={a.id_, b.id_},\n"
        "    )\n"
    )
    violations = _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )
    assert len(violations) == 1
    assert violations[0][1] == "_phase_demo"
    assert violations[0][2] == "wait_for_case_participants"


def test_the_check_passes_when_wrapped():
    """Guard: a wait inside a demo_check block is not a violation."""
    sample = _corpus.parse_inline(
        "def _phase_demo(client, case):\n"
        "    with demo_check('participants present'):\n"
        "        wait_for_case_participants(\n"
        "            vendor_client=client,\n"
        "            case_id=case.id_,\n"
        "            expected_actor_ids={a.id_, b.id_},\n"
        "        )\n"
    )
    assert not _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )


#: A fragment body whose one raising wait is bare, as a format string over the
#: ``StoryState`` annotation form.
_BARE_FRAGMENT = (
    "def vendor_accepts_and_joins(state: {annotation}) -> None:\n"
    "    wait_for_case_participants(state.client('v'), state.case.id_, set())\n"
)


@pytest.mark.parametrize(
    "annotation", ["StoryState", "story.StoryState", "'StoryState'"]
)
def test_the_check_can_fail_on_a_story_fragment(annotation: str):
    """Guard: a fragment's bare raising wait is flagged like a phase's.

    Parametrised over the annotation forms a module may write, so a scenario
    that imports the state module rather than the name, or quotes the
    annotation, is not silently exempt.
    """
    sample = _corpus.parse_inline(_BARE_FRAGMENT.format(annotation=annotation))
    violations = _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )
    assert [v[1:] for v in violations] == [
        ("vendor_accepts_and_joins", "wait_for_case_participants")
    ]


def test_a_story_fragment_wait_in_a_demo_gate_is_not_a_violation():
    """Guard: the same fragment wait inside a ``demo_gate`` is wrapped."""
    sample = _corpus.parse_inline(
        "def vendor_accepts_and_joins(state: StoryState) -> None:\n"
        "    with demo_gate('Vendor joined the case'):\n"
        "        wait_for_case_participants(state.client('v'), '1', set())\n"
    )
    assert not _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )


def test_function_that_is_neither_phase_nor_fragment_is_not_scanned():
    """A plain demo helper is not scenario-level code, so it is not scanned.

    The check covers the code a story or a scenario runs as a step, which owns
    the wrap.  A helper several steps call is classified from its own body by
    :func:`_classify_polling_helpers` instead, and its bare raising call is
    reported against the scenario-level caller.
    """
    sample = _corpus.parse_inline(
        "def seed_the_containers(client, case) -> None:\n"
        "    wait_for_case_participants(client, case.id_, set())\n"
    )
    assert not _bare_wait_violations(
        sample, frozenset({"wait_for_case_participants"})
    )


def test_partial_wrap_is_classified_raising_not_wrapping():
    """A helper that leaves one raising call bare is not a safe wrapping helper.

    Guards ``_has_unwrapped_raising_call``: a body that wraps one poll in a
    demo_check but calls another bare must be treated as raising, so bare
    scenario callers are still flagged (DEMOCI-01-011).
    """
    partial = _corpus.parse_inline(
        "def wait_for_two_things(client, case):\n"
        "    with demo_check('first'):\n"
        "        wait_for_case_on_container(client, case.id_)\n"
        "    wait_for_case_participants(client, case.id_, set())\n"
    )
    assert isinstance(partial, ast.Module)
    fn = partial.body[0]
    assert _wraps_in_demo_context(fn)
    assert _has_unwrapped_raising_call(fn)

    fully = _corpus.parse_inline(
        "def wait_for_two_things(client, case):\n"
        "    with demo_check('first'):\n"
        "        wait_for_case_on_container(client, case.id_)\n"
        "    with demo_check('second'):\n"
        "        wait_for_case_participants(client, case.id_, set())\n"
    )
    assert isinstance(fully, ast.Module)
    assert not _has_unwrapped_raising_call(fully.body[0])


_WAIT = frozenset({"wait_for_case_participants"})


def _phase_violation_count(body: str, params: str = "client, case") -> int:
    """Count bare ``wait_for_case_participants`` calls in a sample ``_phase_demo``."""
    sample = _corpus.parse_inline(
        f"def _phase_demo({params}):\n{body}"
        "    with context('participants present'):\n"
        "        wait_for_case_participants(client, case.id_, set())\n"
    )
    return len(_bare_wait_violations(sample, _WAIT))


def test_variable_bound_demo_context_counts_as_demo_context():
    """A ``with`` on a local name bound only to demo contexts is wrapped."""
    assert (
        _phase_violation_count(
            "    context = demo_gate if causal else demo_check\n",
            "client, case, causal",
        )
        == 0
    )


@pytest.mark.parametrize(
    "binding",
    [
        "context = open_lock",
        "context = demo_gate if causal else open_lock",
        "context = demo_gate\n    context = open_lock",
        "context = demo_gate\n    context += 1",
        "context, other = demo_gate, 1",
        "for context in contexts: pass",
        "if (context := open_lock): pass",
        "context = demo_gate\n    import context",
        "context = demo_gate\n    from somewhere import context",
        "context = demo_gate\n    def context(name): pass",
        "context = demo_gate\n    class context: pass",
        "context = demo_gate\n    try: pass\n    except Exception as context: pass",
        "context = demo_gate\n    match contexts:\n        case [context]: pass",
        "context = demo_gate\n    global context",
        "context = demo_gate\n    nonlocal context",
    ],
)
def test_name_bound_to_non_demo_context_is_not_a_demo_context(binding: str):
    """A name bound (even once) to anything else does not count."""
    assert (
        _phase_violation_count(
            f"    {binding}\n",
            "client, case, causal, contexts, open_lock",
        )
        == 1
    )


def test_parameter_named_like_a_context_is_not_a_demo_context():
    """A parameter is not known to hold a demo context."""
    assert _phase_violation_count("", "client, case, context") == 1


def test_outer_scope_demo_context_is_not_resolved():
    """A nested function does not inherit an outer function's context name."""
    sample = _corpus.parse_inline(
        "def _phase_demo(client, case):\n"
        "    context = demo_gate\n"
        "    def inner():\n"
        "        with context('participants present'):\n"
        "            wait_for_case_participants(client, case.id_, set())\n"
        "    inner()\n"
    )
    assert len(_bare_wait_violations(sample, _WAIT)) == 1


def test_raising_helper_in_sync_module_is_flagged_when_called_bare():
    """A raising helper defined in ``sync.py`` is classified and flagged."""
    sync_like = _corpus.parse_inline(
        "def wait_for_thing_on_replicas(client, case):\n"
        "    wait_for_case_participants(client, case.id_, set())\n"
    )
    assert isinstance(sync_like, ast.Module)
    raising, wrapping = _classify_polling_helpers([sync_like])
    assert raising == {"wait_for_thing_on_replicas"}
    assert not wrapping

    scenario = _corpus.parse_inline(
        "def _phase_demo(client, case):\n"
        "    wait_for_thing_on_replicas(client, case)\n"
    )
    violations = _bare_wait_violations(scenario, raising)
    assert [v[1:] for v in violations] == [
        ("_phase_demo", "wait_for_thing_on_replicas")
    ]


@pytest.mark.parametrize(
    "deferred",
    [
        "    def inner():\n            wait_for_case_participants(c, 1, set())\n",
        "    f = lambda: wait_for_case_participants(c, 1, set())\n",
    ],
)
def test_call_deferred_in_closure_inside_demo_context_is_not_wrapped(
    deferred: str,
):
    """A closure defined inside a demo ``with`` may run outside it."""
    sample = _corpus.parse_inline(
        f"def _phase_demo(c):\n    with demo_check('x'):\n    {deferred}"
    )
    assert len(_bare_wait_violations(sample, _WAIT)) == 1
