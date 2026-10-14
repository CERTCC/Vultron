#!/usr/bin/env python

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
"""Ratchet: every ``setup_ports(...)`` call names the port-wiring logger.

py_trees logs one DEBUG line per port as a typed-ports node registers its
blackboard keys, to whatever logger ``setup_ports`` is handed — the node's own
when none is.  Those lines restate the node class's declared ports on every
tree build and were over half of each container's DEBUG output in the CI
demos (#4600), so Vultron nodes pass
:func:`vultron.core.behaviors.node_logger.port_wiring_logger`, which the entry
points keep at INFO.  A new node that omits it brings the lines back.
"""

import ast

from test.architecture import _corpus

_PACKAGE_ROOT = _corpus.REPO_ROOT / "vultron"


def _setup_ports_calls() -> list[tuple[str, ast.Call]]:
    calls = []
    for path, tree in _corpus.files_mentioning(
        "setup_ports", under=_PACKAGE_ROOT
    ):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setup_ports"
            ):
                calls.append((f"{path}:{node.lineno}", node))
    return calls


def _passes_port_wiring_logger(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "logger":
            continue
        value = keyword.value
        return (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "port_wiring_logger"
        )
    return False


def test_the_scan_finds_setup_ports_calls():
    """A scan that finds nothing would pass vacuously."""
    assert _setup_ports_calls()


def test_every_setup_ports_call_passes_the_port_wiring_logger():
    offenders = [
        where
        for where, call in _setup_ports_calls()
        if not _passes_port_wiring_logger(call)
    ]
    assert not offenders, (
        "setup_ports() must be passed logger=port_wiring_logger() (#4600): "
        + ", ".join(offenders)
    )


def test_a_call_without_the_logger_is_caught():
    call = _corpus.parse_inline("self.setup_ports(port_remappings={})")
    node = next(n for n in ast.walk(call) if isinstance(n, ast.Call))
    assert not _passes_port_wiring_logger(node)
