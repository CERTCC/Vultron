#!/usr/bin/env python
"""Regression: ``inbox_orchestration`` imports first without a cycle (#3705).

``inbox_orchestration`` used to import its storage helpers from the router
package, which imports ``inbox_orchestration`` back for ``run_inbox_pipeline``.
Whichever module a process imported first decided whether the import worked,
so the check runs in a fresh interpreter: inside the pytest session some
earlier test has already imported both modules and would hide the cycle.
"""

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

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "vultron.adapters.driving.fastapi.inbox_orchestration",
        "vultron.adapters.driving.fastapi.inbox_storage",
    ],
)
def test_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
