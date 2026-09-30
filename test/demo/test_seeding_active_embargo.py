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

"""The demo seeder's active embargo follows EP-04, not a field default.

``seed_case_participants_for_demo`` compensates for the CaseProposal round
trip and seeds the embargo ``InitializeDefaultEmbargoNode`` would have
created.  With ``EmbargoEvent.end_time`` required (#3404) the seeder has to
state a duration, and the one it states is resolved the same way the tree
resolves it: the owner's shortest published ``EmbargoPolicy`` if there is
one, otherwise the protocol default (EP-04-005, EP-04-006).
"""

from collections.abc import Generator
from datetime import timedelta
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.config.app import get_config
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.states.em import EM
from vultron.demo.helpers.seeding import seed_case_participants_for_demo
from vultron.wire.as2.vocab.base.objects.actors import as_Service

_TOLERANCE = timedelta(seconds=2)


@pytest.fixture()
def owner_and_dl() -> Generator[
    tuple[as_Service, SqliteDataLayer], None, None
]:
    owner = as_Service(name="Seeded Vendor")
    reset_datalayer(owner.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner.id_)
    dl.clear_all()
    dl.create(owner)
    try:
        yield owner, dl
    finally:
        dl.close()
        reset_datalayer(owner.id_)


def _seed(owner: as_Service, dl: SqliteDataLayer) -> EmbargoEvent:
    case = VulnerabilityCase(name="Seeded case", attributed_to=owner.id_)
    dl.create(case)
    seed_case_participants_for_demo(
        case_id=case.id_,
        vendor_actor_id=owner.id_,
        reporter_actor_id=None,
        report_id=None,
        dl=dl,
    )
    stored = cast(VulnerabilityCase, dl.read(case.id_))
    assert stored.current_status.em.state == EM.ACTIVE
    embargo_id = stored.active_embargo_id
    assert embargo_id is not None
    embargo = dl.read(embargo_id)
    assert isinstance(embargo, EmbargoEvent)
    return embargo


def _duration(embargo: EmbargoEvent) -> timedelta:
    assert embargo.start_time is not None
    return embargo.end_time - embargo.start_time


@pytest.mark.spec("EP-04-005")
@pytest.mark.spec("EP-04-010")
def test_seeded_embargo_without_policies_uses_the_protocol_default(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """No published policy and no proposal: the protocol default applies."""
    owner, dl = owner_and_dl
    embargo = _seed(owner, dl)

    expected = get_config().actor.protocol_default_embargo_duration
    assert abs(_duration(embargo) - expected) <= _TOLERANCE


@pytest.mark.spec("EP-04-006")
def test_seeded_embargo_uses_the_owners_published_policy(
    owner_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A published actor default is the candidate; the protocol default is not."""
    owner, dl = owner_and_dl
    dl.create(
        EmbargoPolicy(
            actor_id=owner.id_,
            inbox=f"{owner.id_}/inbox",
            preferred_duration=timedelta(days=30),
        )
    )
    embargo = _seed(owner, dl)

    assert abs(_duration(embargo) - timedelta(days=30)) <= _TOLERANCE
