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

"""Ratchet: application code must not construct ``httpx.ASGITransport`` directly.

ADR-0042 (OX-12-003): all inter-actor communication is delivered over HTTP.
``httpx.ASGITransport`` (used by the retired ``ASGIEmitter``) MUST NOT appear
in any application module.  The only sanctioned use is FastAPI's
``TestClient``, which uses it internally as a single-app test tool — not as an
inter-actor delivery mechanism.
"""

import ast

from test.architecture import _corpus

#: Modules that are permitted to reference ASGITransport.
#: FastAPI's TestClient wraps ASGITransport internally, so the test infra
#: helpers that use TestClient must be allowed.
_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        # FastAPI TestClient uses ASGITransport internally; test helpers that
        # use TestClient directly are fine — they do not instantiate ASGITransport
        # themselves. The conftest imports TestClient but never ASGITransport.
    }
)

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"


def _contains_asgi_transport(tree: ast.AST) -> list[int]:
    """Return line numbers in *tree* that reference ASGITransport."""
    violations: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "ASGITransport":
            violations.append(node.lineno)
        elif isinstance(node, ast.Name) and node.id == "ASGITransport":
            violations.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and isinstance(node.names, list):
            for alias in node.names:
                if alias.name == "ASGITransport":
                    violations.append(node.lineno)
    return violations


def test_no_asgi_transport_in_application_code():
    """vultron/ must not reference httpx.ASGITransport (OX-12-003)."""
    found: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        "ASGITransport", under=_VULTRON_ROOT
    ):
        rel = py_file.relative_to(_corpus.REPO_ROOT)
        module_key = str(rel)
        if module_key in _ALLOWED_MODULES:
            continue
        lines = _contains_asgi_transport(tree)
        for lineno in lines:
            found.append(f"  {rel}:{lineno}")

    assert not found, (
        "Application modules MUST NOT construct httpx.ASGITransport directly "
        "(ADR-0042, OX-12-003). Found violations:\n"
        + "\n".join(found)
        + "\n\nThe only permitted use of ASGITransport is inside FastAPI's "
        "TestClient, which is a single-app test tool — not an inter-actor "
        "delivery mechanism. Use HttpDeliveryAdapter for inter-actor delivery."
    )


def test_no_asgi_emitter_references_in_application_code():
    """vultron/ must not import or reference ASGIEmitter (OX-12-002)."""
    found: list[str] = []
    for py_file, source in _corpus.sources_mentioning(
        "ASGIEmitter", under=_VULTRON_ROOT
    ):
        rel = py_file.relative_to(_corpus.REPO_ROOT)
        for i, line in enumerate(source.splitlines(), start=1):
            if "ASGIEmitter" in line:
                found.append(f"  {rel}:{i}: {line.strip()}")

    assert not found, (
        "ASGIEmitter has been retired (ADR-0042, OX-12-002). "
        "Application modules must not reference it. Found:\n"
        + "\n".join(found)
    )
