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
"""Tests for the generated ``docs/ns/context.jsonld`` (#2943, VM-10-001/002)."""

import json
import re

from vultron.metadata.base import repo_root
from vultron.metadata.wire_context.sync import (
    CONTEXT_JSONLD_PATH,
    WRITE_COMMAND,
    _all_object_subclasses,
    _concrete_type_value,
    as2_term_values,
    build_context_document,
    is_stale,
    render_context_json,
    vultron_context_terms,
)
from vultron.wire.as2.vocab.base.base import (
    ACTIVITY_STREAMS_NS,
    VULTRON_NS_URI,
)
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP


def _committed_context() -> dict:
    path = repo_root() / CONTEXT_JSONLD_PATH
    parsed: dict = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def _term_block(document: dict) -> dict[str, str]:
    """Return the ``vultron:``-prefixed term-mapping object of ``@context``."""
    context = document["@context"]
    assert isinstance(context, list)
    term_block: dict[str, str] = context[1]
    return term_block


def test_committed_context_is_not_stale() -> None:
    """AC-2: the committed file matches what the generator produces.

    This is the drift guard. It runs in the ordinary unit suite (and via
    ``wire-context --check`` in pre-commit/CI), so adding, removing, or
    re-annotating a Vultron-namespace wire type without regenerating goes red.
    """
    assert not is_stale(), (
        f"{CONTEXT_JSONLD_PATH} is out of sync with the wire vocabulary — "
        f"run '{WRITE_COMMAND}'."
    )


def test_as2_namespace_import_is_first() -> None:
    """AC-4: the AS2 namespace import stays first in the ``@context`` array."""
    context = build_context_document()["@context"]
    assert isinstance(context, list)
    assert context[0] == ACTIVITY_STREAMS_NS
    assert _term_block({"@context": context})["vultron"] == VULTRON_NS_URI


def test_every_vultron_type_resolves_through_context() -> None:
    """AC-5: every Vultron-namespace wire type has a term in the context.

    Enumerated straight from the class annotations, independently of the
    generator's own term collection, so the two must agree.
    """
    committed_terms = _term_block(_committed_context())
    for cls in _all_object_subclasses():
        if getattr(cls, "_vocab_ns", None) is not VocabNamespace.VULTRON:
            continue
        value = _concrete_type_value(cls)
        if value is None:
            continue
        assert value in committed_terms, (
            f"{cls.__name__} emits Vultron type {value!r} but no context term "
            f"resolves it — run '{WRITE_COMMAND}'."
        )
        assert committed_terms[value] == f"vultron:{value}"


def test_as2_term_set_excludes_vultron_terms() -> None:
    """The AS2 term set must not be the whole wire registry.

    ``WIRE_TYPE_MAP`` keys every wire type, Vultron ones included, so using it
    as the "is this an AS2 term?" oracle skips every registered class and makes
    the guard below vacuous.  Provenance comes from the defining module
    instead; this test pins that distinction so the shortcut cannot come back.
    """
    as2_terms = as2_term_values()
    for vultron_term in (
        "VulnerabilityCase",
        "CaseParticipant",
        "EmbargoEvent",
    ):
        assert vultron_term in WIRE_TYPE_MAP
        assert vultron_term not in as2_terms
    assert "Note" in as2_terms  # a real AS2 term is still present


def test_non_as2_wire_types_are_annotated_vultron() -> None:
    """AC-6: any wire type whose ``type`` value is not an AS2 term is VULTRON.

    Guards the mis-annotation the issue found (``as_EmbargoEvent`` inheriting
    ``_vocab_ns = AS`` from ``as_Event``): a Vultron-specific type left
    annotated ``AS`` would be silently dropped from the generated context.
    """
    as2_terms = as2_term_values()
    # The guard is only meaningful if Vultron types actually reach the check.
    assert as2_terms, "AS2 term set is empty — the oracle is broken"
    reached = 0
    offenders = []
    for cls in _all_object_subclasses():
        value = _concrete_type_value(cls)
        if value is None or value in as2_terms:
            continue
        reached += 1
        if getattr(cls, "_vocab_ns", None) is not VocabNamespace.VULTRON:
            offenders.append(f"{cls.__name__} (type={value!r})")
    assert not offenders, (
        "these wire classes carry a non-AS2 type but are not annotated "
        f"VocabNamespace.VULTRON, so they miss the context: {offenders}"
    )
    # Without this the assertion above can pass by examining nothing at all.
    # Core-registered terms (ADR-0099) never reach the annotation check, so the
    # floor is the terms the remaining wire classes contribute.
    annotated_terms = len(vultron_context_terms()) - len(
        _core_registered_vultron_terms()
    )
    assert annotated_terms > 0 and reached >= annotated_terms, (
        f"only {reached} Vultron-typed classes reached the annotation check, "
        f"fewer than the {annotated_terms} annotation-sourced terms — the "
        "AS2 term set is over-broad and the guard is silently vacuous"
    )


def _core_registered_vultron_terms() -> set[str]:
    """Non-AS2 ``type`` values of core classes registered in WIRE_TYPE_MAP."""
    as2_terms = as2_term_values()
    return {
        value
        for cls in WIRE_TYPE_MAP.values()
        if cls.__module__.startswith("vultron.core.models")
        and (value := _concrete_type_value(cls)) is not None
        and value not in as2_terms
    }


def test_core_registered_types_resolve_through_context() -> None:
    """Collapsed ``as_*`` aliases keep their context terms (ADR-0099 detail 3).

    A paired wire class is now an alias of its core class, which is not an
    ``as_Object`` subclass and carries no ``_vocab_ns``.  Enumerating only
    annotated wire classes silently dropped nine terms from the normative
    context; this pins that every such core type still resolves.
    """
    committed_terms = _term_block(_committed_context())
    core_terms = _core_registered_vultron_terms()
    for term in (
        "CaseParticipant",
        "VulnerabilityRecord",
        "VulnerabilityReport",
        "ParticipantStatus",
    ):
        assert term in core_terms
    missing = sorted(t for t in core_terms if t not in committed_terms)
    assert not missing, (
        f"core types {missing} are registered on the wire but no context "
        f"term resolves them — run '{WRITE_COMMAND}'."
    )
    assert "Person" not in core_terms  # an AS2 term is not re-declared


def test_enumeration_ignores_classes_defined_outside_the_vocab_package() -> (
    None
):
    """A test-defined wire subclass must not leak into enumeration.

    ``as_Object.__subclasses__()`` is a live graph: a class declared inside a
    test function joins it and cannot be removed by deleting its registry
    entries (``test_wire_base_hierarchy`` does exactly that).  Such a leak both
    failed this module's annotation guard spuriously and — when annotated
    VULTRON — injected a bogus term into the *normative* artifact.
    """
    from typing import ClassVar, Literal

    from pydantic import Field

    from vultron.wire.as2.vocab.objects.base import as_VultronObject

    before = vultron_context_terms()

    class as_LeakProbe(as_VultronObject):  # noqa: N801
        # Keeps the probe out of WIRE_TYPE_MAP too, not just enumeration (#3592).
        _wire_type_alias: ClassVar[bool] = True
        type_: Literal["LeakProbe"] = Field(
            default="LeakProbe",
            validation_alias="type",
            serialization_alias="type",
        )

    assert as_LeakProbe not in _all_object_subclasses()
    assert "LeakProbe" not in vultron_context_terms()
    assert vultron_context_terms() == before
    assert not is_stale()


def test_generator_terms_match_committed_terms() -> None:
    """The generator's term set equals the committed term set (sans prefix)."""
    committed = _term_block(_committed_context())
    committed.pop("vultron")
    assert committed == vultron_context_terms()


def test_render_is_deterministic_and_sorted() -> None:
    """Rendering twice is byte-identical and terms are alphabetically ordered."""
    assert render_context_json() == render_context_json()
    terms = list(vultron_context_terms())
    assert terms == sorted(terms)


def test_namespace_index_page_lists_exactly_the_generated_terms() -> None:
    """``docs/ns/index.md``'s "Declared types" table matches the context.

    The page is the human-readable face of the normative artifact, and its table
    is hand-maintained — so unlike ``context.jsonld`` itself, nothing stopped it
    from advertising a term the namespace does not declare. It listed
    ``VulnerabilityCaseStub`` until #2982: the stub emits
    ``type: "VulnerabilityCase"``, so it has no term of its own, and a receiver
    trusting the page would have expected ``vultron:VulnerabilityCaseStub`` to
    resolve.
    """
    page = (repo_root() / "docs/ns/index.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*`(\w+)`\s*\|", page, flags=re.MULTILINE)

    assert rows, "found no 'Declared types' rows in docs/ns/index.md"
    assert set(rows) == set(vultron_context_terms()), (
        "docs/ns/index.md's declared-type table disagrees with the generated "
        f"context. Only on the page: {sorted(set(rows) - set(vultron_context_terms()))}; "
        f"only in the context: {sorted(set(vultron_context_terms()) - set(rows))}. "
        f"Regenerate with '{WRITE_COMMAND}' and update the table to match."
    )
