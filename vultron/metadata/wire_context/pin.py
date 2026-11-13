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

import hashlib
import json
from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from vultron.primitives import NonEmptyString

#   parents[0] = wire_context, [1] = metadata, [2] = vultron, [3] = <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
#: Where the pinned local copy and its pin record sit: outside ``vultron/``,
#: which holds only this project's own code.
THIRD_PARTY_JSONLD_DIR = _REPO_ROOT / "third_party" / "jsonld"
#: The pin record.
PIN_PATH = THIRD_PARTY_JSONLD_DIR / "pin.json"


def _relative_posix_path(value: str) -> str:
    """Return *value* when it is a plain relative POSIX path, else raise.

    Every segment must be a real name: no empty, ``.`` or ``..`` segment and no
    backslash, so the path stays inside the pinned local copy on any platform.
    """
    parts = value.split("/")
    if "\\" in value or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"{value!r} is not a relative path inside the copy")
    return value


RelativePath = Annotated[NonEmptyString, AfterValidator(_relative_posix_path)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class JsonLdPin(BaseModel):
    """The external JSON-LD contexts Vultron cites, and where they sit locally."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: dict[NonEmptyString, RelativePath] = Field(
        min_length=1,
        description=(
            "Each external context's URL, mapped to its filename inside the "
            "pinned local copy."
        ),
    )

    sha256: dict[RelativePath, Sha256] = Field(
        description=(
            "The SHA-256 digest of each file of the pinned local copy, so a "
            "hand edit to the copy is detected."
        ),
    )

    @model_validator(mode="after")
    def _files_agree(self) -> JsonLdPin:
        files = set(self.sources.values())
        if set(self.sha256) != files:
            raise ValueError("sha256 must list exactly the files in sources")
        return self


def file_sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pin(path: Path = PIN_PATH) -> JsonLdPin:
    """Read and validate the pin record at *path*."""
    return JsonLdPin.model_validate_json(path.read_bytes())


class ContextTerms(BaseModel):
    """The terms a JSON-LD context defines, separated by scope."""

    model_config = ConfigDict(frozen=True)

    top_level: frozenset[str] = Field(
        default_factory=frozenset,
        description="Terms defined at the context's top level.",
    )
    type_scoped: dict[str, frozenset[str]] = Field(
        default_factory=dict,
        description=(
            "Terms defined inside type-scoped contexts, keyed by type name. "
            "For example, Multikey's controller and publicKeyMultibase are "
            "under the Multikey type's scoped context."
        ),
    )


def extract_terms(context_path: Path) -> ContextTerms:
    """Extract the terms a JSON-LD context defines.

    Returns the top-level terms and, for each type that carries a scoped
    context, the terms that scoped context defines.
    """
    data = json.loads(context_path.read_text())
    context = data.get("@context", {})

    # Top-level terms are the keys that are not @-prefixed metadata
    top_level_terms = {key for key in context if not key.startswith("@")}

    # Type-scoped terms: look for keys whose value is a dict with @context
    type_scoped_terms: dict[str, frozenset[str]] = {}
    for key, value in context.items():
        if isinstance(value, dict) and "@context" in value:
            # This is a type with a scoped context
            scoped_context = value["@context"]
            if isinstance(scoped_context, dict):
                scoped_terms = {
                    k for k in scoped_context if not k.startswith("@")
                }
                type_scoped_terms[key] = frozenset(scoped_terms)

    return ContextTerms(
        top_level=frozenset(top_level_terms),
        type_scoped=type_scoped_terms,
    )


def load_all_terms(pin: JsonLdPin | None = None) -> dict[str, ContextTerms]:
    """Load terms from all pinned contexts.

    Returns a dict mapping each context URL to its extracted terms.
    """
    if pin is None:
        pin = load_pin()

    result: dict[str, ContextTerms] = {}
    for url, filename in pin.sources.items():
        context_path = THIRD_PARTY_JSONLD_DIR / filename
        result[url] = extract_terms(context_path)

    return result


__all__ = [
    "THIRD_PARTY_JSONLD_DIR",
    "PIN_PATH",
    "JsonLdPin",
    "RelativePath",
    "Sha256",
    "ContextTerms",
    "file_sha256",
    "load_pin",
    "extract_terms",
    "load_all_terms",
]
