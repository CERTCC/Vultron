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

from pathlib import Path

from vultron.metadata.specs.registry import load_registry


def load_spec_topics(specs_dir: Path | None = None) -> frozenset[str]:
    """The topic prefix each spec file declares in its top-level ``id:``.

    An Epic title's bare group ID (``SYNC-19``) is an ID only when its prefix
    is one of these (PAD-02-032). Read through :func:`.registry.load_registry`,
    as ``build-context`` reads them, so the two never disagree on the topics.

    Args:
        specs_dir: The spec directory; defaults to the repository's ``specs/``.

    Raises:
        MetadataLoadErrors: If a spec file fails to parse or validate.
        FileNotFoundError: If the directory holds no spec file.
    """
    topics = frozenset(f.id for f in load_registry(specs_dir).files)
    if not topics:
        folder = specs_dir if specs_dir is not None else "specs/"
        raise FileNotFoundError(f"no spec topics found in {folder}")
    return topics
