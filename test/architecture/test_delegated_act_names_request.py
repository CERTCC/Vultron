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
"""Architecture test: no delegated outbound activity omits the request it answers.

ADR-0199 and CM-24-020: when the CASE_MANAGER carries out an act another
actor asked for, the activity names the asker in ``attributedTo`` and the
request it received in ``inReplyTo``, both exactly when the asker is not the
``actor``.  An ``attributedTo`` naming another actor with no ``inReplyTo`` is
a delegated act that does not say what it answers.

Every outbound activity core builds goes through a trigger-activity port
method (ARCH-01-004), so the check reads, under ``vultron/core/``, every call
of a port method that takes ``attributed_to``.  A call that passes an
``attributed_to`` crediting someone else — anything but literal ``None`` or
``self.actor_id``, the actor's own authorship — must also pass an
``in_reply_to`` that is not literal ``None``.  A ``**`` splat could carry
either keyword unseen, so it counts as crediting someone else.  That the two
values agree is the helper's guarantee (``delegated_authorship`` returns both
or neither, and raises on a distinct asker with no request), tested in
``test/core/behaviors/test_delegated_authorship.py``; this test checks that no
call site drops the second.

This is the one ``inReplyTo`` architecture test (#6464 AC-3); #6726 extends
it to every act a ledger commit causes.  It lists no exemption: every
delegated emit on ``main`` has a received request to name.  A new exemption
names the issue that removes it, as a ``path::function`` key in
:data:`_EXEMPT`, and the test asserts the sites found equal the exemptions,
so an entry whose site no longer offends fails too (ARCH-18-001,
ARCH-18-006).

Known gaps: a positional ``attributed_to`` or ``in_reply_to`` is not read;
every port method takes them by keyword in core.  The check reads that an
``in_reply_to`` expression is present, not its value: a conditional that can
yield ``None`` or a wrong variable passes here.  The per-emit tests marked
``CM-24-020`` assert the request each emit names.

The same rule is checked on the wire, over every example activity an
implementer copies (``_vocab_example_corpus``): one whose ``attributedTo``
names an actor other than its ``actor`` carries an ``inReplyTo``.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from test.architecture import _corpus
from test.architecture._vocab_example_corpus import activity_examples
from vultron.primitives import same_actor_id

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_PORTS = _CORE / "ports" / "trigger_activity"

#: Ratchet: ``<path>::<function>`` of a delegated emit allowed to omit
#: ``in_reply_to``, mapped to the issue that removes it.  Empty: every
#: delegated emit names its request.  A new entry carries ``# owner: #N``
#: (ARCH-18-003).
_EXEMPT: dict[str, int] = {}


def _attribute_chain(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _port_methods_taking_attribution() -> frozenset[str]:
    """Names of the trigger-activity port methods with an ``attributed_to``."""
    names: set[str] = set()
    for path in sorted(_PORTS.glob("*.py")):
        for node in ast.walk(_corpus.tree_of(path)):
            if isinstance(node, ast.FunctionDef) and any(
                p.arg == "attributed_to" for p in _corpus.parameters_of(node)
            ):
                names.add(node.name)
    return frozenset(names)


def _is_literal_none(value: ast.AST) -> bool:
    return isinstance(value, ast.Constant) and value.value is None


def _credits_another(kw: ast.keyword) -> bool:
    """A ``**`` splat, or an ``attributed_to`` that is not the actor's own."""
    if kw.arg is None:
        return True
    if kw.arg != "attributed_to":
        return False
    value = kw.value
    return not (
        _is_literal_none(value) or _attribute_chain(value) == "self.actor_id"
    )


def _names_request(call: ast.Call) -> bool:
    return any(
        kw.arg == "in_reply_to" and not _is_literal_none(kw.value)
        for kw in call.keywords
    )


def _enclosing_functions(
    tree: ast.AST,
) -> Iterator[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.Call]]:
    """Each call in *tree* with the innermost function that holds it."""
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        inner = {
            id(c)
            for sub in ast.walk(fn)
            if sub is not fn
            and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
            for c in ast.walk(sub)
        }
        for call in ast.walk(fn):
            if isinstance(call, ast.Call) and id(call) not in inner:
                yield fn, call


def _crediting_calls(
    path: Path, tree: ast.AST, methods: frozenset[str]
) -> Iterator[tuple[str, ast.Call]]:
    """``(<path>::<function>, call)`` for each port call crediting another."""
    rel = (
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        if path.is_absolute()
        else str(path)
    )
    for fn, call in _enclosing_functions(tree):
        if not (
            isinstance(call.func, ast.Attribute) and call.func.attr in methods
        ):
            continue
        if any(_credits_another(kw) for kw in call.keywords):
            yield f"{rel}::{fn.name}", call


def _violations(
    path: Path, tree: ast.AST, methods: frozenset[str]
) -> list[str]:
    return [
        site
        for site, call in _crediting_calls(path, tree, methods)
        if not _names_request(call)
    ]


def _sites_with_attribution() -> Iterator[tuple[Path, ast.AST]]:
    for path, tree in _corpus.files_mentioning("attributed_to", under=_CORE):
        if _PORTS in path.parents:
            continue
        yield path, tree


@pytest.mark.spec("CM-24-002")
@pytest.mark.spec("CM-24-020")
@pytest.mark.spec("ARCH-18-001")
def test_every_delegated_emit_names_the_request_it_carries_out() -> None:
    methods = _port_methods_taking_attribution()
    found = {
        v
        for path, tree in _sites_with_attribution()
        for v in _violations(path, tree, methods)
    }
    assert found == set(_EXEMPT), (
        "an outbound activity credits another actor in attributed_to but"
        " names no request in in_reply_to (CM-24-020, ADR-0199), or an"
        " exemption no longer matches a site (ARCH-18-006):\n"
        f"  not exempted: {sorted(found - set(_EXEMPT))}\n"
        f"  stale exemption: {sorted(set(_EXEMPT) - found)}"
    )


def test_the_port_methods_read_include_every_delegated_emit() -> None:
    """The method set is read from the ports, so it cannot silently go empty."""
    methods = _port_methods_taking_attribution()
    assert {
        "invite_actor_to_case",
        "offer_case_ownership_transfer",
        "offer_case_participant_role",
        "propose_embargo",
    } <= methods


def test_the_scan_finds_the_known_delegated_emits() -> None:
    """Positive control: the scan reaches the emits it exists to police.

    With no exemption, an empty scan would pass; this pins that the role
    offer forward, the relay, the transfer Offer and the stub Invite are each
    read as crediting another actor.
    """
    methods = _port_methods_taking_attribution()
    seen = {
        call.func.attr
        for path, tree in _sites_with_attribution()
        for _, call in _crediting_calls(path, tree, methods)
        if isinstance(call.func, ast.Attribute)
    }
    assert {
        "invite_actor_to_case",
        "offer_case_ownership_transfer",
        "offer_case_participant_role",
        "propose_embargo",
    } <= seen, seen


_METHODS = frozenset({"propose_embargo"})


@pytest.mark.parametrize(
    "call",
    [
        "f.propose_embargo(attributed_to=a.attributed_to)",
        "f.propose_embargo(attributed_to=self.proposer, in_reply_to=None)",
        "f.propose_embargo(**extra)",
    ],
)
def test_detects_a_credit_with_no_request(call: str) -> None:
    tree = _corpus.parse_inline(f"def f(self):\n    {call}\n")
    assert _violations(Path("x.py"), tree, _METHODS)


@pytest.mark.parametrize(
    "call",
    [
        "f.propose_embargo(attributed_to=a.attributed_to,"
        " in_reply_to=a.in_reply_to)",
        "f.propose_embargo(attributed_to=None)",
        "f.propose_embargo(attributed_to=self.actor_id)",
        "f.propose_embargo(embargo_id=e)",
        "f.other(attributed_to=self.proposer)",
    ],
)
def test_accepts_a_credit_with_its_request_or_no_credit(call: str) -> None:
    tree = _corpus.parse_inline(f"def f(self):\n    {call}\n")
    assert not _violations(Path("x.py"), tree, _METHODS)


def _ref_ids(value: object) -> list[str]:
    """The ids *value* names: a bare id, an object, or a list of either."""
    if value is None:
        return []
    if isinstance(value, list):
        return [i for v in value for i in _ref_ids(v)]
    ref = value if isinstance(value, str) else getattr(value, "id_", None)
    return [ref] if isinstance(ref, str) else []


@pytest.mark.spec("CM-24-002")
@pytest.mark.spec("CM-24-020")
def test_no_example_activity_credits_another_actor_without_a_request() -> None:
    offenders = []
    for name, activity in sorted(activity_examples().items()):
        (actor,) = _ref_ids(activity.actor) or [""]
        credited = _ref_ids(getattr(activity, "attributed_to", None))
        if all(same_actor_id(c, actor) for c in credited):
            continue
        if not _ref_ids(getattr(activity, "in_reply_to", None)):
            offenders.append(name)
    assert not offenders, (
        "example activities credit another actor in attributedTo with no"
        f" inReplyTo (CM-24-020): {offenders}"
    )
