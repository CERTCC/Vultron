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
"""Every proof goes through one shared signing module (SIG-05-003, ADR-0164).

The module that creates and verifies proofs is the only one that imports the
Ed25519 or JCS primitives; everything else, tests included, calls it.  The
signing module does not exist yet, so the test is a strict ``xfail`` until
#5380 adds it.
"""

import ast

import pytest

from test.architecture import _corpus

#: The libraries whose signature and canonicalization primitives only the
#: signing module may call.
_PRIMITIVES = (
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "rfc8785",
)


def _imports_a_primitive(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
            names += [f"{node.module}.{alias.name}" for alias in node.names]
        else:
            continue
        if any(
            name == primitive or name.startswith(f"{primitive}.")
            for name in names
            for primitive in _PRIMITIVES
        ):
            return True
    return False


def _modules_calling_primitives() -> list[str]:
    return sorted(
        str(path.relative_to(_corpus.REPO_ROOT))
        for top in ("vultron", "test")
        for path, tree in _corpus.files_mentioning(
            "ed25519", "rfc8785", under=_corpus.REPO_ROOT / top
        )
        if _imports_a_primitive(tree)
    )


def test_the_scan_sees_a_primitive_import():
    """The scan finds both import forms, so an empty result is not vacuous."""
    assert _imports_a_primitive(_corpus.parse_inline("import rfc8785\n"))
    assert _imports_a_primitive(
        _corpus.parse_inline(
            "from cryptography.hazmat.primitives.asymmetric import ed25519\n"
        )
    )
    assert not _imports_a_primitive(_corpus.parse_inline("import json\n"))


@pytest.mark.xfail(
    strict=True,
    reason="SIG-05-003: there is no signing module yet. Tracked by #5380.",
)
@pytest.mark.spec("SIG-05-003")
def test_one_module_calls_the_signing_primitives():
    modules = _modules_calling_primitives()

    assert len(modules) == 1, modules
