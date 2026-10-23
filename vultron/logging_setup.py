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

"""Shared third-party log-noise suppression (SL-04-007).

Some libraries Vultron depends on emit high-volume lifecycle chatter at INFO.
Those lines are infrastructure internals, not protocol story, so they MUST NOT
appear at INFO (SL-04-007).  This module centralises the suppression so that
both the FastAPI server (:func:`vultron.adapters.driving.fastapi.app.configure_logging`)
and the demo CLI apply the same policy.

The same entry points also keep Vultron's own static-wiring loggers at INFO when
the application runs at DEBUG: their DEBUG output restates code, not run-time
state (:data:`STATIC_WIRING_LOGGERS`).

See ``notes/structured-logging.md``.
"""

import logging

from vultron.core.behaviors.node_logger import PORT_WIRING_LOGGER_NAME

#: Loggers whose INFO output is library internals rather than protocol story.
#:
#: ``transitions`` emits ``"<Machine> Finished processing state X enter/exit
#: callbacks."`` and ``"Executed callback '<func>'"`` at INFO for every RM/EM/
#: CS/PEC state machine step.  The narrative EM/RM transition messages Vultron
#: emits itself already carry that information (SL-04-006).
NOISY_INFO_LOGGERS: tuple[str, ...] = ("transitions",)

#: Loggers whose DEBUG output restates code rather than run-time state, kept at
#: INFO even when the application runs at DEBUG.
#:
#: The port-wiring logger receives py_trees' one-line-per-port registration
#: record from every typed-ports node on every tree build: over half of each
#: container's DEBUG output in the CI demos, identical on every build of the
#: same node class (#4600).  To see the wiring, set it to DEBUG after the entry
#: point has run: this pinning overwrites any earlier level.
STATIC_WIRING_LOGGERS: tuple[str, ...] = (PORT_WIRING_LOGGER_NAME,)


#: Levels captured the first time :func:`suppress_third_party_info_noise` runs,
#: so :func:`restore_third_party_log_levels` can undo the global mutation.
_SAVED_LEVELS: dict[str, int] = {}


def suppress_third_party_info_noise(app_log_level: int) -> None:
    """Raise noisy third-party loggers above INFO (SL-04-007).

    Also pins :data:`STATIC_WIRING_LOGGERS` at INFO (or at *app_log_level* when
    that is higher), so a DEBUG run keeps run-time state and drops wiring.

    When *app_log_level* is above ``DEBUG`` the noisy loggers are pinned to
    ``WARNING`` so their INFO chatter is dropped.  When the application is
    running at ``DEBUG`` the loggers are set to ``DEBUG`` so their output is
    still available for troubleshooting.

    This mutates process-global logger state, which is appropriate for an
    application entry point (the server lifespan, the demo CLI) but would be
    rude if it were permanent for library importers and leaks across tests.
    The pre-existing levels are captured on first call so
    :func:`restore_third_party_log_levels` can undo it.

    Args:
        app_log_level: The effective application log level (e.g.
            ``logging.INFO``).
    """
    library_level = (
        logging.DEBUG if app_log_level <= logging.DEBUG else logging.WARNING
    )
    _set_levels(NOISY_INFO_LOGGERS, library_level)
    # Never below INFO, and never above the app level: an app at WARNING must
    # not gain INFO records from a logger pinned here.
    _set_levels(STATIC_WIRING_LOGGERS, max(app_log_level, logging.INFO))


def _set_levels(names: tuple[str, ...], level: int) -> None:
    """Set each named logger to *level*, saving its prior level once."""
    for name in names:
        named_logger = logging.getLogger(name)
        _SAVED_LEVELS.setdefault(name, named_logger.level)
        named_logger.setLevel(level)


def restore_third_party_log_levels() -> None:
    """Undo :func:`suppress_third_party_info_noise`.

    Restores each noisy logger to the level it had before the first
    suppression call.  Safe to call when no suppression is active (no-op).
    """
    while _SAVED_LEVELS:
        name, level = _SAVED_LEVELS.popitem()
        logging.getLogger(name).setLevel(level)
