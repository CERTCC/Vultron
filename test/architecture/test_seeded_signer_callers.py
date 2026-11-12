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
_SIGNING_MODULE_NAME = "vultron.wire.as2.signing"
_SIGNING_MODULE = "vultron/wire/as2/signing.py"

#: Each module allowed to make a proof, and the one function it may call:
#: the outbox sealer signs its owner's own activities, and the docs example
#: renderers sign documentation examples as their own ``actor``.
_ALLOWED_SIGNERS = {
    "vultron/adapters/outbox_sealed_body.py": {"sign_as_author"},
    "vultron/wire/as2/vocab/examples/_base.py": {"sign_docs_example"},
}
#: The modules allowed to compute a seeded key outside the signing module:
#: the profile route, which publishes the public half of its own actor's key.
_ALLOWED_KEY_DERIVERS = {
    "vultron/adapters/driving/fastapi/routers/actors/_lookup.py": {
        _KEY_DERIVER
    },
}


def _module_aliases(tree: ast.AST) -> set[str]:
    """The dotted names *tree* binds to the signing module."""
    aliases = {_SIGNING_MODULE_NAME}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _SIGNING_MODULE_NAME:
                    aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and (
            node.module == "vultron.wire.as2"
        ):
            for alias in node.names:
                if alias.name == "signing":
                    aliases.add(alias.asname or "signing")
    return aliases


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return None if base is None else f"{base}.{node.attr}"
    return None


def _called(tree: ast.AST, names: frozenset[str]) -> set[str]:
    """The functions of *names* *tree* reaches in, or imports out of, signing.

    Any reference counts, called or not, so binding one to a local name
    (``f = signing.sign``) is seen too: an attribute on the module under any
    name it is bound to (``signing.sign``, ``s.sign``,
    ``vultron.wire.as2.signing.sign``) or on any path ending in ``signing``
    (``as2.signing.sign``), a ``getattr`` on the module, and any of *names*
    imported from it under any alias.  A star import from the module
    reaches every one of *names*.
    """
    modules = _module_aliases(tree)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in names:
            base = _dotted(node.value)
            if base is not None and (
                base in modules or base.rsplit(".", 1)[-1] == "signing"
            ):
                found.add(node.attr)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and node.args
            and _dotted(node.args[0]) in modules
        ):
            # The name is a string a scan cannot follow; count them all.
            found.update(names)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module == _SIGNING_MODULE_NAME
        ):
            found.update(
                names
                if any(alias.name == "*" for alias in node.names)
                else (
                    alias.name for alias in node.names if alias.name in names
                )
            )
    return found


def _references(tree: ast.AST, names: frozenset[str]) -> set[str]:
    """The names of *names* *tree* binds, imports or reads, by any path."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in names:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in names:
            found.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            found.update(a.name for a in node.names if a.name in names)
    return found


def _callers(names: frozenset[str]) -> dict[str, set[str]]:
    callers: dict[str, set[str]] = {}
    for path, tree in _corpus.files_mentioning(
        *names, under=_corpus.REPO_ROOT / "vultron"
    ):
        rel = str(path.relative_to(_corpus.REPO_ROOT))
        if rel == _SIGNING_MODULE:
            continue
        called = _called(tree, names)
        if called:
            callers[rel] = called
    return callers


#: The allowed signers' own functions that sign for whatever actor they are
#: given, each with the only modules that may reach it.  The outbox sealer
#: signs as ``seal_outbound_body``'s store owner, but its helper takes the
#: owner as an argument; the renderers sign as any example's ``actor``.  So a
#: module outside these homes that calls one is a wrapper around a signer,
#: and the allow-list above would not see it.
_EXAMPLES_PACKAGE = "vultron/wire/as2/vocab/examples/"
_SIGNING_WRAPPERS = {
    "signed_outbound_body": ("vultron/adapters/outbox_sealed_body.py",),
    "_example_json": (_EXAMPLES_PACKAGE,),
    "json2md": (_EXAMPLES_PACKAGE,),
    "obj_to_file": (_EXAMPLES_PACKAGE,),
    "render_example": (_EXAMPLES_PACKAGE,),
}


def _wrapper_reaches() -> dict[str, set[str]]:
    """Each module under ``vultron/`` outside a wrapper's home that reaches it."""
    names = frozenset(_SIGNING_WRAPPERS)
    reaches: dict[str, set[str]] = {}
    for path, tree in _corpus.files_mentioning(
        *names, under=_corpus.REPO_ROOT / "vultron"
    ):
        rel = str(path.relative_to(_corpus.REPO_ROOT))
        outside = {
            name
            for name in _references(tree, names)
            if not rel.startswith(_SIGNING_WRAPPERS[name])
        }
        if outside:
            reaches[rel] = outside
    return reaches


@pytest.mark.parametrize(
    "source",
    [
        "from vultron.wire.as2 import signing\nsigning.sign_as_author(d)\n",
        "from vultron.wire.as2 import signing as s\ns.sign(d, k)\n",
        "import vultron.wire.as2.signing\nvultron.wire.as2.signing.sign(d, k)\n",
        "from vultron.wire.as2.signing import sign_docs_example as x\n",
        "from vultron.wire.as2 import signing\nf = signing.sign\n",
        "from vultron.wire.as2 import signing\ngetattr(signing, 'sign')(d, k)\n",
        "from vultron.wire.as2.signing import *\n",
        "from vultron.wire import as2\nas2.signing.sign_as_author(d)\n",
        "import vultron.wire.as2 as w\nw.signing.sign(d, k)\n",
    ],
)
def test_the_scan_sees_each_call_form(source: str):
    """The scan finds every form, so a pass is not vacuous."""
    assert _called(_corpus.parse_inline(source), _PROOF_MAKERS)


def test_the_scan_ignores_other_calls():
    tree = _corpus.parse_inline(
        "from vultron.wire.as2 import signing\nsigning.verify(d, k)\n"
        "key.sign(b'x')\n"
    )
    assert not _called(tree, _PROOF_MAKERS)


@pytest.mark.spec("SIG-05-004")
def test_only_the_outbox_and_the_example_renderers_sign():
    assert _callers(_PROOF_MAKERS) == _ALLOWED_SIGNERS


@pytest.mark.spec("SIG-05-004")
def test_only_the_profile_route_computes_a_seeded_key():
    assert _callers(frozenset({_KEY_DERIVER})) == _ALLOWED_KEY_DERIVERS


@pytest.mark.parametrize(
    "source",
    [
        "from vultron.adapters.outbox_sealed_body import signed_outbound_body\n",
        "from vultron.adapters import outbox_sealed_body as o\n"
        "o.signed_outbound_body(a, x)\n",
        "from vultron.wire.as2.vocab.examples.vocab_examples import json2md\n",
        "from vultron.wire.as2.vocab.examples import _base\nf = _base._example_json\n",
    ],
)
def test_the_wrapper_scan_sees_each_form(source: str):
    """The wrapper scan finds every form, so a pass is not vacuous."""
    assert _references(
        _corpus.parse_inline(source), frozenset(_SIGNING_WRAPPERS)
    )


@pytest.mark.spec("SIG-05-004")
def test_no_module_wraps_an_allowed_signer():
    """Only the signers' own homes reach the functions that sign as any actor."""
    assert _wrapper_reaches() == {}
