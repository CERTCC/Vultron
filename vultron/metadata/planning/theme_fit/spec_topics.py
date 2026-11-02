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
"""The spec topic prefixes an Epic title's bare group ID is checked against.

Its own module, not :mod:`.gate`, because ``theme-fit``'s CLI needs it too and
``create_epic.sh`` runs :mod:`.gate` as ``__main__``: importing the gate from
the package would load it twice.
"""

from __future__ import annotations

import re
from pathlib import Path

from vultron.metadata.base import repo_root

_TOPIC_LINE = re.compile(r"^id:\s*(?P<topic>[A-Z][A-Z0-9]*)\s*$", re.MULTILINE)


def load_spec_topics(specs_dir: Path | None = None) -> frozenset[str]:
    """The topic prefix each spec file declares in its top-level ``id:``.

    An Epic title's bare group ID (``SYNC-19``) is an ID only when its prefix
    is one of these (PAD-02-032).

    Args:
        specs_dir: The spec directory; defaults to the repository's ``specs/``.

    Raises:
        FileNotFoundError: If the directory holds no spec file declaring one.
        OSError, UnicodeDecodeError: If a spec file cannot be read.
    """
    folder = specs_dir if specs_dir is not None else repo_root() / "specs"
    topics = frozenset(
        match["topic"]
        for path in sorted(folder.glob("*.yaml"))
        if (match := _TOPIC_LINE.search(path.read_text(encoding="utf-8")))
    )
    if not topics:
        raise FileNotFoundError(f"no spec topics found in {folder}")
    return topics
