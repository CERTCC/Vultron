"""Every Retriever call-out point says whether the store can hold its answer.

BT-18-039 asks for a read-first guard wherever the case file or the actor's
own store can hold the fact a Retriever fetches.  Which Retrievers that is
depends on the data model, so each one states it in its docstring, and this
test keeps a new Retriever from arriving without the statement.

A Retriever is stated in two places: the fuzzer node's class docstring, and
the docstring of the core call-out bundle field that places it in a tree.
Both are checked.  A bundle field is a Retriever when its STOCHASTIC
backend is a fuzzer Retriever node; actor resolution has no fuzzer node, so
its field is named here.
"""

import ast
import dataclasses
import importlib
import inspect
import itertools
import pkgutil
import textwrap

import pytest

import vultron.demo.fuzzer as fuzzer_pkg
import vultron.demo.fuzzer.bundles as stochastic_pkg
from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ActorResolutionCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.guard import unwrap_call_out
from vultron.demo.fuzzer.call_out_point import RetrieverCallOutPoint

_MARKER = "Store-held answer (BT-18-039):"

#: Core-placed Retriever fields whose STOCHASTIC backend is no fuzzer node.
_RETRIEVER_FIELDS_WITHOUT_FUZZER_NODE: list[tuple[type, str]] = [
    (ActorResolutionCallOutBundle, "resolve_actor_factory"),
]


def _retriever_classes() -> list[type]:
    for module in pkgutil.walk_packages(
        fuzzer_pkg.__path__, prefix=f"{fuzzer_pkg.__name__}."
    ):
        importlib.import_module(module.name)
    found: list[type] = []
    pending = list(RetrieverCallOutPoint.__subclasses__())
    while pending:
        cls = pending.pop()
        if cls not in found:
            found.append(cls)
            pending.extend(cls.__subclasses__())
    return sorted(found, key=lambda c: f"{c.__module__}.{c.__qualname__}")


def _field_docstring(bundle_cls: type, field_name: str) -> str:
    """The attribute docstring under *field_name* in *bundle_cls* or a base."""
    for cls in bundle_cls.__mro__:
        if field_name not in vars(cls).get("__annotations__", {}):
            continue
        tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
        body = tree.body[0].body  # type: ignore[attr-defined]
        for stmt, following in itertools.pairwise(body):
            if (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == field_name
                and isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                and isinstance(following.value.value, str)
            ):
                return following.value.value
        return ""
    return ""


def _bundle_retriever_fields() -> list[tuple[type, str]]:
    fields: set[tuple[type, str]] = set(_RETRIEVER_FIELDS_WITHOUT_FUZZER_NODE)
    for module in pkgutil.iter_modules(stochastic_pkg.__path__):
        loaded = importlib.import_module(
            f"{stochastic_pkg.__name__}.{module.name}"
        )
        for name, bundle in vars(loaded).items():
            if not (
                name.endswith("_STOCHASTIC")
                and isinstance(bundle, CallOutBundle)
            ):
                continue
            for field in dataclasses.fields(bundle):  # type: ignore[arg-type]
                if not field.name.endswith("_factory"):
                    continue
                node = unwrap_call_out(getattr(bundle, field.name)(field.name))
                if isinstance(node, RetrieverCallOutPoint):
                    fields.add((type(bundle), field.name))
    return sorted(fields, key=lambda f: f"{f[0].__qualname__}.{f[1]}")


_RETRIEVERS = _retriever_classes()
_BUNDLE_FIELDS = _bundle_retriever_fields()


def _assert_states_verdict(doc: str, where: str) -> None:
    assert _MARKER in doc, (
        f"{where} does not say whether the store can hold its answer"
        f" ({_MARKER})"
    )
    verdict = doc.split(_MARKER, 1)[1].lstrip()
    assert verdict.startswith(("**can**", "**cannot**")), verdict[:40]


def test_retrievers_are_found():
    assert len(_RETRIEVERS) >= 1
    assert len(_BUNDLE_FIELDS) > len(_RETRIEVER_FIELDS_WITHOUT_FUZZER_NODE)


@pytest.mark.spec("BT-18-039")
@pytest.mark.parametrize(
    "retriever", _RETRIEVERS, ids=lambda c: c.__qualname__
)
def test_retriever_docstring_states_its_store_held_answer(retriever):
    _assert_states_verdict(
        retriever.__doc__ or "",
        f"{retriever.__module__}.{retriever.__qualname__}",
    )


@pytest.mark.spec("BT-18-039")
@pytest.mark.parametrize(
    ("bundle_cls", "field_name"),
    _BUNDLE_FIELDS,
    ids=[f"{c.__qualname__}.{f}" for c, f in _BUNDLE_FIELDS],
)
def test_bundle_retriever_field_states_its_store_held_answer(
    bundle_cls, field_name
):
    _assert_states_verdict(
        _field_docstring(bundle_cls, field_name),
        f"{bundle_cls.__qualname__}.{field_name}",
    )


@pytest.mark.spec("BT-18-039")
def test_actor_resolution_is_classified_as_store_held():
    doc = _field_docstring(
        ActorResolutionCallOutBundle, "resolve_actor_factory"
    )
    assert _MARKER in doc
    assert doc.split(_MARKER, 1)[1].lstrip().startswith("**can**")
