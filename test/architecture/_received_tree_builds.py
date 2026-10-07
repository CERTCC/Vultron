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

"""Build every received-side tree once, from its factory's signature.

Shared by ratchets that ask a question of the *built* tree rather than of the
factory's source — which node sits under which gate — so a node reached
through a helper, a local variable or a nested factory is seen exactly as it
runs.  The factories are the sites
``test_received_tree_case_manager_gate._receive_calls`` finds: every top-level
function under ``vultron/core/behaviors/`` that calls
``create_receive_activity_tree``.

Each factory is called with an argument synthesized per parameter
(:func:`_argument_for`): a URI for an id, a minimal domain object for a
domain-typed parameter, a ``MagicMock`` for the received event (factories
only read ids off it to configure nodes).  An optional parameter is
*supplied*, not left at ``None``, so a node that a factory adds only when the
argument is present is built and walked too; a ``bool`` or a defaulted
bundle keeps its default.  A factory the synthesizer cannot build fails the
build with its name, so a new factory signature is a decision, not a skip.
"""

import functools
import importlib
import inspect
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from types import UnionType
from typing import Any, Union, get_args, get_origin
from unittest.mock import MagicMock

import py_trees

from test.architecture import _corpus
from test.architecture.test_received_tree_case_manager_gate import (
    _receive_calls,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.note import VultronNote
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

_Site = tuple[str, str]

_BASE = "https://example.org/received-tree-ratchet"
_CASE_ID = f"{_BASE}/cases/case"


def _domain_values() -> dict[type, Any]:
    """One minimal value per domain type a factory parameter names."""
    return {
        VulnerabilityCase: VulnerabilityCase(
            id_=_CASE_ID, attributed_to=f"{_BASE}/actors/owner"
        ),
        VultronNote: VultronNote(id_=f"{_BASE}/notes/note", content="note"),
        VulnerabilityReport: VulnerabilityReport(
            id_=f"{_BASE}/reports/report", content="report"
        ),
        EmbargoEvent: EmbargoEvent(
            id_=f"{_BASE}/embargoes/embargo",
            context=_CASE_ID,
            end_time=datetime(2030, 1, 1, tzinfo=UTC),
        ),
        LedgerPosition: LedgerPosition(log_index=0, entry_hash="0" * 64),
        RM: RM.ACCEPTED,
        CVDRole: CVDRole.VENDOR,
    }


def _members(annotation: Any) -> tuple[Any, ...]:
    """The non-``None`` members of a union annotation, or the annotation."""
    if get_origin(annotation) in (Union, UnionType):
        return tuple(a for a in get_args(annotation) if a is not type(None))
    return (annotation,)


def _argument_for(param: inspect.Parameter, domain: dict[type, Any]) -> Any:
    """A value for *param* that builds the factory's fullest tree.

    Raises:
        TypeError: no synthesis rule covers the parameter's annotation.
    """
    members = _members(param.annotation)
    for member in members:
        if member in domain:
            return domain[member]
    if str in members:
        return f"{_BASE}/{param.name}"
    if param.default is not inspect.Parameter.empty:
        # bool flags, call-out bundles, configs and other wiring keep their
        # default: they select behaviour, not which nodes exist.
        return param.default
    if bool in members:
        # A required flag: True adds the node it guards, so the walk sees it.
        return True
    if (
        any(
            inspect.isclass(m) and m.__name__.endswith("Event")
            for m in members
        )
        or param.name == "request"
    ):
        return MagicMock(name=param.name)
    if param.name.endswith("_obj"):
        return MagicMock(name=param.name)
    if any(get_origin(m) in (Sequence, list) for m in members):
        # Nodes a caller hands in are walked in the caller's own tree.
        return []
    raise TypeError(
        f"no argument rule for parameter {param.name!r}"
        f" ({param.annotation!r}); extend _argument_for"
    )


def received_tree_factories() -> dict[_Site, Callable[..., Any]]:
    """``(module path, function)`` → factory, for every received-tree site."""
    factories: dict[_Site, Callable[..., Any]] = {}
    for rel, scope, _ in _receive_calls():
        module = importlib.import_module(
            rel.removesuffix(".py").replace("/", ".")
        )
        candidate = getattr(module, scope)
        if inspect.isfunction(candidate):
            factories[(rel, scope)] = candidate
    return factories


@functools.cache
@_corpus.gc_paused()
def built_received_trees() -> dict[_Site, py_trees.behaviour.Behaviour]:
    """Every received-side tree, built once per process."""
    domain = _domain_values()
    trees: dict[_Site, py_trees.behaviour.Behaviour] = {}
    for site, factory in sorted(received_tree_factories().items()):
        signature = inspect.signature(factory, eval_str=False)
        hints = _resolved_hints(factory)
        kwargs = {
            name: _argument_for(
                param.replace(annotation=hints.get(name, param.annotation)),
                domain,
            )
            for name, param in signature.parameters.items()
        }
        try:
            trees[site] = factory(**kwargs)
        except Exception as error:  # report which factory, then fail
            raise AssertionError(
                f"{site[0]}:{site[1]}: cannot build from synthesized"
                f" arguments ({type(error).__name__}: {error}); extend"
                " _argument_for"
            ) from error
    return trees


def _resolved_hints(factory: Callable[..., Any]) -> dict[str, Any]:
    """The factory's annotations, each resolved where its module can.

    A string annotation naming a ``TYPE_CHECKING``-only import stays a
    string; :func:`_argument_for` then falls back to the parameter's default
    or its name.
    """
    namespace = vars(inspect.getmodule(factory))
    hints: dict[str, Any] = {}
    for name, written in inspect.get_annotations(factory).items():
        hints[name] = written
        if isinstance(written, str):
            try:
                # How typing.get_type_hints resolves it, one name at a time.
                hints[name] = eval(written, namespace)  # noqa: S307
            except NameError:
                pass
    return hints
