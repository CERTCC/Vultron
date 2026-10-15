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

"""Ledger event types for the CASE_MANAGER's own consent-row entries.

A consent row belongs to a participant, so each row the CASE_MANAGER brings
into existence or changes as a consequence of an act is its own
CASE_MANAGER activity and its own entry, after the act's entry (ADR-0122,
ADR-0124, CLP-07-013).  Each carries the row in full, and every replica
writes it through the one apply function
(:func:`~vultron.core.models.embargo_apply.apply_embargo_change`).

- :data:`CREATE_EMBARGO_CONSENT_EVENT_TYPE` -- ``Create(EmbargoConsent)``:
  the CASE_MANAGER created a row, such as a participant's ``UNINVITED`` row
  when an embargo is proposed.
- :data:`UPDATE_EMBARGO_CONSENT_EVENT_TYPE` -- ``Update(EmbargoConsent)``:
  the CASE_MANAGER changed a row, such as ``CARRY_OVER`` at activation, its
  own policy consent, a time-out or a withdrawal decline.

Both are ledger event types only: no actor sends either as a message, so no
``MessageSemantics`` member names them.
"""

#: ``Create(EmbargoConsent)`` -- the CASE_MANAGER created a consent row.
CREATE_EMBARGO_CONSENT_EVENT_TYPE = "create_embargo_consent"

#: ``Update(EmbargoConsent)`` -- the CASE_MANAGER changed a consent row.
UPDATE_EMBARGO_CONSENT_EVENT_TYPE = "update_embargo_consent"

__all__ = [
    "CREATE_EMBARGO_CONSENT_EVENT_TYPE",
    "UPDATE_EMBARGO_CONSENT_EVENT_TYPE",
]
