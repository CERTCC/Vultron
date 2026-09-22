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

from vultron.metadata.base import repo_root
from vultron.metadata.wire_context.sync import (
    CONTEXT_JSONLD_PATH,
    WRITE_COMMAND,
    _all_object_subclasses,
    _concrete_type_value,
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


def test_non_as2_wire_types_are_annotated_vultron() -> None:
    """AC-6: any wire type whose ``type`` value is not an AS2 term is VULTRON.

    Guards the mis-annotation the issue found (``as_EmbargoEvent`` inheriting
    ``_vocab_ns = AS`` from ``as_Event``): a Vultron-specific type left
    annotated ``AS`` would be silently dropped from the generated context.
    """
    as2_terms = set(WIRE_TYPE_MAP)
    offenders = []
    for cls in _all_object_subclasses():
        value = _concrete_type_value(cls)
        if value is None or value in as2_terms:
            continue
        if getattr(cls, "_vocab_ns", None) is not VocabNamespace.VULTRON:
            offenders.append(f"{cls.__name__} (type={value!r})")
    assert not offenders, (
        "these wire classes carry a non-AS2 type but are not annotated "
        f"VocabNamespace.VULTRON, so they miss the context: {offenders}"
    )


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
