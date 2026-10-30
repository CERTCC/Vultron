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

"""The environment for a child Python process that imports this checkout.

pytest puts the repository root first on its own ``sys.path``
(``pythonpath = ["."]``), but a child interpreter only inherits ``PYTHONPATH``.
In a worktree that variable can name another checkout, and its ``vultron``
then shadows this one's: a script child's first ``sys.path`` entry is the
script's directory, and a console script's is the venv's ``bin/``, so the
inherited path wins over the editable install (#5456).  :func:`child_env`
puts this checkout's root first, as pytest does for the parent.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def child_env(*extra_paths: Path) -> dict[str, str]:
    """A copy of ``os.environ`` whose ``PYTHONPATH`` starts at this checkout.

    *extra_paths* follow the repository root, then whatever ``PYTHONPATH`` the
    parent inherited, so an import resolves to this checkout's ``vultron`` and
    only falls through to the inherited path for packages this one lacks.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p
        for p in (
            str(REPO_ROOT),
            *(str(path) for path in extra_paths),
            env.get("PYTHONPATH", ""),
        )
        if p
    )
    return env
