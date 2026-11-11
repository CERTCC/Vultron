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
"""

import ast
import logging
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from vultron.errors import VultronActivityConstructionError
from vultron.wire.as2.factories import (
    rm_create_report_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.factories._construct import build_activity


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


@pytest.mark.spec("AF-04-003")
def test_report_factories_log_before_raising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The report factories log like every other factory (AF-04-003)."""
    with caplog.at_level(logging.WARNING):
        with pytest.raises(VultronActivityConstructionError):
            rm_create_report_activity(
                report="not-a-report",  # type: ignore[arg-type]
            )
    assert any(
        "rm_create_report_activity: invalid arguments:" in r.getMessage()
        for r in caplog.records
    )


_FACTORIES = (
    Path(__file__).parents[4] / "vultron" / "wire" / "as2" / "factories"
)

# Pinned exemption set: the factory-package functions that catch
# ``ValidationError`` themselves.  None builds an outbound activity: two
# coerce a held Invite to the class a reply embeds, and one parses an Offer.
# permanent: each raises its own message, not a factory's "invalid arguments"
_OWN_VALIDATION_HANDLERS = frozenset(
    {
        ("_construct.py", "build_activity"),
        ("case/full_case_invite.py", "_as_full_case_invite"),
        ("case/invite.py", "_as_case_invite"),
        ("report.py", "parse_submit_report_offer"),
    }
)


def _catches_validation_error(handler: ast.ExceptHandler) -> bool:
    names = (
        handler.type.elts
        if isinstance(handler.type, ast.Tuple)
        else [handler.type]
    )
    return any(
        isinstance(n, ast.Name) and n.id in {"ValidationError", "caught"}
        for n in names
    )


def _own_validation_handlers() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in _FACTORIES.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Try) and any(
                    _catches_validation_error(h) for h in node.handlers
                ):
                    found.add(
                        (path.relative_to(_FACTORIES).as_posix(), fn.name)
                    )
    return found


@pytest.mark.spec("AF-04-001")
def test_factories_build_through_the_one_helper() -> None:
    """A factory builds through ``build_activity`` instead of its own
    ``try/except ValidationError`` (CS-22-001); a listed handler that no
    longer exists is stale."""
    found = _own_validation_handlers()
    assert found <= _OWN_VALIDATION_HANDLERS, (
        "Build the activity through build_activity"
        f" (factories/_construct.py): {sorted(found - _OWN_VALIDATION_HANDLERS)}"
    )
    assert found >= _OWN_VALIDATION_HANDLERS, (
        f"Stale entries: {sorted(_OWN_VALIDATION_HANDLERS - found)}"
    )
