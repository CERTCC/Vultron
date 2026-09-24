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

"""Case-ledger timestamp-tolerance configuration.

Provides :class:`LedgerConfig`, which exposes the CLP-14 timestamp thresholds
the CaseActor applies at its commit boundary so a deployment with known clock
conditions can tune them (CLP-14-009).

Thresholds are stored as plain integers because they are set from the
environment (``VULTRON_LEDGER__CLOCK_SKEW_TOLERANCE_SECONDS`` and friends);
the ``timedelta`` properties are what the commit-boundary guard consumes.

Per ``specs/case-ledger-processing.yaml`` CLP-14-007, CLP-14-008, CLP-14-009.
"""

from datetime import timedelta

from pydantic import BaseModel, Field


class LedgerConfig(BaseModel):
    """Deployment-tunable CLP-14 timestamp tolerances.

    Attributes:
        clock_skew_tolerance_seconds: How far *before* the parent case's own
            ``published`` timestamp an assertion's claimed timestamp may fall
            before CLP-14-006 rejects it.  A non-zero tolerance is required
            because participant and CaseActor clocks are not synchronised —
            ADR-0079 rejected wall-clock ordering (option C) for exactly this
            reason.  Default 300 s (5 minutes), matching the CLP-14-007
            convention.
        future_tolerance_seconds: How far *ahead* of the CaseActor's own clock
            an assertion's claimed timestamp may fall before CLP-14-007
            rejects it.  CLP-14-007 sets the default ceiling at five minutes.
        staleness_window_days: How far *behind* the CaseActor's own clock an
            assertion's claimed timestamp may fall before CLP-14-008 rejects
            it.  CLP-14-008 sets the default at seven days.
    """

    clock_skew_tolerance_seconds: int = Field(
        default=300,
        ge=0,
        description=(
            "Tolerance applied to the CLP-14-006 check that an assertion is "
            "not stamped before its parent case was created. Default: 300 s."
        ),
    )
    future_tolerance_seconds: int = Field(
        default=300,
        ge=0,
        description=(
            "CLP-14-007 ceiling on how far ahead of the CaseActor's clock a "
            "claimed timestamp may be. Default: 300 s (5 minutes)."
        ),
    )
    staleness_window_days: int = Field(
        default=7,
        ge=0,
        description=(
            "CLP-14-008 window on how far behind the CaseActor's clock a "
            "claimed timestamp may be. Default: 7 days."
        ),
    )

    @property
    def clock_skew_tolerance(self) -> timedelta:
        """CLP-14-006 skew tolerance as a :class:`~datetime.timedelta`."""
        return timedelta(seconds=self.clock_skew_tolerance_seconds)

    @property
    def future_tolerance(self) -> timedelta:
        """CLP-14-007 future ceiling as a :class:`~datetime.timedelta`."""
        return timedelta(seconds=self.future_tolerance_seconds)

    @property
    def staleness_window(self) -> timedelta:
        """CLP-14-008 staleness window as a :class:`~datetime.timedelta`."""
        return timedelta(days=self.staleness_window_days)
