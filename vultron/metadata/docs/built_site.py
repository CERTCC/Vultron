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
"""The built ``site/`` tree, shared by the checks that read the build product.

``docs-withheld``, ``docs-links`` and ``docs-legacy-urls`` judge what
``mkdocs build`` produced rather than the ``docs/`` sources. Each must refuse an
absent or empty ``site/``: an unbuilt site evidences nothing, so a check that ran against one and
reported success would pass while checking nothing (DF-09-009).
"""

from __future__ import annotations

from pathlib import Path

from vultron.metadata.base import repo_root


def site_dir(root: Path | None = None) -> Path:
    """Return the built site directory."""
    return (root or repo_root()) / "site"


def require_built_site(root: Path | None, claim: str) -> Path:
    """Return the built site directory, or raise if the build left nothing.

    Args:
        root: Repository root. Defaults to the enclosing checkout.
        claim: What the caller sets out to show, completing "An unbuilt site
            cannot show that ..." in the error.

    Raises:
        FileNotFoundError: If ``site/`` is absent or empty.
    """
    built = site_dir(root)
    if not built.is_dir() or not any(built.iterdir()):
        raise FileNotFoundError(
            f"{built} is absent or empty — run 'uv run mkdocs build' first. "
            f"An unbuilt site cannot show that {claim}."
        )
    return built
