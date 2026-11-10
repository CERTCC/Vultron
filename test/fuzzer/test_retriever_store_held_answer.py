"""Every Retriever call-out point says whether the store can hold its answer.

BT-18-039 asks for a read-first guard wherever the case file or the actor's
own store can hold the fact a Retriever fetches.  Which Retrievers that is
depends on the data model, so each one states it in its docstring, and this
test keeps a new Retriever from arriving without the statement.
"""

import importlib
import pkgutil

import pytest

import vultron.demo.fuzzer as fuzzer_pkg
from vultron.demo.fuzzer.call_out_point import RetrieverCallOutPoint

_MARKER = "Store-held answer (BT-18-039):"


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


_RETRIEVERS = _retriever_classes()


def test_retrievers_are_found():
    assert len(_RETRIEVERS) >= 1


@pytest.mark.spec("BT-18-039")
@pytest.mark.parametrize(
    "retriever", _RETRIEVERS, ids=lambda c: c.__qualname__
)
def test_retriever_docstring_states_its_store_held_answer(retriever):
    doc = retriever.__doc__ or ""
    assert _MARKER in doc, (
        f"{retriever.__module__}.{retriever.__qualname__} does not say "
        f"whether the store can hold its answer ({_MARKER})"
    )
    verdict = doc.split(_MARKER, 1)[1].lstrip()
    assert verdict.startswith(("**can**", "**cannot**")), verdict[:40]
