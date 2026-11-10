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
"""Sentinel is not a call-out capability shape (BT-18-013, ADR-0097).

There are four call-out shapes: Evaluator, Retriever, Composer and Actuator. A
Sentinel is a call-in pattern: it watches a condition and calls a trigger on
its own initiative, so it has no call-out point node, no blackboard contract,
no domain bundle field and no backend factory.

This check imports every module of the call-out taxonomy — the shape mixins
and fuzzer nodes in ``vultron/demo/fuzzer/`` and the bundles and backends in
``vultron/core/behaviors/call_out/`` — and fails when:

- a class there is a Sentinel shape base, or subclasses one.  A shape base is
  a py_trees ``Behaviour`` or a ``*CallOutPoint`` mixin, so a programming-sense
  marker class such as ``_MissingSentinel`` does not count (AC-6 of #3424);
- a call-out bundle exposes a Sentinel factory field; or
- a docstring anywhere under ``vultron/``, or a sentence in a
  ``docs/developer/reference/bt-fuzzer/`` catalog, credits a Sentinel with
  writing a blackboard key or flag, which is what the old
  ``CheckNoNewDeploymentInfoNode`` docstring and the catalogs did.  A denial
  ("never writes", "not a flag") is allowed, since that is how the text explains
  the call-in pattern; the negation must come just before the write word.
"""

import ast
import dataclasses
import importlib
import pkgutil
import re
from types import ModuleType

import py_trees
import pytest

import vultron.core.behaviors.call_out as core_call_out
import vultron.demo.fuzzer as demo_fuzzer
from test.architecture import _corpus
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.demo.fuzzer import call_out_point

_TAXONOMY_PACKAGES = (core_call_out, demo_fuzzer)

#: The four call-out shape mixins (BT-18-013).
_SHAPE_BASES: tuple[type, ...] = (
    call_out_point.EvaluatorCallOutPoint,
    call_out_point.RetrieverCallOutPoint,
    call_out_point.ComposerCallOutPoint,
    call_out_point.ActuatorCallOutPoint,
)


def _is_sentinel_name(name: str) -> bool:
    return "sentinel" in name.lower()


def _is_shape_like(cls: type) -> bool:
    """A class that could serve as a call-out shape: a BT node or a mixin."""
    return issubclass(
        cls, py_trees.behaviour.Behaviour
    ) or cls.__name__.endswith("CallOutPoint")


def _taxonomy_modules() -> list[ModuleType]:
    """Import and return every module in the call-out taxonomy packages."""
    modules: list[ModuleType] = []
    for package in _TAXONOMY_PACKAGES:
        modules.append(package)
        for info in pkgutil.walk_packages(
            package.__path__, prefix=f"{package.__name__}."
        ):
            modules.append(importlib.import_module(info.name))
    return modules


def _taxonomy_classes() -> set[type]:
    """Every class defined in a call-out taxonomy module."""
    modules = _taxonomy_modules()
    names = {m.__name__ for m in modules}
    return {
        obj
        for module in modules
        for obj in vars(module).values()
        if isinstance(obj, type) and obj.__module__ in names
    }


def _all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    pending: list[type] = list(cls.__subclasses__())
    while pending:
        sub = pending.pop()
        if sub not in found:
            found.add(sub)
            pending.extend(sub.__subclasses__())
    return found


def sentinel_shape_violations(classes: set[type]) -> list[str]:
    """Name each class that is, or descends from, a Sentinel shape base."""
    violations: list[str] = []
    for cls in classes:
        sentinel_bases = [
            base.__qualname__
            for base in cls.__mro__
            if _is_sentinel_name(base.__name__)
        ]
        if sentinel_bases and (
            _is_shape_like(cls)
            or any(
                _is_shape_like(b)
                for b in cls.__mro__
                if _is_sentinel_name(b.__name__)
            )
        ):
            violations.append(
                f"{cls.__module__}.{cls.__qualname__} "
                f"(Sentinel in MRO: {', '.join(sentinel_bases)})"
            )
    return sorted(violations)


def sentinel_bundle_field_violations(bundles: set[type]) -> list[str]:
    """Name each bundle field that offers a Sentinel factory."""
    return sorted(
        f"{bundle.__qualname__}.{field.name}"
        for bundle in bundles
        if dataclasses.is_dataclass(bundle)
        for field in dataclasses.fields(bundle)
        if _is_sentinel_name(field.name)
    )


def _taxonomy_bundles() -> set[type]:
    _taxonomy_modules()
    return {
        b
        for b in _all_subclasses(CallOutBundle)
        if dataclasses.is_dataclass(b)
    }


#: A capitalised ``Sentinel`` (or ``Sentinels``) anywhere in a word, so
#: ``FooSentinel``, ``NewInfoSentinelNode`` and the plural count, but the
#: programming sense ("sentinel value", AC-6 of #3424) does not.
_SENTINEL_WORD = re.compile(r"Sentinels?(?![a-z])")
_WRITES_STATE = re.compile(
    r"\b(writ\w*|wrote|blackboard|flags?)\b", re.IGNORECASE
)
#: A denial: a negation at most two words before the write word ("never
#: writes", "not a flag", "never by writing", "no blackboard").
_DENIED_WRITE = re.compile(
    r"\b(never|not|no)\s+(?:\w+\s+){0,2}?(writ\w*|wrote|blackboard|flags?)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+")

#: The fuzzer-node catalogs that once credited Sentinels with writing flags.
_CATALOG_DIR = (
    _corpus.REPO_ROOT / "docs" / "developer" / "reference" / "bt-fuzzer"
)

_DocNode = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def sentinel_writer_sentences(text: str) -> list[str]:
    """Return each sentence of ``text`` crediting a Sentinel with a write."""
    claims: list[str] = []
    for sentence in _SENTENCE_END.split(" ".join(text.split())):
        if not _SENTINEL_WORD.search(sentence):
            continue
        undenied = _DENIED_WRITE.sub(" ", sentence)
        if _WRITES_STATE.search(undenied):
            claims.append(sentence)
    return claims


def sentinel_writer_claims(tree: ast.AST, label: str) -> list[str]:
    """Name each docstring sentence crediting a Sentinel with a written key."""
    claims: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, _DocNode):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        owner = getattr(node, "name", "<module>")
        claims.extend(
            f"{label}:{owner}: {sentence}"
            for sentence in sentinel_writer_sentences(doc)
        )
    return claims


@pytest.mark.spec("BT-18-013")
def test_no_docstring_credits_a_sentinel_with_a_blackboard_write() -> None:
    scanned = list(
        _corpus.files_mentioning(
            "Sentinel", under=_corpus.REPO_ROOT / "vultron"
        )
    )
    assert scanned, "found no source file that mentions a Sentinel"
    claims = [
        claim
        for path, tree in scanned
        for claim in sentinel_writer_claims(
            tree, path.relative_to(_corpus.REPO_ROOT).as_posix()
        )
    ]
    assert claims == []


@pytest.mark.spec("BT-18-013")
def test_no_fuzzer_catalog_credits_a_sentinel_with_a_blackboard_write() -> (
    None
):
    scanned = [
        (path, text)
        for path, text in _corpus.docs_mentioning("Sentinel")
        if path.is_relative_to(_CATALOG_DIR)
    ]
    assert scanned, "found no bt-fuzzer catalog page that mentions a Sentinel"
    claims = [
        f"{path.relative_to(_corpus.REPO_ROOT).as_posix()}: {sentence}"
        for path, text in scanned
        for sentence in sentinel_writer_sentences(text)
    ]
    assert claims == []


def test_docstring_check_catches_a_sentinel_writer_claim() -> None:
    source = (
        "class Reads:\n"
        '    """Reads the flag written by the upstream FooSentinel.\n\n'
        "    A Sentinel writes the change-detection flag this reads.\n\n"
        "    A Sentinel never writes into this tree.\n\n"
        "    Upstream Sentinels write the new_info flag.\n\n"
        "    The Sentinel writes the flag when no new info arrives.\n\n"
        "    The NewInfoSentinelNode writes it.\n\n"
        "    A Sentinel is not a flag; a sentinel value marks absence.\n"
        '    """\n'
    )
    claims = sentinel_writer_claims(_corpus.parse_inline(source), "planted.py")
    assert claims == [
        "planted.py:Reads: Reads the flag written by the upstream FooSentinel.",
        "planted.py:Reads: A Sentinel writes the change-detection flag this "
        "reads.",
        "planted.py:Reads: Upstream Sentinels write the new_info flag.",
        "planted.py:Reads: The Sentinel writes the flag when no new info "
        "arrives.",
        "planted.py:Reads: The NewInfoSentinelNode writes it.",
    ]


@pytest.mark.spec("BT-18-013")
def test_no_sentinel_shape_base_or_subclass_in_call_out_taxonomy() -> None:
    classes = _taxonomy_classes()
    shaped = {c for c in classes if issubclass(c, _SHAPE_BASES)}
    assert len(shaped) > len(_SHAPE_BASES), (
        "found no capability subclasses — the scan is not reaching the "
        "fuzzer nodes"
    )
    assert sentinel_shape_violations(classes) == []


@pytest.mark.spec("BT-18-013")
def test_shape_subclasses_are_never_sentinels() -> None:
    """Covers subclasses defined outside the scanned packages too."""
    _taxonomy_modules()
    subclasses = {s for base in _SHAPE_BASES for s in _all_subclasses(base)}
    assert subclasses
    assert sentinel_shape_violations(subclasses) == []


@pytest.mark.spec("BT-18-013")
def test_no_bundle_exposes_a_sentinel_factory_field() -> None:
    bundles = _taxonomy_bundles()
    assert len(bundles) > 1, "found no call-out bundles to check"
    assert sentinel_bundle_field_violations(bundles) == []


def test_shape_check_catches_a_sentinel_base_and_its_subclass() -> None:
    class SentinelCallOutPoint:
        pass

    class WatchesSomething(SentinelCallOutPoint):
        pass

    class Unrelated:
        pass

    class NewInfoSentinel(py_trees.behaviour.Behaviour):
        pass

    class _MissingSentinel:
        """A programming-sense marker class (AC-6), not a shape."""

    violations = sentinel_shape_violations(
        {
            SentinelCallOutPoint,
            WatchesSomething,
            Unrelated,
            NewInfoSentinel,
            _MissingSentinel,
        }
    )
    assert len(violations) == 3
    assert any("WatchesSomething" in v for v in violations)
    assert any("NewInfoSentinel " in v for v in violations)
    assert not any("_MissingSentinel" in v for v in violations)


def test_bundle_check_catches_a_sentinel_factory_field() -> None:
    @dataclasses.dataclass(frozen=True)
    class _Bundle:
        evaluate_factory: object = None
        new_info_sentinel_factory: object = None

    assert sentinel_bundle_field_violations({_Bundle}) == [
        "test_bundle_check_catches_a_sentinel_factory_field.<locals>."
        "_Bundle.new_info_sentinel_factory"
    ]
