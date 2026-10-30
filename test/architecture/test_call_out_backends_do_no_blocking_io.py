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
"""In-repo call-out backends perform no blocking I/O (BT-18-025).

A call-out point answers within one tick (BT-18-011), so its backend must not
block on a network call, a subprocess, a file read, a sleep or a prompt. The
deterministic backends live in ``vultron/core/behaviors/call_out/`` and the
probabilistic ones in ``vultron/demo/fuzzer/`` (BT-16-001). Neither package may
import a blocking-I/O module or call a blocking builtin.

A backend injected from outside the repository (BT-23-004) is out of this
scan's reach; the seam's runtime guard covers what it can see of it.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_BACKEND_ROOTS = (
    _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "call_out",
    _corpus.REPO_ROOT / "vultron" / "demo" / "fuzzer",
)

#: Modules whose import means a backend can block on I/O.
_BLOCKING_MODULES = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "subprocess",
        "urllib",
        "urllib3",
    }
)

#: Calls that block: a sleep, a file open or an interactive prompt.
_BLOCKING_CALLS = frozenset({"input", "open", "sleep"})


def _violations(path: Path, tree: ast.AST) -> list[str]:
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    found: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            if name.split(".")[0] in _BLOCKING_MODULES:
                found.append(f"{rel}:{_corpus.node_line(node)} imports {name}")
        if isinstance(node, ast.Call):
            callee = _corpus.callee_name(node.func)
            if callee in _BLOCKING_CALLS:
                found.append(
                    f"{rel}:{_corpus.node_line(node)} calls {callee}()"
                )
    return found


@pytest.mark.spec("BT-18-025")
def test_in_repo_call_out_backends_do_no_blocking_io() -> None:
    violations = [
        violation
        for root in _BACKEND_ROOTS
        for path, tree in _corpus.all_trees(root)
        for violation in _violations(path, tree)
    ]
    assert not violations, (
        "a call-out backend must not block on I/O (BT-18-025):\n"
        + "\n".join(violations)
    )


@pytest.mark.parametrize(
    "source",
    [
        "import requests\n",
        "from urllib.request import urlopen\n",
        "import time\ntime.sleep(1)\n",
        "open('x')\n",
    ],
)
def test_detector_catches_blocking_io(source: str) -> None:
    tree = _corpus.parse_inline(source)
    assert _violations(_BACKEND_ROOTS[0] / "x.py", tree)
