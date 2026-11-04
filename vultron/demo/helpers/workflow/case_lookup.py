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

"""Find, or wait for, the case a report or report Offer produced."""

import logging

from vultron.demo.helpers.polling._poll import _poll_until
from vultron.demo.utils import (
    DataLayerClient,
    case_references_report,
    read_received_activity,
    ref_id,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def _report_id_from_offer_data(
    offer_data: dict[str, object],
    offer_id: str,
) -> str | None:
    """Extract the report ID referenced by an offer.

    Args:
        offer_data: Raw dict representation of the offer from the DataLayer.
        offer_id: Full URI of the offer (used in warning log only).

    Returns:
        The report ID string, or ``None`` if the offer does not reference a
        report object.
    """
    offer_object = offer_data.get("object")
    if isinstance(offer_object, str):
        return offer_object
    if isinstance(offer_object, dict):
        return offer_object.get("id")

    report_id = ref_id(offer_object)
    if report_id:
        return report_id

    logger.warning("Offer %s does not reference a report object", offer_id)
    return None


def _load_case_from_datalayer(
    client: DataLayerClient,
    item: str | dict[str, object],
    actor_id: str | None = None,
) -> as_VulnerabilityCase | None:
    """Load a as_VulnerabilityCase from the DataLayer, handling both IDs and dicts.

    Args:
        client: DataLayerClient for the container to query.
        item: Either a full case URI string or a raw dict to validate.
        actor_id: Whose replica to read.  Defaults to *client*'s own actor; must
            match the store the enclosing listing came from, or the id fetched
            here will be looked for in a different replica than it was found in.

    Returns:
        The ``as_VulnerabilityCase``, or ``None`` if the fetch fails.
    """
    if not isinstance(item, str):
        return as_VulnerabilityCase.model_validate(item)

    try:
        return as_VulnerabilityCase.model_validate(
            client.get(client.dl_path(item, actor_id=actor_id))
        )
    except Exception as exc:  # noqa: BLE001  # ruff-baseline #3326
        logger.warning("Could not fetch case %s: %s", item, exc)
        return None


def find_case_by_report_id(
    client: DataLayerClient,
    report_id: str,
    actor_id: str | None = None,
) -> as_VulnerabilityCase | None:
    """Find the first ``as_VulnerabilityCase`` referencing *report_id*.

    Args:
        client: DataLayerClient connected to the container holding the case.
        report_id: Full URI of the ``as_VulnerabilityReport``.
        actor_id: Whose replica to search.  Defaults to *client*'s own actor.
            Note that under ADR-0041 the **CaseActor** authors the canonical case,
            so a caller looking for the case a report produced — rather than for
            its own replica of one — should pass the CaseActor
            (:func:`~vultron.demo.utils.case_actor_id_for_report`).  Searching the
            reporter's or vendor's store instead finds nothing until the
            CaseActor's ``Create(VulnerabilityCase)`` has been delivered and
            processed.

    Returns:
        The matching ``as_VulnerabilityCase``, or ``None`` if not found.
    """
    cases_data = client.get(
        client.dl_path("VulnerabilityCases/", actor_id=actor_id)
    )
    if not cases_data:
        return None

    for item in cases_data:
        case = _load_case_from_datalayer(client, item, actor_id=actor_id)
        if case is None:
            continue

        if case_references_report(case, report_id):
            return case
    return None


def find_case_for_offer(
    client: DataLayerClient,
    offer_id: str,
) -> as_VulnerabilityCase | None:
    """Find the as_VulnerabilityCase associated with a report offer.

    The Offer is the one *client*'s actor received, read from its archive
    record (DL-06-006).

    Args:
        client: DataLayerClient connected to the container holding the case.
        offer_id: Full URI of the ``VultronActivity`` offer.

    Returns:
        The matching ``as_VulnerabilityCase``, or ``None`` if not found.
    """
    offer_data = read_received_activity(client, offer_id)
    if not offer_data:
        return None

    report_id = _report_id_from_offer_data(offer_data, offer_id)
    if not report_id:
        return None

    return find_case_by_report_id(client, report_id)


def wait_for_case_for_offer(
    client: DataLayerClient,
    offer_id: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
) -> as_VulnerabilityCase:
    """Poll *client*'s own store until the case for *offer_id* is replicated.

    This is the causal precondition for ``validate-report`` (ADR-0058).  Under
    ADR-0041 the receiver does not create the case: it proposes one to the
    CaseActor, which creates the case in *its own* store (ADR-0073) and
    replicates it back as ``Create(VulnerabilityCase)``.  PCR-01-003 makes that
    the *only* route — co-locating the CaseActor on the same host grants no
    visibility into its store — so the receiver genuinely has no case until the
    replica lands, and ``RM.VALID`` is a case-scoped transition.

    Unlike the case object as observed *after* validate-report (which used to
    look synchronously available and was therefore an invalid gate, #2134), the
    replica's arrival is a real asynchronous event driven by another actor's
    outbox: exactly the kind of causal arrow ADR-0058 wants gated.

    Lives next to :func:`find_case_for_offer` rather than in the ``polling``
    package because it is that lookup's polling wrapper; putting it here
    keeps the offer→report→case resolution chain in one module
    (ARCH-15-004).

    Args:
        client: DataLayerClient connected to the receiving actor's container.
        offer_id: Full URI of the submit-report ``as_Offer`` activity.
        timeout_seconds: Maximum time to wait for the replica.
        poll_interval: Seconds between polls.

    Returns:
        The replicated ``as_VulnerabilityCase`` from *client*'s own store.

    Raises:
        AssertionError: If the replica does not appear within *timeout_seconds*.
    """
    found: dict[str, as_VulnerabilityCase] = {}

    def _check() -> bool:
        case = find_case_for_offer(client, offer_id)
        if case is None:
            return False
        found["case"] = case
        return True

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for the VulnerabilityCase replica for offer"
        f" {offer_id!r} to arrive in the store at {client.base_url} — the"
        " CaseActor's Create(VulnerabilityCase) may not have been delivered"
        " (ADR-0041, PCR-01-003)",
        swallow_exceptions=True,
    )
    return found["case"]


def wait_for_case_by_report(
    client: DataLayerClient,
    report_id: str,
    actor_id: str,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.5,
) -> as_VulnerabilityCase:
    """Poll *actor_id*'s store on *client* until the case for *report_id* exists.

    The canonical case is created by the CaseActor in *its own* store when it
    accepts the vendor's ``Create(CaseProposal)`` (ADR-0041, ADR-0073), some
    time after the report Offer was delivered — a background task on the
    receiver, then another on the CaseActor.  Pass the CaseActor's id to read
    the canonical case, or a participant's id to wait for that participant's
    replica of it.  This is :func:`find_case_by_report_id`'s polling wrapper
    and lives beside it for the reason :func:`wait_for_case_for_offer` gives.

    Args:
        client: DataLayerClient connected to the container hosting *actor_id*.
        report_id: Full URI of the ``as_VulnerabilityReport``.
        actor_id: Whose store to read — the CaseActor's for the canonical case.
        timeout_seconds: Maximum time to wait.
        poll_interval: Seconds between polls.

    Returns:
        The ``as_VulnerabilityCase`` referencing *report_id* in that store.

    Raises:
        AssertionError: If no such case appears within *timeout_seconds*.
    """
    found: dict[str, as_VulnerabilityCase] = {}

    def _check() -> bool:
        case = find_case_by_report_id(client, report_id, actor_id=actor_id)
        if case is None:
            return False
        found["case"] = case
        return True

    _poll_until(
        _check,
        timeout_seconds,
        poll_interval,
        f"Timed out waiting for a VulnerabilityCase referencing report"
        f" {report_id!r} in the store of {actor_id!r} at {client.base_url}"
        " — the CaseActor's Create(CaseProposal) handling may not have"
        " completed (ADR-0041)",
        swallow_exceptions=True,
    )
    return found["case"]
