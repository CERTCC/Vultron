#!/usr/bin/env python

#  Copyright (c) 2023-2026 Carnegie Mellon University and Contributors.
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

"""CVD Role enumeration — bottom-of-stack neutral layer.

``CVDRole`` is a cross-cutting primitive used by ``vultron/core/``,
``vultron/config/``, and ``vultron/adapters/``.  It lives here so that all
three layers can import it without creating circular dependencies.

This module MUST NOT import from ``vultron.core``, ``vultron.config``, or
``vultron.adapters``.

Per ``docs/adr/0031-vultron-enums-neutral-layer.md`` and
``specs/configuration.yaml`` CFG-07-006.
"""

from enum import StrEnum, auto


class CVDRole(StrEnum):
    """Individual CVD role values (lowercase string enum).

    Each member represents a single, atomic CVD role. Participants may hold
    multiple roles simultaneously; use ``list[CVDRole]`` at call sites rather
    than bitmask arithmetic.

    Values are lowercase strings (e.g. ``CVDRole.REPORTER == 'reporter'``).

    There is no ``FINDER`` role (ADR-0078): an actor that discovers and
    reports a vulnerability holds ``REPORTER``, and who found it is report or
    note metadata.  The retired wire value ``"finder"`` is refused, see
    :data:`RETIRED_ROLE_VALUES`.

    Roles:
        REPORTER: Entity that reports the vulnerability to others.
        VENDOR: Supplier of the affected product or service.
        DEPLOYER: Entity that deploys the fix.
        COORDINATOR: Entity that coordinates the CVD process.
        OBSERVER: Monitoring participant with no vendor-fix-deployment
            obligations; the base (lowest non-null privilege) CVD role.
            Admitted via standard Invite/Accept (CM-25). Formerly ``OTHER``;
            renamed in ADR-0057.
        CASE_OWNER: Actor who owns and manages a VulnerabilityCase (BTND-05-001).
        CASE_MANAGER: The ActivityStreams Actor that performs ongoing case
            replica synchronisation and manages the case on behalf of the case
            owner.  A CaseManager participant SHOULD also hold the COORDINATOR
            role (CBT-01-003); nothing requires it.  While the demo uses a
            Service actor type, any Actor type (e.g. Person) may hold this
            role.
        CVE_NUMBERING_AUTHORITY: Participant that holds CVE Numbering Authority
            (CNA) status, granting authority to assign CVE IDs.  A CNA is
            orthogonal to other CVD roles — a VENDOR, COORDINATOR, or any other
            participant may independently hold this role.  Used by
            ``IsIDAssignmentAuthority`` (static capability check) and
            ``IdAssignable`` (scope-match evaluation) BT nodes to route ID
            assignment decisions to the correct participant(s).
    """

    REPORTER = auto()
    VENDOR = auto()
    DEPLOYER = auto()
    COORDINATOR = auto()
    OBSERVER = auto()
    CASE_OWNER = auto()
    CASE_MANAGER = auto()
    CVE_NUMBERING_AUTHORITY = auto()


#: Wire values of retired ``CVDRole`` members, mapped to why each is refused.
#: Stored data or an inbound activity carrying one fails validation with this
#: reason rather than being read as another role: a retired role is not an
#: alias, and silently rewriting it would change what a record claims.
RETIRED_ROLE_VALUES: dict[str, str] = {
    "finder": (
        "the 'finder' role was retired (ADR-0078); an actor that discovers and"
        " reports a vulnerability holds 'reporter', and who found it belongs"
        " in the report or a case note"
    ),
}


def parse_role(value: str) -> CVDRole:
    """Parse one role string (any case) into a ``CVDRole``.

    Raises:
        ValueError: *value* is a retired role (:data:`RETIRED_ROLE_VALUES`),
            with the retirement reason, or is not a role at all.
    """
    key = value.lower()
    reason = RETIRED_ROLE_VALUES.get(key)
    if reason is not None:
        raise ValueError(f"{value!r} is not a valid CVDRole: {reason}")
    return CVDRole(key)


def serialize_roles(roles: list[CVDRole]) -> list[str]:
    """Serialize a list of CVDRole members to a list of lowercase strings."""
    return [role.value for role in roles]


def validate_roles(
    value: object, field_name: str = "default_case_roles"
) -> list[CVDRole]:
    """Coerce a list of strings or CVDRole members to ``list[CVDRole]``.

    Accepts either a list of ``CVDRole`` enum members (pass-through) or a
    list of string values (e.g. from JSON deserialization).  ``None`` is
    treated as an empty list (field omitted).  Any other non-list type, or a
    list item that is neither a string nor a ``CVDRole``, raises
    ``ValueError`` naming ``field_name`` so a malformed value is refused rather
    than read as "no roles".
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(  # noqa: TRY004  # ruff-baseline #3353
            f"{field_name} must be a list of CVDRole strings, got {type(value).__name__!r}: {value!r}"
        )
    result: list[CVDRole] = []
    for item in value:
        if isinstance(item, CVDRole):
            result.append(item)
        elif isinstance(item, str):
            result.append(parse_role(item))
        else:
            # ValueError, not TypeError: Pydantic only turns ValueError into a
            # ValidationError, and callers are field validators.
            raise ValueError(  # noqa: TRY004
                f"{field_name} items must be CVDRole strings, got {type(item).__name__!r}: {item!r}"
            )
    return result
