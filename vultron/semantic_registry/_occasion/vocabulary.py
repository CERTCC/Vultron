"""Occasion vocabulary: the reference pages, how-to guides and formal
protocol shorthands an occasion names (MSM-06-002, MSM-08-008)."""

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

from enum import StrEnum


class MessagePage(StrEnum):
    """The ``docs/reference/messages/`` page that owns an entry (MSM-06-002).

    Values are the page file stems; member order is the canonical display
    order of the pages.
    """

    RM = "rm"
    EM = "em"
    CS = "cs"
    GENERAL = "general"
    FAULTS_AND_ACKNOWLEDGEMENTS = "faults_and_acknowledgements"
    CASE_MANAGEMENT = "case_management"
    CASE_PROPOSAL = "case_proposal"
    LEDGER_REPLICATION = "ledger_replication"


class HowToGuide(StrEnum):
    """The how-to guides an occasion declares, as ``docs/``-relative paths."""

    REPORT_VULNERABILITY = (
        "howto/activitypub/activities/report_vulnerability.md"
    )
    MANAGE_CASE = "howto/activitypub/activities/manage_case.md"
    INITIALIZE_CASE = "howto/activitypub/activities/initialize_case.md"
    INVITE_ACTOR = "howto/activitypub/activities/invite_actor.md"
    MANAGE_PARTICIPANTS = "howto/activitypub/activities/manage_participants.md"
    ROLE_DELEGATION = "howto/activitypub/activities/role_delegation.md"
    ESTABLISH_EMBARGO = "howto/activitypub/activities/establish_embargo.md"
    MANAGE_EMBARGO = "howto/activitypub/activities/manage_embargo.md"
    STATUS_UPDATES = "howto/activitypub/activities/status_updates.md"
    SUGGEST_ACTOR = "howto/activitypub/activities/suggest_actor.md"


class ProtocolShorthand(StrEnum):
    """The formal protocol message set (``formal_protocol/messages.md``).

    Unlike the legacy simulator's ``MessageTypes``, this lists the revision
    messages ``EV``, ``EJ`` and ``EC`` in their own right.  Each shares its
    wire activity with its initial-negotiation counterpart, told apart by the
    case's EM state: ``EV`` with ``EP`` on the embargo Invite, and ``EC`` and
    ``EJ`` with ``EA`` and ``ER`` on the Case Owner's decision,
    ``Add``/``Reject(EmbargoEvent)[target=VulnerabilityCase]`` (MSM-02).
    """

    RS = "RS"
    RI = "RI"
    RV = "RV"
    RD = "RD"
    RA = "RA"
    RC = "RC"
    RK = "RK"
    RE = "RE"
    EP = "EP"
    ER = "ER"
    EA = "EA"
    EV = "EV"
    EJ = "EJ"
    EC = "EC"
    ET = "ET"
    EK = "EK"
    EE = "EE"
    CV = "CV"
    CF = "CF"
    CD = "CD"
    CP = "CP"
    CX = "CX"
    CA = "CA"
    CK = "CK"
    CE = "CE"
    GI = "GI"
    GK = "GK"
    GE = "GE"

    @property
    def formal_name(self) -> str:
        """The message's name in ``formal_protocol/messages.md``, e.g.
        ``"Fix Readiness"`` for ``CF`` (MSM-08-008)."""
        return _FORMAL_NAMES[self]

    @property
    def formal_section(self) -> str:
        """The anchor of the ``formal_protocol/messages.md`` section that
        defines this message's family, e.g. ``"cs-message-types"``."""
        return _FORMAL_SECTIONS[self.value[0]]


#: The section of ``formal_protocol/messages.md`` defining each family of
#: shorthands, keyed by the shorthand's first letter (its state machine).
_FORMAL_SECTIONS: dict[str, str] = {
    "R": "rm-message-types",
    "E": "em-message-types",
    "C": "cs-message-types",
    "G": "other-message-types",
}

#: The formal message names, as ``docs/reference/formal_protocol/messages.md``
#: gives them; ``test_semantic_registry_occasions.py`` holds the two in step.
_FORMAL_NAMES: dict[ProtocolShorthand, str] = {
    ProtocolShorthand.RS: "Report Submission",
    ProtocolShorthand.RI: "Report Invalid",
    ProtocolShorthand.RV: "Report Valid",
    ProtocolShorthand.RD: "Report/Case Deferred",
    ProtocolShorthand.RA: "Report/Case Accepted",
    ProtocolShorthand.RC: "Report Closed",
    ProtocolShorthand.RK: "Report Acknowledgment",
    ProtocolShorthand.RE: "Report Error",
    ProtocolShorthand.EP: "Embargo Proposal",
    ProtocolShorthand.ER: "Embargo Proposal Rejection",
    ProtocolShorthand.EA: "Embargo Proposal Acceptance",
    ProtocolShorthand.EV: "Embargo Revision Proposal",
    ProtocolShorthand.EJ: "Embargo Revision Rejection",
    ProtocolShorthand.EC: "Embargo Revision Acceptance",
    ProtocolShorthand.ET: "Embargo Termination",
    ProtocolShorthand.EK: "Embargo Acknowledgment",
    ProtocolShorthand.EE: "Embargo Error",
    ProtocolShorthand.CV: "Vendor Awareness",
    ProtocolShorthand.CF: "Fix Readiness",
    ProtocolShorthand.CD: "Fix Deployed",
    ProtocolShorthand.CP: "Public Awareness",
    ProtocolShorthand.CX: "Exploit Public",
    ProtocolShorthand.CA: "Attacks Observed",
    ProtocolShorthand.CK: "CS Acknowledgment",
    ProtocolShorthand.CE: "CS Error",
    ProtocolShorthand.GI: "General Inquiry",
    ProtocolShorthand.GK: "General Acknowledgment",
    ProtocolShorthand.GE: "General Error",
}
