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
"""The pin record of the external JSON-LD contexts and their pinned copies (VM-10-011)."""

import json

import pytest
from pydantic import ValidationError

from vultron.metadata.wire_context.pin import (
    PIN_PATH,
    THIRD_PARTY_JSONLD_DIR,
    ContextTerms,
    JsonLdPin,
    extract_terms,
    file_sha256,
    load_all_terms,
    load_pin,
)

_NOTICE_FILE_PATTERN = "NOTICE-*"


@pytest.mark.spec("VM-10-011")
def test_the_pin_maps_every_context_file_of_the_pinned_local_copy() -> None:
    pin = load_pin()
    on_disk = {
        path.relative_to(THIRD_PARTY_JSONLD_DIR).as_posix()
        for path in THIRD_PARTY_JSONLD_DIR.glob("*.jsonld")
        if path.is_file()
    }

    assert set(pin.sources.values()) == on_disk
    assert on_disk, "the pinned local copy holds at least one context"


def test_every_pinned_file_has_a_notice_file_beside_it() -> None:
    notice_files = list(THIRD_PARTY_JSONLD_DIR.glob(_NOTICE_FILE_PATTERN))
    assert notice_files, "at least one NOTICE file exists"

    # All contexts are in the same directory, so any NOTICE covers them
    for local in load_pin().sources.values():
        context_path = THIRD_PARTY_JSONLD_DIR / local
        assert context_path.is_file()


@pytest.mark.spec("VM-10-011", "VM-10-013")
def test_the_pinned_local_copy_is_unedited() -> None:
    pin = load_pin()

    edited = [
        local
        for local, digest in pin.sha256.items()
        if file_sha256(THIRD_PARTY_JSONLD_DIR / local) != digest
    ]

    assert edited == [], (
        f"these pinned files differ from their recorded digest: {edited}"
    )


@pytest.mark.spec("VM-10-011")
def test_the_pin_lists_the_four_cited_contexts() -> None:
    pin = load_pin()
    urls = set(pin.sources.keys())

    expected = {
        "https://www.w3.org/ns/activitystreams",
        "https://w3id.org/security/data-integrity/v2",
        "https://w3id.org/security/multikey/v1",
        "https://www.w3.org/ns/cid/v1",
    }

    assert urls == expected


@pytest.mark.spec("VM-10-011")
def test_extract_terms_reads_top_level_terms() -> None:
    pin = load_pin()
    as2_file = pin.sources["https://www.w3.org/ns/activitystreams"]
    as2_path = THIRD_PARTY_JSONLD_DIR / as2_file

    terms = extract_terms(as2_path)

    # AS2 defines many top-level terms
    assert "Accept" in terms.top_level
    assert "Reject" in terms.top_level
    assert "actor" in terms.top_level
    assert "object" in terms.top_level
    assert len(terms.top_level) > 50, "AS2 defines many terms"


@pytest.mark.spec("VM-10-011")
def test_extract_terms_reads_type_scoped_terms_from_multikey() -> None:
    pin = load_pin()
    multikey_file = pin.sources["https://w3id.org/security/multikey/v1"]
    multikey_path = THIRD_PARTY_JSONLD_DIR / multikey_file

    terms = extract_terms(multikey_path)

    # Multikey has a type-scoped context
    assert "Multikey" in terms.type_scoped
    multikey_terms = terms.type_scoped["Multikey"]
    assert "controller" in multikey_terms
    assert "publicKeyMultibase" in multikey_terms


@pytest.mark.spec("VM-10-011")
def test_extract_terms_reads_type_scoped_terms_from_data_integrity() -> None:
    pin = load_pin()
    di_file = pin.sources["https://w3id.org/security/data-integrity/v2"]
    di_path = THIRD_PARTY_JSONLD_DIR / di_file

    terms = extract_terms(di_path)

    # DataIntegrityProof has a type-scoped context
    assert "DataIntegrityProof" in terms.type_scoped
    proof_terms = terms.type_scoped["DataIntegrityProof"]
    assert "proofPurpose" in proof_terms
    assert "verificationMethod" in proof_terms


@pytest.mark.spec("VM-10-011")
def test_load_all_terms_returns_terms_for_each_context() -> None:
    all_terms = load_all_terms()

    assert len(all_terms) == 4
    assert "https://www.w3.org/ns/activitystreams" in all_terms
    assert "https://w3id.org/security/data-integrity/v2" in all_terms
    assert "https://w3id.org/security/multikey/v1" in all_terms
    assert "https://www.w3.org/ns/cid/v1" in all_terms

    # Each entry is a ContextTerms
    for _url, terms in all_terms.items():
        assert isinstance(terms, ContextTerms)
        assert isinstance(terms.top_level, frozenset)
        assert isinstance(terms.type_scoped, dict)


def _pin_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = json.loads(PIN_PATH.read_bytes())
    data.update(changes)
    return data


@pytest.mark.parametrize(
    "changes",
    [
        {"sources": {}},
        {"sha256": {}},
        {"sources": {"https://example.org/": "../escape.jsonld"}},
        {"sources": {"https://example.org/": "/absolute.jsonld"}},
        {"sources": {"https://example.org/": "sub/./dot.jsonld"}},
        {"sources": {"https://example.org/": "back\\slash.jsonld"}},
        {"surplus": "field"},
    ],
    ids=[
        "no-sources",
        "no-digests",
        "path-escapes-copy",
        "absolute-path",
        "unnormalized-path",
        "backslash-path",
        "unknown-field",
    ],
)
def test_a_malformed_pin_record_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        JsonLdPin.model_validate(_pin_data(**changes))


def test_a_name_starting_with_two_dots_is_a_relative_path() -> None:
    data = _pin_data()
    data["sources"] = {"https://example.org/": "..context.jsonld"}
    data["sha256"] = {"..context.jsonld": "0" * 64}

    assert (
        JsonLdPin.model_validate(data).sources["https://example.org/"]
        == "..context.jsonld"
    )
