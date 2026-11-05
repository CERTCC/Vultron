#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The two trigger route families, and the app that mounts both.

Shared by every gate that asks a question of the mounted trigger surface — the
route-to-registry bijection, the response-key contract, the scenario-tree
coverage check — so none of them can disagree about which paths are trigger
routes or about how the app under test is built.
"""

from __future__ import annotations

from fastapi import FastAPI

from vultron.adapters.driving.fastapi.app import create_app
from vultron.config import config_override

#: Path fragments that select the two trigger route families (TRIG-01-001,
#: TRIG-09-001).  Matched as substrings so the ``/api/v2`` mount prefix does
#: not have to be repeated at every call site.
TRIGGER_PATH_FRAGMENT = "/actors/{actor_id}/trigger/"
DEMO_PATH_FRAGMENT = "/actors/{actor_id}/demo/"
TRIGGER_FAMILY_FRAGMENTS = (TRIGGER_PATH_FRAGMENT, DEMO_PATH_FRAGMENT)


def is_trigger_family_path(path: str) -> bool:
    """True when ``path`` belongs to one of the two trigger route families."""
    return any(fragment in path for fragment in TRIGGER_FAMILY_FRAGMENTS)


def build_prototype_app() -> FastAPI:
    """Build an isolated app with the demo router mounted (TRIG-09-001).

    Forces ``mode=PROTOTYPE`` for the duration of construction so the
    result does not depend on the caller's environment; ``config_override``
    restores the config cache on exit (CFG-06-006).
    """
    with config_override(VULTRON_MODE="prototype"):
        return create_app(docs_url=None, openapi_url=None)
