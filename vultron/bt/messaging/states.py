#!/usr/bin/env python
"""file: message_types
author: adh
created_at: 4/7/22 12:39 PM
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


from enum import Enum


class MessageTypes(Enum):
    """Represents the type of a message.
    Message types are used to determine the type of a message and to determine the type of a message's response.

    Message types include:

    RS = Report Submission
    RI = Report Invalid
    RV = Report Valid
    RD = Report Deferred
    RA = Report Accepted
    RC = Report Closed
    RK = Report Management acknowledgement (general)
    RE = Report Management error (general)

    EP = Embargo Proposal
    ER = Embargo Rejected
    EA = Embargo Accepted
    EV = Embargo Revision Proposal
    EJ = Embargo Revision Rejected
    EC = Embargo Revision Accepted
    ET = Embargo Terminated
    EK = Embargo Management acknowledgement (general)
    EE = Embargo Management error (general)

    CV = Vendor Aware
    CF = Fix Ready
    CD = Fix Deployed
    CP = Public Aware
    CX = Exploit Published
    CA = Attacks Observed
    CK = Case State acknowledgement (general)
    CE = Case State error (general)

    GI = General Information Request
    GK = General Information acknowledgement
    GE = General Information error
    """

    VULTRON_MESSAGE_REPORT_SUBMISSION = "RS"
    VULTRON_MESSAGE_REPORT_INVALID = "RI"
    VULTRON_MESSAGE_REPORT_VALID = "RV"
    VULTRON_MESSAGE_REPORT_DEFERRED = "RD"
    VULTRON_MESSAGE_REPORT_ACCEPTED = "RA"
    VULTRON_MESSAGE_REPORT_CLOSED = "RC"
    VULTRON_MESSAGE_REPORT_MANAGEMENT_ACK = "RK"
    VULTRON_MESSAGE_REPORT_MANAGEMENT_ERROR = "RE"

    VULTRON_MESSAGE_EMBARGO_PROPOSAL = "EP"
    VULTRON_MESSAGE_EMBARGO_REJECTED = "ER"
    VULTRON_MESSAGE_EMBARGO_ACCEPTED = "EA"
    VULTRON_MESSAGE_EMBARGO_REVISION_PROPOSAL = "EV"
    VULTRON_MESSAGE_EMBARGO_REVISION_REJECTED = "EJ"
    VULTRON_MESSAGE_EMBARGO_REVISION_ACCEPTED = "EC"
    VULTRON_MESSAGE_EMBARGO_TERMINATED = "ET"
    VULTRON_MESSAGE_EMBARGO_MANAGEMENT_ACK = "EK"
    VULTRON_MESSAGE_EMBARGO_MANAGEMENT_ERROR = "EE"

    VULTRON_MESSAGE_CASE_STATE_VENDOR_AWARE = "CV"
    VULTRON_MESSAGE_CASE_STATE_FIX_READY = "CF"
    VULTRON_MESSAGE_CASE_STATE_FIX_DEPLOYED = "CD"
    VULTRON_MESSAGE_CASE_STATE_PUBLIC_AWARE = "CP"
    VULTRON_MESSAGE_CASE_STATE_EXPLOIT_PUBLISHED = "CX"
    VULTRON_MESSAGE_CASE_STATE_ATTACKS_OBSERVED = "CA"
    VULTRON_MESSAGE_CASE_STATE_ACK = "CK"
    VULTRON_MESSAGE_CASE_STATE_ERROR = "CE"

    VULTRON_MESSAGE_GENERAL_INFORMATION_REQUEST = "GI"
    VULTRON_MESSAGE_GENERAL_INFORMATION_ACK = "GK"
    VULTRON_MESSAGE_GENERAL_INFORMATION_ERROR = "GE"

    # convenience aliases
    ReportSubmission = VULTRON_MESSAGE_REPORT_SUBMISSION
    ReportInvalid = VULTRON_MESSAGE_REPORT_INVALID
    ReportValid = VULTRON_MESSAGE_REPORT_VALID
    ReportDeferred = VULTRON_MESSAGE_REPORT_DEFERRED
    ReportAccepted = VULTRON_MESSAGE_REPORT_ACCEPTED
    ReportClosed = VULTRON_MESSAGE_REPORT_CLOSED
    ReportManagementAck = VULTRON_MESSAGE_REPORT_MANAGEMENT_ACK
    ReportManagementError = VULTRON_MESSAGE_REPORT_MANAGEMENT_ERROR

    EmbargoProposal = VULTRON_MESSAGE_EMBARGO_PROPOSAL
    EmbargoRejected = VULTRON_MESSAGE_EMBARGO_REJECTED
    EmbargoAccepted = VULTRON_MESSAGE_EMBARGO_ACCEPTED
    EmbargoRevisionProposal = VULTRON_MESSAGE_EMBARGO_REVISION_PROPOSAL
    EmbargoRevisionRejected = VULTRON_MESSAGE_EMBARGO_REVISION_REJECTED
    EmbargoRevisionAccepted = VULTRON_MESSAGE_EMBARGO_REVISION_ACCEPTED
    EmbargoTerminated = VULTRON_MESSAGE_EMBARGO_TERMINATED
    EmbargoManagementAck = VULTRON_MESSAGE_EMBARGO_MANAGEMENT_ACK
    EmbargoManagementError = VULTRON_MESSAGE_EMBARGO_MANAGEMENT_ERROR

    CaseStateVendorAware = VULTRON_MESSAGE_CASE_STATE_VENDOR_AWARE
    CaseStateFixReady = VULTRON_MESSAGE_CASE_STATE_FIX_READY
    CaseStateFixDeployed = VULTRON_MESSAGE_CASE_STATE_FIX_DEPLOYED
    CaseStatePublicAware = VULTRON_MESSAGE_CASE_STATE_PUBLIC_AWARE
    CaseStateExploitPublished = VULTRON_MESSAGE_CASE_STATE_EXPLOIT_PUBLISHED
    CaseStateAttacksObserved = VULTRON_MESSAGE_CASE_STATE_ATTACKS_OBSERVED
    CaseStateAck = VULTRON_MESSAGE_CASE_STATE_ACK
    CaseStateError = VULTRON_MESSAGE_CASE_STATE_ERROR

    GeneralInformationRequest = VULTRON_MESSAGE_GENERAL_INFORMATION_REQUEST
    GeneralInformationAck = VULTRON_MESSAGE_GENERAL_INFORMATION_ACK
    GeneralInformationError = VULTRON_MESSAGE_GENERAL_INFORMATION_ERROR

    # convenience aliases
    RS = VULTRON_MESSAGE_REPORT_SUBMISSION
    RI = VULTRON_MESSAGE_REPORT_INVALID
    RV = VULTRON_MESSAGE_REPORT_VALID
    RD = VULTRON_MESSAGE_REPORT_DEFERRED
    RA = VULTRON_MESSAGE_REPORT_ACCEPTED
    RC = VULTRON_MESSAGE_REPORT_CLOSED
    RK = VULTRON_MESSAGE_REPORT_MANAGEMENT_ACK
    RE = VULTRON_MESSAGE_REPORT_MANAGEMENT_ERROR

    EP = VULTRON_MESSAGE_EMBARGO_PROPOSAL
    ER = VULTRON_MESSAGE_EMBARGO_REJECTED
    EA = VULTRON_MESSAGE_EMBARGO_ACCEPTED
    EV = VULTRON_MESSAGE_EMBARGO_REVISION_PROPOSAL
    EJ = VULTRON_MESSAGE_EMBARGO_REVISION_REJECTED
    EC = VULTRON_MESSAGE_EMBARGO_REVISION_ACCEPTED
    ET = VULTRON_MESSAGE_EMBARGO_TERMINATED
    EK = VULTRON_MESSAGE_EMBARGO_MANAGEMENT_ACK
    EE = VULTRON_MESSAGE_EMBARGO_MANAGEMENT_ERROR

    CV = VULTRON_MESSAGE_CASE_STATE_VENDOR_AWARE
    CF = VULTRON_MESSAGE_CASE_STATE_FIX_READY
    CD = VULTRON_MESSAGE_CASE_STATE_FIX_DEPLOYED
    CP = VULTRON_MESSAGE_CASE_STATE_PUBLIC_AWARE
    CX = VULTRON_MESSAGE_CASE_STATE_EXPLOIT_PUBLISHED
    CA = VULTRON_MESSAGE_CASE_STATE_ATTACKS_OBSERVED
    CK = VULTRON_MESSAGE_CASE_STATE_ACK
    CE = VULTRON_MESSAGE_CASE_STATE_ERROR

    GI = VULTRON_MESSAGE_GENERAL_INFORMATION_REQUEST
    GK = VULTRON_MESSAGE_GENERAL_INFORMATION_ACK
    GE = VULTRON_MESSAGE_GENERAL_INFORMATION_ERROR

    def __str__(self):
        return self.name


# Report Management Message Types
RM_MESSAGE_TYPES = [
    MessageTypes.RS,
    MessageTypes.RI,
    MessageTypes.RV,
    MessageTypes.RD,
    MessageTypes.RA,
    MessageTypes.RC,
    MessageTypes.RK,
    MessageTypes.RE,
]

# Embargo Management Message Types
EM_MESSAGE_TYPES = [
    MessageTypes.EP,
    MessageTypes.ER,
    MessageTypes.EA,
    MessageTypes.EV,
    MessageTypes.EJ,
    MessageTypes.EC,
    MessageTypes.ET,
    MessageTypes.EK,
    MessageTypes.EE,
]

# Case State Message Types
CS_MESSAGE_TYPES = [
    MessageTypes.CV,
    MessageTypes.CF,
    MessageTypes.CD,
    MessageTypes.CP,
    MessageTypes.CX,
    MessageTypes.CA,
    MessageTypes.CK,
    MessageTypes.CE,
]

# General Information Message Types
GM_MESSAGE_TYPES = [MessageTypes.GI, MessageTypes.GK, MessageTypes.GE]


def main():
    print("All Message Types:")
    print("------------------")
    for message_type in list(MessageTypes):
        print(message_type, message_type.value)

    print()
    print("Report Management Message Types:")
    print("-------------------------------")
    for message_type in RM_MESSAGE_TYPES:
        print(message_type, message_type.value)

    print()
    print("Embargo Management Message Types:")
    print("---------------------------------")
    for message_type in EM_MESSAGE_TYPES:
        print(message_type, message_type.value)

    print()
    print("Case State Message Types:")
    print("-------------------------")
    for message_type in CS_MESSAGE_TYPES:
        print(message_type, message_type.value)

    print()
    print("General Information Message Types:")
    print("----------------------------------")
    for message_type in GM_MESSAGE_TYPES:
        print(message_type, message_type.value)


if __name__ == "__main__":
    main()
