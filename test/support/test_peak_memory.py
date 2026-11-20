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

"""The module memory budget guard of #6727 fails over its budget, not under it.

The peak is read through a stub: a real allocation can only raise a worker's
peak when it exceeds what an earlier test there already reached, so it would
test the worker's history, not the guard.
"""

from collections.abc import Iterator

import pytest

from test.support import peak_memory
from test.support.peak_memory import peak_rss_growth_within, peak_rss_mib


def _peaks(monkeypatch: pytest.MonkeyPatch, *readings: float) -> None:
    it: Iterator[float] = iter(readings)
    monkeypatch.setattr(peak_memory, "peak_rss_mib", lambda: next(it))


def test_growth_within_the_budget_passes(monkeypatch) -> None:
    _peaks(monkeypatch, 700.0, 900.0)
    with peak_rss_growth_within(200, "a module"):
        pass


def test_growth_over_the_budget_fails_naming_the_block(monkeypatch) -> None:
    _peaks(monkeypatch, 700.0, 901.0)
    with pytest.raises(
        AssertionError,
        match=r"a module raised the process's peak memory by 201 MiB, over "
        r"its 200 MiB budget",
    ):
        with peak_rss_growth_within(200, "a module"):
            pass


def test_the_peak_reads_this_process_in_mib() -> None:
    """A Linux or macOS process of this size is tens to thousands of MiB."""
    assert 10 < peak_rss_mib() < 100_000
