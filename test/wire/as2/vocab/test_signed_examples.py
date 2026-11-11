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
"""Docs examples of sent activities carry their actor's proof (SIG-01-001).

The examples under ``docs/reference/examples/`` and the ones the docs pages
render through ``json2md`` show each activity as its actor's outbox would
seal it, signed by that example's own ``actor`` with a fixed ``created``
(``signing.sign_docs_example``), so a regeneration writes the same bytes.
"""

import json
from pathlib import Path

import pytest

from vultron.core.models._helpers import format_timestamp
from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronUnsignableJsonError,
)
from vultron.wire.as2.vocab.examples._base import (
    EXAMPLE_TIMESTAMP,
    _example_json,
    _example_scope,
    json2md,
)
from vultron.wire.as2.vocab.examples.vocab_examples import (
    create_report,
    finder,
    gen_report,
)

_EXAMPLES_DIR = Path(__file__).parents[4] / "docs" / "reference" / "examples"


def _published_key(actor_id: str) -> str:
    """The key *actor_id*'s profile would publish, as a reader would read it."""
    key = signing.seeded_signing_key(actor_id)
    return signing.published_multikey(key, actor_id).public_key_multibase


def _committed() -> list[tuple[str, dict]]:
    return [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(_EXAMPLES_DIR.glob("*.json"))
    ]


def test_the_examples_directory_is_not_empty():
    assert _committed(), f"no examples under {_EXAMPLES_DIR}"


@pytest.mark.spec("SIG-01-001")
@pytest.mark.parametrize(
    "name,document",
    [item for item in _committed() if "actor" in item[1]],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_every_committed_activity_example_verifies_as_its_actor(
    name: str, document: dict
):
    proof = document["proof"]
    actor = signing.author_of(document)
    assert proof["verificationMethod"] == signing.key_id_for(actor), name
    signing.verify(document, _published_key(actor))


def test_an_example_naming_no_actor_is_shown_unsigned():
    for name, document in _committed():
        if "actor" not in document:
            assert "proof" not in document, name


def test_example_json_signs_as_the_actor_at_the_fixed_moment():
    document = json.loads(_example_json(create_report()))

    assert document["proof"]["created"] == format_timestamp(EXAMPLE_TIMESTAMP)
    assert document["proof"]["verificationMethod"] == signing.key_id_for(
        document["actor"]
    )
    signing.verify(document, _published_key(document["actor"]))


def _scoped_create_report():
    """The ``create_report`` example as the generator builds it."""
    with _example_scope("create_report"):
        return create_report()


def test_example_json_is_byte_stable():
    """Two builds of one example render the same bytes, proof included."""
    first = _example_json(_scoped_create_report())

    assert first == _example_json(_scoped_create_report())
    assert first == (_EXAMPLES_DIR / "create_report.json").read_text(
        encoding="utf-8"
    )


def test_a_profile_or_report_is_shown_unsigned():
    for obj in (finder(), gen_report()):
        assert "proof" not in json.loads(_example_json(obj))


def test_json2md_shows_the_signed_example():
    report = _scoped_create_report()
    block = json2md(report)
    inner = block.split("\n", 1)[1].rsplit("\n```", 1)[0]

    assert inner == _example_json(report)


def test_sign_docs_example_refuses_a_document_naming_no_actor():
    with pytest.raises(VultronUnsignableJsonError):
        signing.sign_docs_example(
            {"id": "urn:uuid:1", "type": "Note"}, created=EXAMPLE_TIMESTAMP
        )
