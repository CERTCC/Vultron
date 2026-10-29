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

"""Check that the actor deciding at a scenario step holds the step's role.

DEMOCI-11-013: when a scenario reports reaching a declared step, the harness
fails it if the calling actor does not hold the branch point's role.  Each
role is read from the canonical case in the CaseActor's own store
(DEMOMA-06-005), where it is recorded by the act that gave it:

- **A participant** holds the roles on its ``CaseParticipant`` record.  That
  includes an invitee that has not answered yet: the CASE_MANAGER seats an
  inert record with the roles the Invite offers (CM-17-003), so a
  ``vendor-join`` decision reads the role the Invite it answers gave it.
- **The Reporter** decides the root step before any case exists.  Its role
  comes from submitting the report, so the check is that the case the report
  produced names the deciding actor as the report's author.  The harness
  makes it when it first follows the case's ledger.
"""

from collections.abc import Mapping

from vultron.demo.helpers.seeding import _dl_key
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.errors import DemoScenarioStepError

# The checks read the stored JSON rather than parsing it into wire models.
# Each needs one or two fields, and a field that is missing or of the wrong
# shape must fail the step, not be filled in by a model default.  The reads
# are not free in a recording run: the server draws ids when it serves a
# record, so a recording made with the checks differs from one made without
# them from the first check on (``vultron.demo.determinism``).

#: A record as the store serves it: JSON, keyed by field name.
Record = Mapping[str, object]

_MISSING = object()


def _field(data: Record, camel: str, snake: str) -> object:
    """*data*'s value for a field stored under its camelCase or snake name.

    Returns ``_MISSING`` when the record has neither.
    """
    if camel in data:
        return data[camel]
    return data.get(snake, _MISSING)


def _ref_id(value: object) -> str | None:
    """The id of a reference given as a string or as an object's JSON."""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        found = value.get("id")
        return found if isinstance(found, str) else None
    return None


def _author(report: object) -> str | None:
    """The author a report's JSON names, or ``None`` when it names none."""
    if not isinstance(report, Mapping):
        return None
    author = _field(report, "attributedTo", "attributed_to")
    return None if author is _MISSING else _ref_id(author)


def _unreadable(key: str, what: str) -> DemoScenarioStepError:
    return DemoScenarioStepError(
        f"the CaseActor's record {key!r} {what}, so the step's role cannot "
        "be read (DEMOCI-11-013)."
    )


def _read(client: DataLayerClient, key: str) -> Record:
    """Read *key* from *client*'s own store, raising when it is not a record."""
    data: object = client.get(client.dl_path(key))
    if not isinstance(data, Mapping):
        raise _unreadable(key, f"is a {type(data).__name__}, not a record")
    return data


def require_case_role(
    case_actor_client: DataLayerClient,
    case_id: str,
    actor_id: str,
    role: CVDRole,
    step: str,
) -> None:
    """Fail unless *actor_id*'s participant in *case_id* holds *role*.

    Args:
        case_actor_client: Client bound to the CaseActor, whose store holds
            the canonical case.
        case_id: The case the scenario follows.
        actor_id: The actor deciding at the step.
        role: The branch point's role.
        step: The step, named for the error message.

    Raises:
        DemoScenarioStepError: When the actor is not a participant in the
            case, its participant does not hold *role*, or a record the
            check reads is not a record or lacks the field it needs.
        httpx.HTTPStatusError: When the CaseActor's store cannot be read.
    """
    case = _read(case_actor_client, case_id)
    index = _field(case, "actorParticipantIndex", "actor_participant_index")
    if not isinstance(index, Mapping):
        raise _unreadable(case_id, "has no participant index")
    participant_id = index.get(actor_id)
    if not isinstance(participant_id, str):
        raise DemoScenarioStepError(
            f"{step} is decided by {actor_id!r}, which is not a participant "
            f"in case {case_id!r}, so it holds no {role.name} role there "
            "(DEMOCI-11-013)."
        )
    participant = _read(case_actor_client, _dl_key(participant_id))
    roles = _field(participant, "caseRoles", "case_roles")
    if not isinstance(roles, list):
        raise _unreadable(participant_id, "has no list of case roles")
    if role.value not in roles:
        raise DemoScenarioStepError(
            f"{step} is decided by {actor_id!r}, whose participant in case "
            f"{case_id!r} holds {roles}, not the branch point's role "
            f"{role.value!r} (DEMOCI-11-013)."
        )


def require_report_submitter(
    case_actor_client: DataLayerClient,
    case_id: str,
    actor_id: str,
    step: str,
) -> None:
    """Fail unless *actor_id* authored a report of *case_id*.

    The Reporter decides the root step before the case exists, so its role
    comes from submitting the report (DEMOCI-11-013).

    Args:
        case_actor_client: Client bound to the CaseActor, whose store holds
            the canonical case and the report.
        case_id: The case the report produced.
        actor_id: The actor that decided the root step.
        step: The step, named for the error message.

    Raises:
        DemoScenarioStepError: When no report of the case names *actor_id*
            as its author, or a record the check reads is not a record or
            lacks the field it needs.
        httpx.HTTPStatusError: When the CaseActor's store cannot be read.
    """
    case = _read(case_actor_client, case_id)
    reports = _field(case, "vulnerabilityReports", "vulnerability_reports")
    if not isinstance(reports, list):
        raise _unreadable(case_id, "has no list of reports")
    authors: list[str | None] = []
    for report in reports:
        author = _author(report)
        if author is None and (report_id := _ref_id(report)) is not None:
            author = _author(_read(case_actor_client, _dl_key(report_id)))
        authors.append(author)
    if actor_id not in authors:
        raise DemoScenarioStepError(
            f"{step} is decided by {actor_id!r} as the Reporter, but the "
            f"reports of case {case_id!r} are by {authors}; the Reporter is "
            "the actor that submits the report (DEMOCI-11-013)."
        )
