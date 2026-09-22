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
"""Generate the normative JSON-LD ``@context`` from the wire vocabulary (#2943).

VM-10-001 requires every outbound Vultron message to declare
``@context: "https://certcc.github.io/Vultron/ns/context.jsonld"``. That
document maps every Vultron-namespace ``type`` string (``CaseParticipant``,
``ProcessingFault``, …) to its ``vultron:`` IRI so a receiver can resolve the
term. Hand-maintaining it means a new Vultron-namespace wire type is added to
the code but forgotten in the context, and receivers silently cannot resolve
it. This module derives the document from the one source of truth — the wire
classes' ``_vocab_ns`` annotation — and a drift check (``--check``, wired into
pre-commit and CI) fails when the committed file diverges.

The term set is every distinct concrete ``type_`` value carried by a wire class
whose ``_vocab_ns`` is :data:`VocabNamespace.VULTRON` (VM-10-002). It is keyed
by the emitted ``type`` *value*, not the class name: ``VulnerabilityCaseStub``
emits ``type: "VulnerabilityCase"``, so it needs no separate term — the
``VulnerabilityCase`` term already resolves it.

CLI (``uv run wire-context``):
    --check   exit 1 if ``docs/ns/context.jsonld`` is stale
    --write   rewrite ``docs/ns/context.jsonld`` in place
"""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.wire.as2.vocab.base.base import (
    ACTIVITY_STREAMS_NS,
    VULTRON_NS_URI,
)
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.objects.base import as_Object

#: Repository-relative path of the generated artifact.
CONTEXT_JSONLD_PATH = "docs/ns/context.jsonld"

#: Command that regenerates the artifact, quoted in every failure message.
WRITE_COMMAND = "uv run wire-context --write"


def _import_all_vocab() -> None:
    """Import every wire vocabulary module so no class is missed.

    Enumeration walks ``as_Object.__subclasses__()``, so a class that has not
    been imported is invisible — the exact silent-drop failure this generator
    exists to prevent. Importing the top-level ``vultron.wire.as2`` package does
    **not** transitively load every leaf module (e.g. ``as_EmbargoEvent`` and
    ``VulnerabilityCaseStub`` are left out), so the package tree is walked and
    every module imported before enumeration.
    """
    import vultron.wire.as2.vocab as vocab_pkg

    for module in pkgutil.walk_packages(
        vocab_pkg.__path__, vocab_pkg.__name__ + "."
    ):
        importlib.import_module(module.name)


def _all_object_subclasses() -> set[type]:
    """Return every subclass of :class:`as_Object`, transitively."""
    _import_all_vocab()

    def descend(cls: type) -> set[type]:
        found: set[type] = set()
        for sub in cls.__subclasses__():
            found.add(sub)
            found |= descend(sub)
        return found

    return descend(as_Object)


def _concrete_type_value(cls: type) -> str | None:
    """Return *cls*'s default wire ``type`` value, or ``None`` if abstract.

    An abstract base (``VultronAS2Object``) leaves ``type_`` a union default of
    ``None``; only classes with a concrete default carry a wire term.
    """
    field = cls.model_fields.get("type_")  # type: ignore[attr-defined]
    if field is None:
        return None
    default = getattr(field, "default", None)
    value = getattr(default, "value", default)
    return value if isinstance(value, str) and value else None


def vultron_context_terms() -> dict[str, str]:
    """Map each Vultron-namespace wire ``type`` value to its ``vultron:`` IRI.

    The single source of truth is the class annotation ``_vocab_ns ==
    VocabNamespace.VULTRON``. Distinct concrete ``type_`` values are collected
    and mapped to ``vultron:<term>`` (VM-10-002).
    """
    terms: set[str] = set()
    for cls in _all_object_subclasses():
        if getattr(cls, "_vocab_ns", None) is not VocabNamespace.VULTRON:
            continue
        value = _concrete_type_value(cls)
        if value is not None:
            terms.add(value)
    return {term: f"vultron:{term}" for term in sorted(terms)}


def build_context_document() -> dict[str, object]:
    """Return the full ``context.jsonld`` document as a dict.

    The AS2 namespace import stays first in the ``@context`` array so AS2 terms
    resolve against ActivityStreams and only Vultron-specific terms are drawn
    from the ``vultron:`` namespace (VM-10-002, ADR-0069).
    """
    term_block: dict[str, str] = {"vultron": VULTRON_NS_URI}
    term_block.update(vultron_context_terms())
    return {"@context": [ACTIVITY_STREAMS_NS, term_block]}


def render_context_json() -> str:
    """Return the desired file contents (two-space indent, trailing newline)."""
    return json.dumps(build_context_document(), indent=2) + "\n"


def is_stale(root: Path | None = None) -> bool:
    """True when the committed file differs from the generated document."""
    target = (root or repo_root()) / CONTEXT_JSONLD_PATH
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    return current != render_context_json()


def write_context(root: Path | None = None) -> bool:
    """Rewrite the artifact if stale; return whether a write occurred."""
    target = (root or repo_root()) / CONTEXT_JSONLD_PATH
    desired = render_context_json()
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    if current == desired:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desired, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run wire-context [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help=f"Exit 1 if {CONTEXT_JSONLD_PATH} is stale.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help=f"Rewrite {CONTEXT_JSONLD_PATH} from the wire vocabulary.",
    )
    args = parser.parse_args(argv)

    if args.write:
        if write_context():
            print(f"Wrote {CONTEXT_JSONLD_PATH}")
        else:
            print(f"{CONTEXT_JSONLD_PATH} already in sync.")
        return

    if is_stale():
        print(
            f"[ERROR] {CONTEXT_JSONLD_PATH} is stale — run '{WRITE_COMMAND}' "
            "(VM-10-001, VM-10-002). A Vultron-namespace wire type was added, "
            "removed, or re-annotated without regenerating the context.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"{CONTEXT_JSONLD_PATH} is in sync.")


if __name__ == "__main__":
    main()
