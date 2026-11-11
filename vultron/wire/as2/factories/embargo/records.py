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
"""Factories that create an embargo event or create and update a consent row.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.vocab.activities.embargo import (
    _CreateEmbargoConsentActivity,
    _CreateEmbargoEventActivity,
    _UpdateEmbargoConsentActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Update,
)
from vultron.wire.as2.vocab.objects.embargo_consent import (
    as_EmbargoConsent,
)
from vultron.wire.as2.vocab.objects.embargo_event import (
    as_EmbargoEvent,
)


def create_embargo_event_activity(
    embargo: as_EmbargoEvent,
    **kwargs,
) -> as_Create:
    """Build a Create(EmbargoEvent): the case's creation wrote an embargo.

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    embargo in full, right after the genesis entry (CLP-07-021); never sent
    as a message.

    Args:
        embargo: The embargo the case's creation wrote.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "create_embargo_event_activity",
        _CreateEmbargoEventActivity,
        lambda: {"object_": embargo, **kwargs},
    )


def create_embargo_consent_activity(
    row: as_EmbargoConsent,
    **kwargs,
) -> as_Create:
    """Build a Create(EmbargoConsent): the CASE_MANAGER created a row.

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    new consent row in full (ADR-0122, CLP-07-021); never sent as a message.

    Args:
        row: The new consent row; it names its participant actor.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "create_embargo_consent_activity",
        _CreateEmbargoConsentActivity,
        lambda: {"object_": row, **kwargs},
    )


def update_embargo_consent_activity(
    row: as_EmbargoConsent,
    **kwargs,
) -> as_Update:
    """Build an Update(EmbargoConsent): the CASE_MANAGER changed a row.

    The snapshot shape of a CASE_MANAGER-authored ledger entry carrying the
    changed consent row in full (ADR-0122, CLP-07-021); never sent as a
    message.

    Args:
        row: The changed consent row; it names its participant actor.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "update_embargo_consent_activity",
        _UpdateEmbargoConsentActivity,
        lambda: {"object_": row, **kwargs},
    )
