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

It also holds the participant's ledger position statement interval
(``specs/sync-ledger-replication.yaml`` SYNC-17-007) and the CASE_MANAGER's
unanswered-Invite resend cooldown (SYNC-20-005, SYNC-20-006).
"""

from datetime import timedelta

from pydantic import BaseModel, Field, model_validator


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
        position_statement_interval_seconds: How often a hosted participant
            states its ledger position for each case it holds, with
            ``Read(CaseLedgerEntry)``, beyond the statement it sends after
            every restart (SYNC-17-007).  Off (``None``) by default, because
            a periodic check costs traffic a deployment should choose.
            Override via
            ``VULTRON_LEDGER__POSITION_STATEMENT_INTERVAL_SECONDS``.
        invite_resend_cooldown_seconds: The base cooldown between two resends
            of one unanswered Invite to one participant (SYNC-20-005).  Each
            consecutive resend doubles it.  Default 30 s, the base of the
            ledger replay cooldown (SYNC-15-013).  Override via
            ``VULTRON_LEDGER__INVITE_RESEND_COOLDOWN_SECONDS``.
        invite_resend_max_cooldown_seconds: The ceiling the doubled resend
            cooldown stops at, so an unanswered Invite is still resent at a
            fixed interval until its deadline (SYNC-20-005).  Default 600 s,
            the replay cooldown's ceiling.  Override via
            ``VULTRON_LEDGER__INVITE_RESEND_MAX_COOLDOWN_SECONDS``.
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

    position_statement_interval_seconds: int | None = Field(
        default=None,
        ge=1,
        description=(
            "SYNC-17-007 interval at which each hosted participant states its "
            "ledger position to each case's CASE_MANAGER with "
            "Read(CaseLedgerEntry), after the statement every restart sends. "
            "Default: None (off)."
        ),
    )
    invite_resend_cooldown_seconds: float = Field(
        default=30.0,
        gt=0,
        description=(
            "SYNC-20-005 base cooldown between two resends of one unanswered "
            "Invite to one participant; each consecutive resend doubles it. "
            "Default: 30 s."
        ),
    )
    invite_resend_max_cooldown_seconds: float = Field(
        default=600.0,
        gt=0,
        description=(
            "SYNC-20-005 ceiling on the doubled resend cooldown. Default: 600 s."
        ),
    )

    @model_validator(mode="after")
    def _resend_ceiling_not_below_base(self) -> "LedgerConfig":
        """Refuse a resend ceiling below its base: the cooldown only grows."""
        if (
            self.invite_resend_max_cooldown_seconds
            < self.invite_resend_cooldown_seconds
        ):
            raise ValueError(
                "invite_resend_max_cooldown_seconds must not be below"
                " invite_resend_cooldown_seconds (SYNC-20-005)"
            )
        return self

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
