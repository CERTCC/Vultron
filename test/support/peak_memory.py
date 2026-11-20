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

"""Bound how far a test module raises its process's peak memory (#6727).

A worker's peak resident set is what the kernel's memory killer weighs, and
an in-process demo module that grows it per test is the worker a loaded gate
loses.  :func:`peak_rss_growth_within` fails the module when the process's
peak grows by more than a fixed budget while the module runs.

The measure is the rise of ``ru_maxrss``, the process's peak so far, over the
module.  It never reads high: a module that allocates nothing raises nothing.
It can read low, when an earlier module in the same worker already set a
higher peak, so it is exact in a single-file run and a lower bound in a
shared worker.
"""

import resource
import sys
from collections.abc import Iterator
from contextlib import contextmanager

#: ``ru_maxrss`` is in KiB on Linux and in bytes on macOS.
_MAXRSS_UNIT = 1 if sys.platform == "darwin" else 1024


def peak_rss_mib() -> float:
    """This process's peak resident set so far, in MiB."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak * _MAXRSS_UNIT / (1024 * 1024)


@contextmanager
def peak_rss_growth_within(budget_mib: float, what: str) -> Iterator[None]:
    """Fail if the process's peak grows by more than *budget_mib* in the block.

    Args:
        budget_mib: The most the peak may rise, in MiB.
        what: Names the block in the failure message.

    Raises:
        AssertionError: when the peak rose by more than *budget_mib*.
    """
    start = peak_rss_mib()
    yield
    growth = peak_rss_mib() - start
    assert growth <= budget_mib, (
        f"{what} raised the process's peak memory by {growth:.0f} MiB, over "
        f"its {budget_mib:.0f} MiB budget (#6727): something it runs holds "
        "memory past the test that built it"
    )
