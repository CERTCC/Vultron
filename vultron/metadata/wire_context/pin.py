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
"""Pinned local copies of the JSON-LD contexts Vultron cites (VM-10-011).

``third_party/jsonld/pin.json`` names each external context's URL and SHA-256
digest, and the pinned local copy sits beside it. The copy and the record are
third-party files outside ``vultron/``; only the term check and the tests read
them, never the runtime.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from vultron.metadata.pin_record import (
    PinRecord,
    RelativePath,
    Sha256,
    file_sha256,
)

#   parents[0] = wire_context, [1] = metadata, [2] = vultron, [3] = <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
#: Where the pinned local copy and its pin record sit: outside ``vultron/``,
#: which holds only this project's own code.
THIRD_PARTY_JSONLD_DIR = _REPO_ROOT / "third_party" / "jsonld"
#: The pin record.
PIN_PATH = THIRD_PARTY_JSONLD_DIR / "pin.json"
#: Separates the term names on the path to a nested scoped context.
SCOPE_SEPARATOR = "/"


class JsonLdPin(PinRecord):
    """The external JSON-LD contexts Vultron cites, and where they sit locally."""


def load_pin(path: Path = PIN_PATH) -> JsonLdPin:
    """Read and validate the pin record at *path*."""
    return JsonLdPin.model_validate_json(path.read_bytes())


class ContextTerms(BaseModel):
    """The terms a JSON-LD context defines, separated by scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    top_level: frozenset[str] = Field(
        description="Terms defined at the context's top level.",
    )
    type_scoped: dict[str, frozenset[str]] = Field(
        default_factory=dict,
        description=(
            "Terms defined only inside a scoped context, never at top level, "
            "keyed by the term that carries the scoped context. A scoped "
            "context nested in another is keyed by the path of terms, joined "
            "by ``SCOPE_SEPARATOR``: data-integrity's proof purposes sit under "
            "``DataIntegrityProof/proofPurpose``, and Multikey's "
            "``controller`` and ``publicKeyMultibase`` under ``Multikey``."
        ),
    )


class UnreadableContextError(ValueError):
    """A pinned context holds a shape the term loader cannot read."""


def _local_context(value: object, where: str) -> Mapping[str, object]:
    """Return *value* when it is an inline JSON-LD context object, else raise.

    The term check reads terms only from inline definitions; a context given
    as a URL or a list would hide terms this loader cannot see.
    """
    if not isinstance(value, dict):
        raise UnreadableContextError(
            f"{where}: @context is a {type(value).__name__}, not an inline "
            "context object"
        )
    return value


def _terms_of(context: Mapping[str, object]) -> frozenset[str]:
    """Return the terms *context* defines: every key not a JSON-LD keyword."""
    return frozenset(key for key in context if not key.startswith("@"))


def _collect_scoped(
    context: Mapping[str, object],
    scope: tuple[str, ...],
    top_level: frozenset[str],
    found: dict[str, frozenset[str]],
    where: str,
) -> None:
    """Add to *found* every scoped context inside *context*, at any depth."""
    for term, definition in context.items():
        if not isinstance(definition, dict) or "@context" not in definition:
            continue
        path = (*scope, term)
        key = SCOPE_SEPARATOR.join(path)
        scoped = _local_context(definition["@context"], f"{where}: {key}")
        found[key] = _terms_of(scoped) - top_level
        _collect_scoped(scoped, path, top_level, found, where)


def extract_terms(context_path: Path) -> ContextTerms:
    """Return the terms the JSON-LD context at *context_path* defines.

    Raises ``UnreadableContextError`` when the document has no inline
    ``@context`` object, so a context the loader cannot read never passes as
    one with no terms.
    """
    where = context_path.name
    document = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or "@context" not in document:
        raise UnreadableContextError(f"{where}: the document has no @context")
    context = _local_context(document["@context"], where)

    top_level = _terms_of(context)
    type_scoped: dict[str, frozenset[str]] = {}
    _collect_scoped(context, (), top_level, type_scoped, where)
    return ContextTerms(top_level=top_level, type_scoped=type_scoped)


def load_all_terms(
    pin: JsonLdPin | None = None,
    copy_dir: Path = THIRD_PARTY_JSONLD_DIR,
) -> dict[str, ContextTerms]:
    """Return the terms of each pinned context, keyed by the context's URL."""
    record = load_pin() if pin is None else pin
    return {
        url: extract_terms(copy_dir / filename)
        for url, filename in record.sources.items()
    }


__all__ = [
    "PIN_PATH",
    "SCOPE_SEPARATOR",
    "THIRD_PARTY_JSONLD_DIR",
    "ContextTerms",
    "JsonLdPin",
    "UnreadableContextError",
    "RelativePath",
    "Sha256",
    "extract_terms",
    "file_sha256",
    "load_all_terms",
    "load_pin",
]
