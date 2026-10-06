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
"""The CASE_MANAGER role is never unfilled (CM-24-006).

Both creation paths register a holder at birth and delegation hands it on, so a
roster with no ``CVDRole.CASE_MANAGER`` is corrupt, not a topology.  A trigger
that must emit as the CASE_MANAGER fails on such a roster rather than sending
directly as the requester (a fallback an earlier, now retired, requirement allowed).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.use_cases.triggers.actor import (
    SvcOfferCaseOwnershipTransferUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    OfferCaseOwnershipTransferTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

OWNER = "https://example.org/actors/owner"
TRANSFEREE = "https://example.org/actors/transferee"


@pytest.mark.spec("CM-24-006")
def test_delegated_trigger_fails_when_no_case_manager_holds_the_role() -> None:
    """A roster with no CASE_MANAGER is a fault, not a fallback."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)
    dl.create(as_Service(id_=OWNER, name="Owner"))
    case = VulnerabilityCase(name="Corrupt roster", attributed_to=OWNER)
    dl.create(case)
    request = OfferCaseOwnershipTransferTriggerRequest(
        actor_id=OWNER, case_id=case.id_, transferee_id=TRANSFEREE
    )

    with pytest.raises(VultronNotFoundError, match="CASE_MANAGER"):
        SvcOfferCaseOwnershipTransferUseCase(dl, request).execute()
