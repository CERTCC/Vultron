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

"""Closing the case a report opened on receipt, after the report is invalid.

Kept out of :mod:`vultron.demo.helpers` (the package does not re-export it)
because it composes :mod:`vultron.demo.exchange.embargo_lifecycle`, which
imports the helpers package; :mod:`~vultron.demo.helpers.embargo_phases`
stands apart for the same reason.
"""

from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.exchange.embargo_lifecycle import demo_terminate_embargo
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.workflow import (
    check_report_answer_recorded,
    receiver_invalidates_report,
    wait_for_case_for_offer,
)
from vultron.demo.utils import DataLayerClient, demo_gate, demo_step
from vultron.wire.as2.vocab.base.objects.actors import as_Actor


def receiver_invalidates_and_closes(
    client: DataLayerClient,
    reporter: as_Actor,
    receiver: as_Actor,
    offer_id: str,
    note: str,
) -> None:
    """Invalidate the report, then close the case opened for it on receipt.

    Once a case holds the report, its Case Owner closes the case by
    ``Leave(VulnerabilityCase)``, never by ``Close(Report)`` (CM-23-019).
    Every act goes through its actor's own trigger to the case's
    CASE_MANAGER (#5438):

    1. *receiver* invalidates the report (:func:`receiver_invalidates_report`),
       and the reporter's replica is checked to record it.
    2. *receiver*, the Case Owner, ends the case's embargo, which would
       refuse its ``Leave`` (TRIG-13-003).
    3. The reporter leaves, then *receiver* does, last (CM-23-015).

    Args:
        client: DataLayerClient for the container hosting every actor; it
            is bound to *receiver*'s store.
        reporter: The actor that submitted the report.
        receiver: The actor the report was offered to, the case's owner.
        offer_id: Full URI of the submit-report ``as_Offer``.
        note: The Report Invalid's ``content``.
    """
    receiver_invalidates_report(client, receiver, offer_id, note=note)
    check_report_answer_recorded(
        client, reporter, receiver, offer_id, {RM.INVALID}
    )
    with demo_gate("Case opened on receipt found for the closure"):
        case = wait_for_case_for_offer(client, offer_id)
        with demo_step(
            "Case Owner ends the embargo and closes the case, leaving last"
        ):
            demo_terminate_embargo(
                ActorSession(client=client, actor=receiver), case
            )
            close_case_owner_last(
                case=case,
                authority_client=client,
                # Each leaver's replica is read through a client bound to
                # its own store.
                others=[
                    CaseLeaver(
                        client=client.model_copy(
                            update={"actor_id": reporter.id_}
                        ),
                        actor=reporter,
                    )
                ],
                owner=CaseLeaver(client=client, actor=receiver),
            )
