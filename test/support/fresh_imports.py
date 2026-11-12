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

"""Ask a fresh interpreter which packages an import loads.

An import guard that reads a module's own ``import`` statements misses what
those imports load in turn; ``sys.modules`` in an interpreter that has
imported nothing else does not.  The import guards that must count indirect
loads (CEH-05-008, #6328) share this one probe.
"""

import json
import subprocess
import sys
from collections.abc import Iterable


def loaded_under(imports: Iterable[str], packages: Iterable[str]) -> list[str]:
    """Return every module under *packages* loaded by importing *imports*.

    Args:
        imports: the modules to import, in order, in a new interpreter
        packages: the package names to look for; a package counts as loaded
            when it or any of its submodules is in ``sys.modules``

    Returns:
        the sorted names of the loaded modules under *packages*; empty when
        none was loaded
    """
    imports = list(imports)
    packages = list(packages)
    if not imports or not packages:
        raise ValueError("loaded_under needs at least one import and package")
    probe = (
        "import json, sys\n"
        + "".join(f"import {name}\n" for name in imports)
        + f"packages = {packages!r}\n"
        + "print(json.dumps(sorted(m for m in sys.modules if any("
        + "m == p or m.startswith(p + '.') for p in packages))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    loaded: list[str] = json.loads(out)
    return loaded
