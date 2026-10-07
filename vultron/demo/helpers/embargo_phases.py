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

"""Embargo-phase steps shared by ``rcv-embargo`` and ``rcvv-embargo``.

Both scenarios assert the CASE_MANAGER's canonical ``em_state`` after a phase
(DEMOMA-20-008, DEMOMA-21-009) and both open with the Reporter revising the
default embargo that case creation activated (EP-04-001).  The assertions read
the CASE_MANAGER's canonical case, or wait for the fan-out; none reads a
triggering actor's replica straight after its trigger (DEMOMA-20-011,
DEMOMA-21-010).
"""

import logging

from vultron.core.states.em import EM
from vultron.demo.actor_session import ActorSession
from vultron.demo.exchange.embargo_lifecycle import (
    COMMIT_TIMEOUT_SECONDS,
    demo_propose_and_activate_embargo,
)
from vultron.demo.helpers.polling import (
    resolve_case_actor_store_id,
    wait_for_case_em_state,
)
from vultron.demo.utils import demo_check, demo_gate
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def canonical_case(
    session: ActorSession, case: as_VulnerabilityCase
) -> as_VulnerabilityCase:
    """The case as the CASE_MANAGER holds it, read through *session*'s container."""
    client = session.client
    return as_VulnerabilityCase.model_validate(
        client.get(
            client.dl_path(
                case.id_,
                actor_id=resolve_case_actor_store_id(client, case.id_),
            )
        )
    )


def assert_canonical_em_state(
    session: ActorSession,
    case: as_VulnerabilityCase,
    expected: EM,
    phase: str,
    active_embargo_id: str | None = None,
) -> None:
    """Assert the CASE_MANAGER's canonical case is at *expected*.

    Args:
        session: A session whose container hosts the CASE_MANAGER's store (the
            Coordinator's).
        phase: The phase name, for the check label.
        active_embargo_id: When given, the embargo that must be the active one;
            ``EM.ACTIVE`` alone cannot tell a revision from the embargo it
            revised.
    """
    client = session.client
    with demo_check(
        f"{phase}: CASE_MANAGER's canonical case has {expected.name}"
    ):
        wait_for_case_em_state(
            client,
            case.id_,
            expected,
            COMMIT_TIMEOUT_SECONDS,
            dl_actor_id=resolve_case_actor_store_id(client, case.id_),
            active_embargo_id=active_embargo_id,
        )


def confirm_embargo_revised(
    coordinator: ActorSession,
    case: as_VulnerabilityCase,
    prior_embargo_id: str | None,
    phase: str,
    gate_label: str,
) -> str | None:
    """Gate on a revision, not *prior_embargo_id*, being the embargo in force.

    A gate, not a check: later phases end or revise the embargo this one put in
    force, so without a revision they would only add secondary failures
    (DEMOCI-01-007).

    Returns:
        The id of the embargo now in force, or ``None`` when no revision took
        effect (the failure is recorded).
    """
    revised_embargo_id: str | None = None
    with demo_gate(gate_label):
        in_force = canonical_case(coordinator, case).active_embargo_id
        if in_force is None or in_force == prior_embargo_id:
            raise AssertionError(
                f"active embargo {in_force!r} is not a revision of"
                f" {prior_embargo_id!r}"
            )
        revised_embargo_id = in_force
        assert_canonical_em_state(
            coordinator,
            case,
            EM.ACTIVE,
            phase,
            active_embargo_id=revised_embargo_id,
        )
    return revised_embargo_id


def revise_default_embargo(
    reporter: ActorSession,
    coordinator: ActorSession,
    vendor: ActorSession,
    case: as_VulnerabilityCase,
    phase: str,
) -> str | None:
    """The Reporter revises the default embargo; the Coordinator activates it.

    Case creation activates the default embargo (EP-04-001), so the Reporter's
    proposal revises it: the CASE_MANAGER relays it, *vendor* consents, and
    *coordinator*, as owner, activates the revision (EP-09).

    Returns:
        The id of the embargo now in force, or ``None`` when no revision took
        effect (the failure is recorded).
    """
    default_embargo_id = canonical_case(coordinator, case).active_embargo_id

    demo_propose_and_activate_embargo(reporter, coordinator, vendor, case)

    return confirm_embargo_revised(
        coordinator,
        case,
        default_embargo_id,
        phase,
        "The revision, not the default embargo, is now in force",
    )
