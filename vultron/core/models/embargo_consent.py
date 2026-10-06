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

"""One participant's consent to one embargo.

Consent is per (participant, embargo) (ADR-0120, CM-10-001, CM-18-001): a
:class:`CaseParticipant` carries one :class:`EmbargoConsent` row for each
embargo it was asked about, and nothing else records consent.  Being bound by
the embargo in force, and having lapsed from a replaced one, are lookups over
the rows — see :meth:`CaseParticipant.is_signatory` and
:meth:`CaseParticipant.has_lapsed`.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)


class EmbargoConsent(ValidatedAssignmentMixin, BaseModel):
    """A participant's answer to one embargo: the row of the consent table."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    embargo_id: NonEmptyString
    state: EmbargoConsentState
