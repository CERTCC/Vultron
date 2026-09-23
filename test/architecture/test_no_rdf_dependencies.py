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
"""Ratchet: ``rdflib`` and ``owlready2`` are not dependencies (IMPLTS-06-003).

Both libraries existed solely for ``vultron/scripts/ontology2md.py``, which
rendered the OWL/TTL ontology into five ``docs/reference/ontology/`` pages at
docs-build time. #3551 withheld those pages from the site, which left the script
with no callers and two RDF libraries sitting in the **runtime** dependency set
— and therefore in every deployed container image — for no runtime purpose. The
script and both dependencies were removed in #3570.

The ontology itself stays in the repository at ``ontology/`` as a working
record. Nothing reads it at runtime or at build time, so a reappearing import
means someone is reviving the renderer, which reopens the question of whether
the ontology is a maintained artifact. That is a decision, not a dependency
bump, so it fails here rather than passing quietly.

Source: ISSUE-3570.
"""

from __future__ import annotations

import tomllib

import pytest

from test.architecture import _corpus

_REPO_ROOT = _corpus.REPO_ROOT
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

RETIRED_RDF_LIBRARIES = ("rdflib", "owlready2")


def _declared_dependencies() -> list[str]:
    """Return every dependency string in the project and its dependency groups."""
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    declared = list(config.get("project", {}).get("dependencies", []))
    for group in config.get("dependency-groups", {}).values():
        declared.extend(entry for entry in group if isinstance(entry, str))
    optional = config.get("project", {}).get("optional-dependencies", {})
    for extra in optional.values():
        declared.extend(extra)
    return declared


def test_dependency_discovery_is_not_vacuous():
    """A ratchet that resolves no targets must fail, not pass (DF-09-009)."""
    declared = _declared_dependencies()
    assert (
        declared
    ), f"No dependencies parsed from {_PYPROJECT} — parser is broken."
    # A known-present dependency, so a silently-emptied list cannot pass.
    assert any(entry.startswith("pydantic") for entry in declared)


@pytest.mark.parametrize("library", RETIRED_RDF_LIBRARIES)
def test_rdf_library_is_not_a_declared_dependency(library: str):
    """IMPLTS-06-003: neither library may be declared, in any group."""
    offenders = [
        entry
        for entry in _declared_dependencies()
        if entry.split("[")[0].split(">")[0].split("=")[0].strip() == library
    ]
    assert not offenders, (
        f"'{library}' is declared in pyproject.toml as {offenders}. It was "
        "removed in #3570 along with vultron/scripts/ontology2md.py, its only "
        "user. Reintroducing it reopens whether the ontology is maintained "
        "(IMPLTS-06-003)."
    )


@pytest.mark.parametrize("library", RETIRED_RDF_LIBRARIES)
def test_rdf_library_is_not_imported(library: str):
    """No module under vultron/ or test/ may import either library.

    Reads the shared corpus rather than walking the tree, per TB-13-003 — this
    file is one of the siblings `test_ratchet_hygiene.py` polices.
    """
    offenders = sorted(
        str(path.relative_to(_REPO_ROOT))
        for directory in ("vultron", "test")
        for path, source in _corpus.sources_mentioning(
            f"import {library}", under=_REPO_ROOT / directory
        )
        # This file names both libraries in prose and in its own assertions, so
        # match import statements at line starts rather than the bare substring.
        if any(
            line.strip().startswith((f"import {library}", f"from {library}"))
            for line in source.splitlines()
        )
    )
    assert not offenders, (
        f"'{library}' is imported by {offenders}, but it is no longer a "
        "dependency, so those modules cannot run (IMPLTS-06-003)."
    )


def test_ontology_ttl_files_are_retained():
    """The artifact stays in the repo; only its renderer and deps went.

    If this fails, the ontology was deleted rather than withheld, which is not
    what #3551 decided — and it would also make the `docs-withheld` declaration
    for the OWL/TTL ontology stale.
    """
    assert list((_REPO_ROOT / "ontology").glob("*.ttl")), (
        "ontology/*.ttl is empty. #3551 retains the ontology in the repository "
        "and withholds it from the site; it does not delete it."
    )
