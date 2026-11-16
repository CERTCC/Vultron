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
"""The wire fields the JSON-LD term check excuses, one ratchet per owner.

``uv run wire-context --check`` and ``test_wire_term_declarations.py`` read
these constants (:mod:`vultron.metadata.wire_context.terms`, by ``ast``, so
each must stay a ``frozenset`` literal of strings).  An entry is
``<declaring class>.<wire name>: <rule>``, and it names a field that a rule
of ADR-0194 refuses today (VM-10-007, VM-10-009, VM-10-012).  Each constant is
held equal to the violations it excuses in both directions: a new violation
fails, and so does an entry whose field is fixed (ARCH-18-001, ARCH-18-006).
When an owner Task fixes its fields, it deletes its constant or leaves it
empty, and the close guard refuses a pull request that closes an owner still
cited here (ARCH-18-012).
"""

# owner: #6410
KNOWN_EMBARGO_POLICY_TERM_VIOLATIONS = frozenset(
    {
        "EmbargoPolicy.actorId: VM-10-007",
        "EmbargoPolicy.notes: VM-10-007",
    }
)

# owner: #6411
KNOWN_LEDGER_ENTRY_TERM_VIOLATIONS = frozenset(
    {"CaseLedgerEntry.caseId: VM-10-007"}
)

# owner: #6413
KNOWN_ITEM_TITLE_TERM_VIOLATIONS = frozenset(
    {"VulnerabilityItem.title: VM-10-007"}
)

# owner: #6415
KNOWN_PARTICIPANT_TERM_VIOLATIONS = frozenset(
    {"CaseParticipant.participantCaseName: VM-10-007"}
)

# owner: #6416
KNOWN_ITEM_NAME_CLASH_TERM_VIOLATIONS = frozenset(
    {
        "VulnerabilityItem.notes: VM-10-007",
        "VulnerabilityItemId.text: VM-10-007",
        "VulnerabilityItemNote.text: VM-10-007",
    }
)

# owner: #6418
KNOWN_ACTOR_KEY_TERM_VIOLATIONS = frozenset(
    {"CoreActor.assertionMethod: VM-10-007"}
)

# owner: #6419
KNOWN_OFFER_REFERENCE_TERM_VIOLATIONS = frozenset(
    {
        "_AddReportToCaseActivity.offerActorId: VM-10-007",
        "_AddReportToCaseActivity.offerId: VM-10-007",
        "as_CaseProposal.offerActorId: VM-10-007",
        "as_CaseProposal.offerId: VM-10-007",
    }
)

# owner: #6420
KNOWN_CASE_STUB_TERM_VIOLATIONS = frozenset(
    {"as_VulnerabilityCaseStub.caseId: VM-10-007"}
)

# owner: #6421
KNOWN_EMBARGO_TERMINATION_TERM_VIOLATIONS = frozenset(
    {"EmbargoTermination.reason: VM-10-007"}
)
