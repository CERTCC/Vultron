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
"""Pinned copies of the external JSON-LD contexts Vultron cites (VM-10-011, VM-10-013).

The term check reads AS2, data-integrity, Multikey and Controlled Identifiers
terms from byte-for-byte copies under ``third_party/jsonld/``, recorded in a
``pin.json`` as ``third_party/csaf/`` records the CSAF schemas.  No copy exists
yet, so both tests are strict ``xfail`` until #6407 adds them.
"""

import hashlib
import json
from pathlib import Path

import pytest

_PIN_PATH = Path(__file__).resolve().parents[2] / "third_party/jsonld/pin.json"

_CITED_CONTEXTS = frozenset(
    {
        "https://www.w3.org/ns/activitystreams",
        "https://w3id.org/security/data-integrity/v2",
        "https://w3id.org/security/multikey/v1",
        "https://www.w3.org/ns/cid/v1",
    }
)

_TRACKED = "Tracked by #6407."


def _pinned_files() -> list[tuple[str, Path, str]]:
    """Each pinned context as (URL, local path, recorded SHA-256 digest)."""
    record = json.loads(_PIN_PATH.read_text())
    sources = record["sources"]
    digests = record["sha256"]
    return [
        (url, _PIN_PATH.parent / filename, digests[filename])
        for url, filename in sources.items()
    ]


@pytest.mark.spec("VM-10-011")
def test_each_cited_context_has_a_pinned_copy() -> None:
    pinned = _pinned_files()
    assert {url for url, _, _ in pinned} == _CITED_CONTEXTS
    assert all(path.is_file() for _, path, _ in pinned)


@pytest.mark.spec("VM-10-013")
def test_each_pinned_context_copy_matches_its_digest() -> None:
    pinned = _pinned_files()
    assert pinned, "the pin record lists no context"
    for url, path, digest in pinned:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == digest, f"{path} no longer matches the pin for {url}"
