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

"""Build an app's own ``AppConfig`` and keep its hold from leaking (ADR-0206).

``AppConfig(...)`` keyword arguments are not a settings source, so an app's
own config is a copy of the loaded one with its values changed
(:func:`own_app_config`).  While an app holding its own config runs, a read in
no app scope raises for the whole process, so a test that leaves one running
is caught by :func:`release_leaked_app_config_holds`.
"""

from typing import Any

from vultron.config import AppConfig, app as app_config


def own_app_config(**updates: Any) -> AppConfig:
    """Return the loaded process-wide config with *updates* applied."""
    return AppConfig().model_copy(update=updates)


def held_app_config_count() -> int:
    """How many apps holding their own config are running in this process."""
    return app_config._HELD_APP_CONFIGS.count


def release_leaked_app_config_holds(before: int) -> int:
    """Put the held count back to *before* and return how many had leaked.

    Args:
        before: :func:`held_app_config_count` at the start of the test.

    Returns:
        The number of holds the test left running, ``0`` when none.
    """
    leaked = held_app_config_count() - before
    if leaked > 0:
        app_config._HELD_APP_CONFIGS.add(-leaked)
        return leaked
    return 0
