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
"""The one pin record of the CSAF 2.1 draft and its pinned local copy (CSAF-05-001)."""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from vultron.metadata.csaf.regenerate import (
    resolve_relative_ref,
    schema_refs,
)
from vultron.wire.csaf.pin import (
    PIN_PATH,
    PINNED_COPY_DIR,
    CsafPin,
    file_sha256,
    load_pin,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CROSSWALK_VERSION = (
    _REPO_ROOT / "docs" / "reference" / "csaf_crosswalk" / "_csaf_version.md"
)
_COMMIT_IN_URL = re.compile(r"/oasis-tcs/csaf/(?:tree|blob)/([0-9a-f]{40})/")
_SHORT_COMMIT = re.compile(r"commit \[`([0-9a-f]{7})`\]")


@pytest.mark.spec("CSAF-05-001")
def test_the_crosswalk_names_the_pinned_commit() -> None:
    pin = load_pin()
    text = _CROSSWALK_VERSION.read_text(encoding="utf-8")

    full_commits = set(_COMMIT_IN_URL.findall(text))
    short_commits = set(_SHORT_COMMIT.findall(text))

    assert full_commits == {pin.commit}, (
        f"{_CROSSWALK_VERSION.name} links commits {sorted(full_commits)}; "
        f"{PIN_PATH.name} pins {pin.commit}"
    )
    assert short_commits == {pin.short_commit}
    assert f"({pin.draft_stage})" in text
    assert pin.repository.removeprefix("https://github.com/") in text


@pytest.mark.spec("CSAF-05-001", "CSAF-05-002")
def test_the_pin_maps_every_file_of_the_pinned_local_copy() -> None:
    pin = load_pin()
    on_disk = {
        path.relative_to(PINNED_COPY_DIR).as_posix()
        for path in PINNED_COPY_DIR.rglob("*")
        if path.is_file()
    }

    assert set(pin.sources.values()) == on_disk
    assert pin.root in on_disk


@pytest.mark.spec("CSAF-05-002")
def test_every_reference_in_the_copy_is_pinned() -> None:
    pin = load_pin()
    remote: set[str] = set()
    relative: set[str] = set()
    for local in pin.sources.values():
        schema = json.loads((PINNED_COPY_DIR / local).read_bytes())
        for ref in schema_refs(schema):
            target = ref.partition("#")[0]
            if "://" in target:
                remote.add(target)
            elif target:
                relative.add(resolve_relative_ref(target, local))

    assert remote, "the CSAF schema references other schemas by URL"
    assert remote <= set(pin.sources)
    assert relative <= set(pin.sources.values())


@pytest.mark.spec("CSAF-05-002")
def test_the_pinned_local_copy_is_unedited() -> None:
    pin = load_pin()

    edited = [
        local
        for local, digest in pin.sha256.items()
        if file_sha256(PINNED_COPY_DIR / local) != digest
    ]

    assert edited == [], (
        f"these pinned files differ from their recorded digest: {edited}"
    )


def _pin_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = json.loads(PIN_PATH.read_bytes())
    data.update(changes)
    return data


@pytest.mark.parametrize(
    "changes",
    [
        {"commit": "29b1e27"},
        {"commit": "29B1E27AA126B820CBD6EEE1830CA27EF02793D1"},
        {"draft_stage": ""},
        {"root": "/csaf_2.1/json_schema/csaf.json"},
        {"root": "../csaf.json"},
        {"root": "csaf_2.1/./json_schema/csaf.json"},
        {"root": "."},
        {"root": "csaf_2.1\\json_schema\\csaf.json"},
        {"root": "csaf_2.1//json_schema/csaf.json"},
        {"sha256": {}},
        {"root": "csaf_2.1/json_schema/absent.json"},
        {"sources": {}},
        {"surplus": "field"},
    ],
    ids=[
        "short-commit",
        "upper-case-commit",
        "blank-draft-stage",
        "absolute-root",
        "root-outside-copy",
        "unnormalized-root",
        "dot-root",
        "backslash-root",
        "empty-segment-root",
        "digests-missing",
        "root-not-in-sources",
        "no-sources",
        "unknown-field",
    ],
)
def test_a_malformed_pin_record_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CsafPin.model_validate(_pin_data(**changes))


def test_a_name_starting_with_two_dots_is_a_relative_path() -> None:
    data = _pin_data()
    data["sources"] = {"https://example.org/a": "..schema.json"}
    data["root"] = "..schema.json"
    data["sha256"] = {"..schema.json": "0" * 64}

    assert CsafPin.model_validate(data).root == "..schema.json"
