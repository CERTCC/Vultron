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
"""Only an actor's outbox and the docs example renderers sign (SIG-05-004).

Seeded keys are guessable by design (ADR-0164), so the guarantee that one
actor never signs for another is in the code: the outbox sealer signs only
its owner's own activities, and the docs example renderer signs only
documentation examples, bodies no server sends, each as its own ``actor``.
This lists every module under ``vultron/`` that calls a proof-making
function of the signing module, and every one that computes a seeded key,
so a new caller fails here until it is reviewed.
"""

import ast

import pytest

from test.architecture import _corpus

#: The signing module's functions that make a proof.
_PROOF_MAKERS = frozenset({"sign", "sign_as_author", "sign_docs_example"})
#: The signing module's function that computes a private key from a seed.
_KEY_DERIVER = "seeded_signing_key"
_SIGNING_MODULE = "vultron/wire/as2/signing.py"

#: The modules allowed to make a proof: the outbox sealer, for its owner's
#: own activities, and the docs example renderers.
_ALLOWED_SIGNERS = [
    "vultron/adapters/outbox_sealed_body.py",
    "vultron/wire/as2/vocab/examples/_base.py",
]
#: The modules allowed to compute a seeded key outside the signing module:
#: the profile route, which publishes the public half of its own actor's key.
_ALLOWED_KEY_DERIVERS = [
    "vultron/adapters/driving/fastapi/routers/actors/_lookup.py",
]


def _calls(tree: ast.AST, names: frozenset[str]) -> bool:
    """Whether *tree* calls ``signing.<name>`` or a bare imported ``<name>``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in names
                and isinstance(func.value, ast.Name)
                and func.value.id == "signing"
            ):
                return True
            if isinstance(func, ast.Name) and func.id in names:
                return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "vultron.wire.as2.signing"
            and any(alias.name in names for alias in node.names)
        ):
            return True
    return False


def _modules_calling(names: frozenset[str]) -> list[str]:
    return sorted(
        rel
        for path, tree in _corpus.files_mentioning(
            *names, under=_corpus.REPO_ROOT / "vultron"
        )
        if (rel := str(path.relative_to(_corpus.REPO_ROOT))) != _SIGNING_MODULE
        and _calls(tree, names)
    )


def test_the_scan_sees_each_call_form():
    """The scan finds an attribute call and an import, so a pass is not
    vacuous."""
    assert _calls(
        _corpus.parse_inline("signing.sign_as_author(d, owner_id=o)\n"),
        _PROOF_MAKERS,
    )
    assert _calls(
        _corpus.parse_inline(
            "from vultron.wire.as2.signing import sign_docs_example\n"
        ),
        _PROOF_MAKERS,
    )
    assert not _calls(
        _corpus.parse_inline("signing.verify(d, k)\n"), _PROOF_MAKERS
    )


@pytest.mark.spec("SIG-05-004")
def test_only_the_outbox_and_the_example_renderers_sign():
    assert _modules_calling(_PROOF_MAKERS) == _ALLOWED_SIGNERS


@pytest.mark.spec("SIG-05-004")
def test_only_the_profile_route_computes_a_seeded_key():
    assert _modules_calling(frozenset({_KEY_DERIVER})) == (
        _ALLOWED_KEY_DERIVERS
    )
