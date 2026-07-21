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

"""Lifecycle-staged VulnerabilityCase domain types.

Implements ADR-0033: field-set-anchored staged types for VulnerabilityCase.
Each staged type adds ``model_validator`` logic that enforces its lifecycle
invariants.  All three types share ``type_="VulnerabilityCase"`` (inherited from
the base class and not redeclared here) so they:

- Round-trip through the DataLayer as the base type (LST-05-003).
- Do **not** register separately in ``CORE_VOCABULARY`` — only the base class
  is registered (per the ``__init_subclass__`` guard in
  :class:`~vultron.core.models.base.CoreObject`).

The canonical usage pattern is read-boundary promotion (ADR-0032, LST-05-001):

.. code-block:: python

    vc = dl.read(case_id)                           # returns VulnerabilityCase
    embargoed = EmbargoedCase.model_validate(vc)    # raises if no active embargo

Spec: ``specs/lifecycle-staged-types.yaml`` LST-02, LST-05.
ADR: ``docs/adr/0033-lifecycle-staged-case-types.md``.
Notes: ``notes/lifecycle-staged-types.md``.
"""

from __future__ import annotations

from pydantic import ConfigDict, model_validator

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.states.em import EM
from vultron.errors import VultronValidationError


class IncomingReport(VulnerabilityCase):
    """Pre-case stage: report data present, no case participants assigned yet.

    Guarantees:

    - At least one entry in ``vulnerability_reports``.
    - ``case_participants`` is empty (no case bootstrap has run).

    Shared ``type_="VulnerabilityCase"`` (inherited, not redeclared) ensures
    DataLayer round-trip compatibility.

    Spec: LST-02-001.
    """

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _check_incoming_report_invariants(self) -> "IncomingReport":
        if not self.vulnerability_reports:
            raise VultronValidationError(
                "IncomingReport requires at least one vulnerability report "
                "(LST-02-001)."
            )
        if self.case_participants:
            raise VultronValidationError(
                "IncomingReport must not have case participants — "
                "no case assignment yet (LST-02-001)."
            )
        return self


class Case(VulnerabilityCase):
    """Bootstrapped case stage: case exists with participants and status history.

    Guarantees:

    - At least one entry in ``vulnerability_reports``.
    - At least two ``case_participants`` (reporter and receiver).
    - ``case_statuses`` is non-empty (seeded at bootstrap).

    Shared ``type_="VulnerabilityCase"`` (inherited, not redeclared) ensures
    DataLayer round-trip compatibility.

    Spec: LST-02-001, LST-02-002.
    """

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _check_case_invariants(self) -> "Case":
        if not self.vulnerability_reports:
            raise VultronValidationError(
                "Case requires at least one vulnerability report (LST-02-002)."
            )
        n = len(self.case_participants)
        if n < 2:
            raise VultronValidationError(
                f"Case requires reporter and receiver participants "
                f"(≥2 parties); found {n} (LST-02-002)."
            )
        if not any(isinstance(s, CaseStatus) for s in self.case_statuses):
            raise VultronValidationError(
                "Case requires at least one materialized CaseStatus entry "
                "(LST-02-002)."
            )
        return self


class EmbargoedCase(Case):
    """Active-embargo stage: Case with a non-None active embargo.

    Guarantees all :class:`Case` invariants plus:

    - ``active_embargo`` is non-None.
    - The most recent :class:`~vultron.core.models.case_status.CaseStatus`
      has ``em_state ∈ {ACTIVE, REVISE}``.

    The EM machine never returns to ``NONE``/``PROPOSED`` once ``ACTIVE``,
    so this milestone is monotonic (LST-02-003).

    Shared ``type_="VulnerabilityCase"`` (inherited, not redeclared) ensures
    DataLayer round-trip compatibility.

    Spec: LST-02-001, LST-02-003.
    """

    @model_validator(mode="after")
    def _check_embargoed_invariants(self) -> "EmbargoedCase":
        if self.active_embargo is None:
            raise VultronValidationError(
                "EmbargoedCase requires active_embargo to be non-None "
                "(LST-02-003)."
            )
        try:
            em_state = self.current_status.em.state
        except ValueError as exc:
            raise VultronValidationError(
                "EmbargoedCase requires at least one materialized CaseStatus; "
                "found none (LST-02-003)."
            ) from exc
        if em_state not in (EM.ACTIVE, EM.REVISE):
            raise VultronValidationError(
                f"EmbargoedCase requires em_state ∈ {{ACTIVE, REVISE}}, "
                f"got {em_state!r} (LST-02-003)."
            )
        return self


__all__ = ["Case", "EmbargoedCase", "IncomingReport"]
