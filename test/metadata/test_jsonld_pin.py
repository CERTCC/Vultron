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
"""The JSON-LD pin record and the terms read from its pinned copies (VM-10-011).

The digest check and the four-context check live in
``test_jsonld_context_pins.py``, which reads the record without this loader.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from vultron.metadata.wire_context.pin import (
    PIN_PATH,
    THIRD_PARTY_JSONLD_DIR,
    ContextTerms,
    JsonLdPin,
    UnreadableContextError,
    extract_terms,
    load_all_terms,
    load_pin,
)

_AS2 = "https://www.w3.org/ns/activitystreams"
_DATA_INTEGRITY = "https://w3id.org/security/data-integrity/v2"
_MULTIKEY = "https://w3id.org/security/multikey/v1"
_CID = "https://www.w3.org/ns/cid/v1"


@pytest.fixture(scope="module")
def all_terms() -> dict[str, ContextTerms]:
    return load_all_terms()


@pytest.mark.spec("VM-10-011")
def test_the_pin_maps_every_context_file_of_the_pinned_local_copy() -> None:
    on_disk = {path.name for path in THIRD_PARTY_JSONLD_DIR.glob("*.jsonld")}

    assert on_disk, "the pinned local copy holds no context"
    assert set(load_pin().sources.values()) == on_disk


@pytest.mark.spec("VM-10-011")
def test_every_pinned_source_is_named_in_a_notice_file() -> None:
    notices = " ".join(
        path.read_text(encoding="utf-8")
        for path in THIRD_PARTY_JSONLD_DIR.glob("NOTICE-*")
    )

    unnamed = [url for url in load_pin().sources if url not in notices]

    assert unnamed == [], f"no NOTICE file names these sources: {unnamed}"


@pytest.mark.spec("VM-10-011")
def test_load_all_terms_reads_each_pinned_context(
    all_terms: dict[str, ContextTerms],
) -> None:
    assert set(all_terms) == set(load_pin().sources)
    assert all(terms.top_level for terms in all_terms.values())


@pytest.mark.spec("VM-10-011")
def test_as2_terms_are_top_level_with_no_scoped_context(
    all_terms: dict[str, ContextTerms],
) -> None:
    as2 = all_terms[_AS2]

    assert {
        "Accept",
        "Reject",
        "actor",
        "object",
        "inReplyTo",
    } <= as2.top_level
    assert as2.type_scoped == {}


@pytest.mark.spec("VM-10-011")
def test_multikey_terms_are_type_scoped_not_top_level(
    all_terms: dict[str, ContextTerms],
) -> None:
    multikey = all_terms[_MULTIKEY]

    assert multikey.top_level == {"id", "type", "Multikey"}
    assert {"controller", "publicKeyMultibase"} <= multikey.type_scoped[
        "Multikey"
    ]


@pytest.mark.spec("VM-10-011")
def test_data_integrity_proof_purposes_are_scoped_under_proof_purpose(
    all_terms: dict[str, ContextTerms],
) -> None:
    data_integrity = all_terms[_DATA_INTEGRITY]
    proof = data_integrity.type_scoped["DataIntegrityProof"]
    purposes = data_integrity.type_scoped["DataIntegrityProof/proofPurpose"]

    assert {"proofPurpose", "verificationMethod", "cryptosuite"} <= proof
    assert {"assertionMethod", "authentication"} <= purposes
    assert "proofPurpose" not in data_integrity.top_level
    assert "assertionMethod" not in data_integrity.top_level


@pytest.mark.spec("VM-10-011")
def test_a_scoped_term_also_defined_at_top_level_is_only_top_level(
    all_terms: dict[str, ContextTerms],
) -> None:
    cid = all_terms[_CID]

    assert "controller" in cid.top_level
    assert "controller" not in cid.type_scoped["Multikey"]
    assert "publicKeyMultibase" in cid.type_scoped["Multikey"]
    assert all(
        not (terms & cid.top_level) for terms in cid.type_scoped.values()
    )


@pytest.mark.parametrize(
    "document",
    [
        {},
        [],
        {"@context": "https://example.org/context"},
        {"@context": ["https://example.org/context"]},
        {
            "@context": {
                "T": {"@id": "ex:T", "@context": "https://example.org/c"}
            }
        },
    ],
    ids=[
        "no-context",
        "not-an-object",
        "context-by-url",
        "context-list",
        "scoped-context-by-url",
    ],
)
def test_a_context_the_loader_cannot_read_is_refused(
    tmp_path: Path, document: object
) -> None:
    path = tmp_path / "context.jsonld"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(UnreadableContextError):
        extract_terms(path)


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
