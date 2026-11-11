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
"""Tests for ``build_activity``, the factories' one construction helper.

Spec coverage:
- AF-04-001: a ``ValidationError`` becomes ``VultronActivityConstructionError``.
- AF-04-003: the failure is logged at WARNING before the raise.

``OWN_VALIDATION_HANDLER_EXEMPTIONS`` is a pinned exemption set (ARCH-18):
the factory-package scopes allowed to catch a validation failure themselves.
"""

import ast
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

from test.support.objects import make
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR,
)
from vultron.errors import VultronActivityConstructionError
from vultron.wire.as2.factories import (
    create_processing_fault_activity,
    offer_case_participant_activity,
    rm_close_report_activity,
    rm_create_report_activity,
    rm_engage_case_activity,
    rm_invalidate_report_activity,
    rm_invite_to_case_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault


class _Thing(BaseModel):
    count: int


def _refuse() -> int:
    """An argument expression that refuses with ``ValidationError``."""
    _Thing.model_validate({"count": "not a number"})
    raise AssertionError("unreachable")


def test_build_activity_returns_the_built_object() -> None:
    built = build_activity("make_thing", _Thing, lambda: {"count": 3})
    assert built == _Thing(count=3)


@pytest.mark.spec("AF-04-001")
@pytest.mark.spec("AF-04-003")
def test_constructor_validation_error_becomes_construction_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        with pytest.raises(
            VultronActivityConstructionError,
            match=r"^make_thing: invalid arguments$",
        ) as info:
            build_activity("make_thing", _Thing, lambda: {"count": "x"})
    assert isinstance(info.value.__cause__, ValidationError)
    assert any(
        record.levelno == logging.WARNING
        and record.getMessage().startswith("make_thing: invalid arguments:")
        for record in caplog.records
    )


@pytest.mark.spec("AF-04-001")
def test_argument_expression_refusal_becomes_construction_error() -> None:
    """The fields run inside the guarded scope, so their refusal is caught."""
    with pytest.raises(VultronActivityConstructionError) as info:
        build_activity("make_thing", _Thing, lambda: {"count": _refuse()})
    assert isinstance(info.value.__cause__, ValidationError)


def test_also_names_further_exception_types() -> None:
    def fields() -> dict[str, int]:
        raise KeyError("missing")

    with pytest.raises(VultronActivityConstructionError) as info:
        build_activity("make_thing", _Thing, fields, also=(KeyError,))
    assert isinstance(info.value.__cause__, KeyError)


def test_other_exceptions_propagate_unchanged() -> None:
    def fields() -> dict[str, int]:
        raise KeyError("missing")

    with pytest.raises(KeyError):
        build_activity("make_thing", _Thing, fields)


@pytest.mark.spec("AF-04-001")
def test_named_case_refusal_reaches_the_caller_as_construction_error() -> None:
    """``_named_case`` refuses a case with no id inside the factory's scope."""
    with pytest.raises(
        VultronActivityConstructionError,
        match=r"^rm_engage_case_activity: invalid arguments$",
    ):
        rm_engage_case_activity("", actor="https://example.org/actors/a")


def _not_a_report_offer() -> tuple[tuple[object, ...], dict[str, object]]:
    """An Offer of something other than a report."""
    offer = make(
        as_Offer,
        actor="https://example.org/actors/a",
        object_="https://example.org/notes/1",
    )
    return (offer,), {}


_Call = Callable[[], tuple[tuple[object, ...], dict[str, object]]]

_REPORT_FACTORY_CALLS: tuple[tuple[Callable[..., object], _Call], ...] = (
    (rm_create_report_activity, lambda: (("not-a-report",), {})),
    (
        rm_submit_report_activity,
        lambda: (("not-a-report",), {"to": "https://example.org/actors/b"}),
    ),
    (rm_read_report_activity, _not_a_report_offer),
    (rm_validate_report_activity, _not_a_report_offer),
    (rm_invalidate_report_activity, _not_a_report_offer),
    (rm_close_report_activity, _not_a_report_offer),
)


def _assert_logged(factory: Callable[..., object], caplog: Any) -> None:
    assert any(
        f"{factory.__name__}: invalid arguments:" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.spec("AF-04-003")
@pytest.mark.parametrize(
    ("factory", "call"),
    _REPORT_FACTORY_CALLS,
    ids=[f.__name__ for f, _ in _REPORT_FACTORY_CALLS],
)
def test_report_factories_log_before_raising(
    factory: Callable[..., object],
    call: _Call,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The report factories log like every other factory (AF-04-003)."""
    args, kwargs = call()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(VultronActivityConstructionError):
            factory(*args, **kwargs)
    _assert_logged(factory, caplog)


@pytest.mark.spec("AF-04-001", "AF-04-003")
@pytest.mark.parametrize(
    ("factory", "args", "kwargs"),
    [
        (
            offer_case_participant_activity,
            ("https://example.org/actors/b",),
            {
                "target": "https://example.org/cases/1",
                "roles": [cast(Any, "bogus")],
            },
        ),
        (
            rm_invite_to_case_activity,
            (),
            {"invitee": "https://example.org/actors/b", "target": ""},
        ),
    ],
    ids=["participant", "invite-stub"],
)
def test_argument_construction_runs_inside_the_guarded_scope(
    factory: Callable[..., object],
    args: tuple[object, ...],
    kwargs: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The participant an Offer carries and the stub an Invite carries are
    built inside the factory's scope, so a bad argument is a construction
    error, not a raw ``ValidationError`` (AF-04-001)."""
    with caplog.at_level(logging.WARNING):
        with pytest.raises(VultronActivityConstructionError) as info:
            factory(*args, **kwargs)
    assert isinstance(info.value.__cause__, ValidationError)
    _assert_logged(factory, caplog)


@pytest.mark.spec("AF-04-001")
def test_processing_fault_factory_reports_a_validation_failure() -> None:
    """``create_processing_fault_activity`` builds through the helper too."""
    fault = make(
        as_ProcessingFault,
        failure_class=VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR,
        in_reply_to="https://example.org/activities/1",
    )
    with pytest.raises(VultronActivityConstructionError) as info:
        create_processing_fault_activity(actor="", fault=fault)
    assert isinstance(info.value.__cause__, ValidationError)


_FACTORIES = (
    Path(__file__).parents[4] / "vultron" / "wire" / "as2" / "factories"
)

# Pinned exemption set: the scopes in the factory package that catch a
# validation failure themselves.  The helper is the one place a factory's
# failure is caught (CS-22-001); the others build no outbound activity: two
# coerce a held Invite to the class a reply embeds, one parses an Offer, and
# one parses a ``published`` string (``ValueError``, which ``ValidationError``
# subclasses); each raises its own message, not "invalid arguments".
# permanent: AF-04-001, CS-22-001 (build_activity is the one handler)
OWN_VALIDATION_HANDLER_EXEMPTIONS = frozenset(
    {
        ("_construct.py", "build_activity"),
        ("case/full_case_invite.py", "_as_full_case_invite"),
        ("case/invite.py", "_as_case_invite"),
        ("embargo/negotiation.py", "_published_instant"),
        ("report.py", "parse_submit_report_offer"),
    }
)

#: Exception names a handler may catch without catching a validation
#: failure: what the factory package raises or catches for other reasons.
_OTHER_EXCEPTIONS = frozenset(
    {"AttributeError", "KeyError", "TypeError", "VultronParseError"}
)


def _validation_aliases(tree: ast.Module) -> frozenset[str]:
    """Every local name *tree* binds to pydantic's ``ValidationError``."""
    return frozenset(
        {"ValidationError"}
        | {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
            if alias.name == "ValidationError"
        }
    )


def _may_catch_validation_error(
    handler: ast.ExceptHandler, aliases: frozenset[str]
) -> bool:
    """Whether *handler* can catch a ``ValidationError``.

    A bare ``except``, ``Exception``, ``BaseException``, ``ValidationError``
    under any alias, and a name or attribute that is no known non-validation
    exception class (``pydantic.ValidationError``, ``mod.ValueError``, a
    variable holding a tuple as ``build_activity``'s does) all can.
    """
    if handler.type is None:
        return True
    types = (
        handler.type.elts
        if isinstance(handler.type, ast.Tuple)
        else [handler.type]
    )
    for node in types:
        if isinstance(node, ast.Attribute):
            if node.attr not in _OTHER_EXCEPTIONS:
                return True
            continue
        if not isinstance(node, ast.Name):
            return True
        if node.id in aliases or node.id in {"Exception", "BaseException"}:
            return True
        if node.id not in _OTHER_EXCEPTIONS:
            return True
    return False


def _scopes(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    """The module and every function in it, each with its name."""
    scopes: list[tuple[str, ast.AST]] = [("<module>", tree)]
    scopes.extend(
        (node.name, node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return scopes


def own_validation_handlers_in(tree: ast.Module) -> set[str]:
    """The scopes of *tree* that hold a handler of a validation failure.

    A ``try`` belongs to the innermost function around it, or to
    ``<module>`` when no function encloses it.
    """
    aliases = _validation_aliases(tree)
    owner: dict[int, str] = {}
    for name, scope in _scopes(tree):
        for node in ast.walk(scope):
            if isinstance(node, (ast.Try, ast.TryStar)):
                owner[id(node)] = name
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, ast.TryStar)) and any(
            _may_catch_validation_error(h, aliases) for h in node.handlers
        ):
            found.add(owner[id(node)])
    return found


def _own_validation_handlers() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in _FACTORIES.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(_FACTORIES).as_posix()
        found.update(
            (rel, scope) for scope in own_validation_handlers_in(tree)
        )
    return found


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("try:\n    pass\nexcept ValidationError:\n    pass\n", {"<module>"}),
        (
            "from pydantic import ValidationError as VE\n"
            "def f():\n    try:\n        pass\n    except VE:\n        pass\n",
            {"f"},
        ),
        (
            "async def f():\n    try:\n        pass\n"
            "    except pydantic.ValidationError:\n        pass\n",
            {"f"},
        ),
        (
            "def f():\n    try:\n        pass\n    except:\n        pass\n",
            {"f"},
        ),
        (
            "def f():\n    try:\n        pass\n"
            "    except Exception:\n        pass\n",
            {"f"},
        ),
        (
            "def f():\n    try:\n        pass\n    except caught:\n        pass\n",
            {"f"},
        ),
        (
            "def f():\n    try:\n        pass\n"
            "    except VultronParseError:\n        pass\n",
            set(),
        ),
        (
            "def f():\n    try:\n        pass\n"
            "    except* ValidationError:\n        pass\n",
            {"f"},
        ),
        (
            "def f():\n    try:\n        pass\n"
            "    except builtins.ValueError:\n        pass\n",
            {"f"},
        ),
        (
            "def f():\n    try:\n        pass\n"
            "    except errors.VultronParseError:\n        pass\n",
            set(),
        ),
    ],
    ids=[
        "module",
        "alias",
        "attribute-async",
        "bare",
        "exception",
        "variable",
        "other",
        "except-star",
        "attribute-other",
        "attribute-known",
    ],
)
def test_the_scan_finds_each_shape_of_handler(
    source: str, expected: set[str]
) -> None:
    assert own_validation_handlers_in(ast.parse(source)) == expected


@pytest.mark.spec("AF-04-001")
def test_factories_build_through_the_one_helper() -> None:
    """A factory builds through ``build_activity`` instead of its own
    ``try/except ValidationError`` (CS-22-001); a listed handler that no
    longer exists is stale."""
    found = _own_validation_handlers()
    listed = OWN_VALIDATION_HANDLER_EXEMPTIONS
    assert found <= listed, (
        "Build the activity through build_activity"
        f" (factories/_construct.py): {sorted(found - listed)}"
    )
    assert listed <= found, f"Stale entries: {sorted(listed - found)}"
