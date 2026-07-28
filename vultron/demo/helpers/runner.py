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

"""Demo runner helpers shared across exchange demos.

Provides :func:`run_exchange_demos` for the standard ``main()`` loop used
by every exchange demo module, and :func:`check_all_containers` for
multi-container health checks used by scenario demos.
"""

import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

from vultron.demo.utils import (
    DataLayerClient,
    check_server_availability,
    demo_environment,
)

logger = logging.getLogger(__name__)


def run_exchange_demos(
    all_demos: Sequence[Tuple[str, Callable]],
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """Run an exchange demo module's demo suite.

    This is the standard ``main()`` body shared by all exchange demo modules.
    It performs a health check (unless skipped), iterates over the selected
    demo functions inside a fresh :func:`~vultron.demo.utils.demo_environment`
    context for each demo, accumulates errors, and logs a summary.

    Each demo callable must accept
    ``(client, finder, vendor, coordinator)`` as positional arguments.

    Args:
        all_demos: Sequence of ``(name, callable)`` pairs — the module-level
            ``_ALL_DEMOS`` list.
        skip_health_check: When ``True``, skip the server availability check.
            Useful in integration tests where the server is already known
            to be running.
        demos: Optional subset of demo *callables* to run.  When provided,
            only entries whose callable appears in this sequence are executed.
            When ``None``, all entries in *all_demos* are run.
    """
    client = DataLayerClient()

    if not skip_health_check and not check_server_availability(client):
        logger.error("=" * 80)
        logger.error("ERROR: API server is not available")
        logger.error("=" * 80)
        logger.error("Cannot connect to: %s", client.base_url)
        logger.error("")
        logger.error("Please ensure the Vultron API server is running:")
        logger.error(
            "  uv run uvicorn vultron.api.main:app --host localhost --port 7999"
        )
        logger.error("=" * 80)
        sys.exit(1)

    selected = (
        all_demos
        if demos is None
        else [(name, fn) for name, fn in all_demos if fn in demos]
    )
    total = len(selected)
    errors = []

    for demo_name, demo_fn in selected:
        try:
            with demo_environment(client) as (finder, vendor, coordinator):
                demo_fn(client, finder, vendor, coordinator)
        except Exception as e:
            logger.error("%s failed: %s", demo_name, e, exc_info=True)
            errors.append((demo_name, str(e)))

    logger.info("=" * 80)
    logger.info("ALL DEMOS COMPLETE")
    logger.info("=" * 80)

    if errors:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error("Total demos: %d", total)
        logger.error("Failed demos: %d", len(errors))
        logger.error("Successful demos: %d", total - len(errors))
        logger.error("")
        for demo_name, error in errors:
            logger.error("%s:", demo_name)
            logger.error("  %s", error)
            logger.error("")
        logger.error("=" * 80)
    else:
        logger.info("")
        logger.info("✓ All %d demos completed successfully!", total)
        logger.info("")


def check_all_containers(
    labeled_clients: Sequence[Tuple[str, DataLayerClient]],
) -> None:
    """Check availability of all containers, exiting with status 1 on failure.

    Args:
        labeled_clients: Sequence of ``(label, client)`` pairs.  *label* is
            used only in error messages; *client* provides the ``base_url``
            to health-check.

    Raises:
        SystemExit: If any container is not reachable.
    """
    for label, client in labeled_clients:
        if not check_server_availability(client):
            logger.error(
                "Container '%s' is not reachable at %s",
                label,
                client.base_url,
            )
            sys.exit(1)
