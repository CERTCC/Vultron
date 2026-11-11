#!/usr/bin/env python

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

"""The case inputs a report's attached document fills (CSAF-02, CSAF-03).

One mapping serves both sides of a report:

- the CASE_MANAGER fills the inputs of a case it creates from a proposal that
  carries the initial ``Offer(VulnerabilityReport)``, measured against its
  receipt of that proposal (CSAF-02-001, CSAF-03-001);
- the Reporter's submit-report trigger fills the report name, summary and
  proposed embargo end its request leaves unstated, measured against its own
  "now" (CSAF-04-010).

:func:`case_inputs_from_claims` is that mapping.  The reference time is a
parameter, so neither caller reads a clock below its act's edge (ADR-0176).
A value the Offer or the report states always wins over the document's
(CSAF-02-003), and only a document of category ``csaf_vulnerability_report``
fills anything (CSAF-02-001, CSAF-02-002).

:func:`claims_signals` raises the receiver-local case-split and
candidate-parties signals (CSAF-04-006, CSAF-04-007).  A signal only shows
that a split or a party may be needed; nothing here acts on one
(CSAF-04-008).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models._helpers import timestamp_serializer
from vultron.core.models.case_reference import (
    CaseReference,
    CaseReferenceLink,
)
from vultron.core.models.report_claims import (
    CandidatePartiesSignal,
    CaseSplitDifference,
    CaseSplitSignal,
    ClaimedReference,
    ClaimOutcome,
    ReportClaims,
    VulnerabilityClaims,
)
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
    VulnerabilityItemNote,
)
from vultron.core.scoring.ssvc_2 import SSVC_2_Exploitation
from vultron.primitives import NonEmptyString

#: The CSAF profile whose documents may fill case inputs (CSAF-02-001).
CSAF_VULNERABILITY_REPORT = "csaf_vulnerability_report"

#: SSVC v2 Exploitation value keys, as the wire reader copies them
#: (``VulnerabilityClaims.exploitation``), onto core's SSVC type.
SSVC_EXPLOITATION_KEYS: dict[str, SSVC_2_Exploitation] = {
    "N": SSVC_2_Exploitation.NONE,
    "P": SSVC_2_Exploitation.POC,
    "A": SSVC_2_Exploitation.ACTIVE,
}


#: The SSVC Exploitation values that set a CS bit; ``None`` sets nothing
#: (CSAF-03-004).
_STATES_SOMETHING = frozenset(
    {SSVC_2_Exploitation.POC, SSVC_2_Exploitation.ACTIVE}
)


class StatedReportFields(BaseModel):
    """What the Offer and its report state for the values a document can fill.

    ``proposed_embargo_end`` is the end of the Offer's ``proposedEmbargo``;
    ``None`` means the Offer carries none.  Each field that is not ``None``
    beats the document's value for the same thing (CSAF-02-003).
    """

    model_config = ConfigDict(frozen=True)

    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    proposed_embargo_end: datetime | None = None

    _serialize_proposed_embargo_end = timestamp_serializer(
        "proposed_embargo_end"
    )


class ReportCaseInputs(BaseModel):
    """The case inputs a report states, filled from its document.

    ``name``, ``summary`` and ``proposed_embargo_end`` are the stated value
    when there is one, else the document's; ``proposed_embargo_end`` is
    ``None`` when the document sets P, X or A, since the case then starts
    with no embargo (EP-04-020).  ``public``, ``exploit_public``
    and ``attacks_observed`` are the P, X and A the document states for any
    of its vulnerabilities; no Vultron field states them.  ``outcomes`` names
    each document value this mapping used (``APPLIED``) or set aside for a
    stated one (``OVERRIDDEN``); a value it names nowhere stays display only
    (CSAF-04-004).  ``filled_from_document`` is ``False`` when the document
    may fill nothing (CSAF-02-002): the stated fields then pass through and
    no outcome is given.

    ``item_vulnerabilities`` are the document's vulnerabilities that become
    the case's vulnerability items, those with a ``cve`` or an ``ids`` entry
    (CSAF-03-008), and ``references`` its document-level references, which
    become the case's references (CSAF-03-009).  They are claims, not case
    objects: the case's creator builds the objects
    (:func:`vulnerability_item_from_claims`, :func:`case_reference_from_claim`),
    so this mapping mints no id.
    """

    model_config = ConfigDict(frozen=True)

    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    proposed_embargo_end: datetime | None = None
    public: bool = False
    exploit_public: bool = False
    attacks_observed: bool = False
    item_vulnerabilities: list[VulnerabilityClaims] = Field(
        default_factory=list
    )
    references: list[ClaimedReference] = Field(default_factory=list)
    outcomes: dict[NonEmptyString, ClaimOutcome] = Field(default_factory=dict)
    filled_from_document: bool = False

    _serialize_proposed_embargo_end = timestamp_serializer(
        "proposed_embargo_end"
    )

    @classmethod
    def from_stated(cls, stated: StatedReportFields) -> "ReportCaseInputs":
        """The inputs when no document fills any: the stated values alone."""
        return cls(
            name=stated.name,
            summary=stated.summary,
            proposed_embargo_end=stated.proposed_embargo_end,
        )

    @property
    def embargo_eligible(self) -> bool:
        """Whether the case may start under an embargo (EP-04-020)."""
        return not (
            self.public or self.exploit_public or self.attacks_observed
        )


def fills_case_inputs(claims: ReportClaims) -> bool:
    """Whether a document of *claims*' category may fill case inputs.

    Only the CSAF Vulnerability Report profile speaks for the sender
    (CSAF-02-001); a document of any other category changes no case data
    (CSAF-02-002).  Whether the report is an initial one is the caller's
    question, because it needs the receiver's store.
    """
    return claims.document_category == CSAF_VULNERABILITY_REPORT


def _require_aware(reference_time: datetime) -> None:
    if reference_time.tzinfo is None:
        raise ValueError(
            "the reference time for a document's dates needs a time zone,"
            f" got {reference_time.isoformat()} (CSAF-03-001)"
        )


def _is_future(when: datetime | None, reference_time: datetime) -> bool:
    """A date counts as future only when later than the reference time.

    A date equal to it counts as past (CSAF-03-003).
    """
    return when is not None and when > reference_time


def _exploitation(vul: VulnerabilityClaims) -> SSVC_2_Exploitation | None:
    """The SSVC Exploitation value *vul* states, or ``None``.

    A key that is not an SSVC v2 Exploitation value states nothing.
    """
    if vul.exploitation is None:
        return None
    return SSVC_EXPLOITATION_KEYS.get(vul.exploitation)


class _VulState(BaseModel):
    """The P, X, A and future disclosure date one vulnerability states."""

    model_config = ConfigDict(frozen=True)

    public: bool
    exploit_public: bool
    attacks_observed: bool
    future_disclosure_date: datetime | None

    _serialize_future_disclosure_date = timestamp_serializer(
        "future_disclosure_date"
    )


def _vul_state(
    vul: VulnerabilityClaims, reference_time: datetime
) -> _VulState:
    exploitation = _exploitation(vul)
    future = _is_future(vul.disclosure_date, reference_time)
    return _VulState(
        public=vul.disclosure_date is not None and not future,
        exploit_public=exploitation is SSVC_2_Exploitation.POC,
        attacks_observed=exploitation is SSVC_2_Exploitation.ACTIVE
        or bool(vul.first_known_exploitation_dates),
        future_disclosure_date=vul.disclosure_date if future else None,
    )


def makes_vulnerability_item(vul: VulnerabilityClaims) -> bool:
    """Whether *vul* names its vulnerability, so it becomes an item.

    A vulnerability item is what later messages and projections refer to
    (CM-05-003), so an entry with neither a ``cve`` nor an ``ids`` entry
    makes none (CSAF-03-008).
    """
    return vul.cve is not None or bool(vul.ids)


def case_reference_from_claim(claim: ClaimedReference) -> CaseReference:
    """The case reference a claimed reference becomes (CSAF-03-009).

    The claim's ``url`` is the ``href`` of the reference's ``url`` Link and
    its ``summary`` the reference's ``name``.  The Link carries no ``rel``:
    a CSAF reference says nothing of what kind of resource it names, and
    its ``category`` (``self`` or ``external``) is about the document, not
    the resource.
    """
    return CaseReference(
        url=CaseReferenceLink(href=claim.url), name=claim.summary
    )


def vulnerability_item_from_claims(
    vul: VulnerabilityClaims,
) -> VulnerabilityItem:
    """The vulnerability item *vul* becomes, field for field (CSAF-03-008).

    Its ``cve``, ``ids``, ``title`` and ``notes`` are copied as claimed, and
    no identifier is interpreted (CM-05-008); each of its references becomes
    a case reference held inline on the item.

    Raises:
        ValueError: when *vul* names no vulnerability
            (:func:`makes_vulnerability_item`).
    """
    if not makes_vulnerability_item(vul):
        raise ValueError(
            "a CSAF vulnerability with no cve and no ids names no"
            " vulnerability, so it makes no vulnerability item (CSAF-03-008)"
        )
    return VulnerabilityItem(
        cve=vul.cve,
        ids=[
            VulnerabilityItemId(system_name=i.system_name, text=i.text)
            for i in vul.ids
        ],
        title=vul.title,
        notes=[
            VulnerabilityItemNote(**note.model_dump()) for note in vul.notes
        ],
        references=[case_reference_from_claim(r) for r in vul.references],
    )


def _item_outcomes(
    claims: ReportClaims, outcomes: dict[str, ClaimOutcome]
) -> list[VulnerabilityClaims]:
    """Mark the values the case's items and references take ``APPLIED``.

    Returns the vulnerabilities that make items.  The document-level
    references all become case references (CSAF-03-009); a vulnerability's
    identity fields become its item's only when it names the vulnerability
    (CSAF-03-008), and otherwise stay display only.
    """
    for index in range(len(claims.references)):
        outcomes[f"references[{index}]"] = ClaimOutcome.APPLIED
    items: list[VulnerabilityClaims] = []
    for index, vul in enumerate(claims.vulnerabilities):
        if not makes_vulnerability_item(vul):
            continue
        items.append(vul)
        prefix = f"vulnerabilities[{index}]."
        if vul.cve is not None:
            outcomes[f"{prefix}cve"] = ClaimOutcome.APPLIED
        if vul.title is not None:
            outcomes[f"{prefix}title"] = ClaimOutcome.APPLIED
        for name in ("ids", "notes", "references"):
            for i in range(len(getattr(vul, name))):
                outcomes[f"{prefix}{name}[{i}]"] = ClaimOutcome.APPLIED
    return items


def _stated_or_claimed(
    path: str,
    stated: str | None,
    claimed: str | None,
    outcomes: dict[str, ClaimOutcome],
) -> str | None:
    """Take *stated* over *claimed*, recording the claim's outcome at *path*."""
    if claimed is None:
        return stated
    if stated is not None:
        outcomes[path] = ClaimOutcome.OVERRIDDEN
        return stated
    outcomes[path] = ClaimOutcome.APPLIED
    return claimed


def case_inputs_from_claims(
    claims: ReportClaims,
    *,
    reference_time: datetime,
    stated: StatedReportFields | None = None,
) -> ReportCaseInputs:
    """Fill the case inputs *stated* leaves unstated from *claims*.

    The mapping (CSAF-03):

    - the name is ``document.title`` and the summary the document-level
      ``summary`` note, else the ``description`` note (CSAF-03-007);
    - the proposed embargo end is the earliest ``disclosure_date`` later than
      *reference_time* (CSAF-03-001, CSAF-03-002), unless the document also
      sets P, X or A;
    - a ``disclosure_date`` no later than *reference_time* sets P
      (CSAF-03-003);
    - SSVC Exploitation ``PoC`` sets X and ``Active`` sets A, and ``None``
      sets nothing (CSAF-03-004);
    - an entry in ``first_known_exploitation_dates`` sets A (CSAF-03-005);
    - each vulnerability with a ``cve`` or an ``ids`` entry becomes a
      vulnerability item (CSAF-03-008), and each document-level reference a
      case reference (CSAF-03-009).

    A value *stated* gives beats the document's, which is then recorded
    ``OVERRIDDEN`` (CSAF-02-003); a past ``disclosure_date`` still sets P,
    because no Vultron field states P.  When the document sets P, X or A,
    the case starts with no embargo (EP-04-020): no embargo end is
    returned, not even a stated one, and the future dates stay display
    only, neither applied nor overridden.

    Args:
        claims: What the attached document claims.
        reference_time: The instant the dates are measured against: the
            CASE_MANAGER's receipt of the proposal that carries the Offer,
            never the Offer's ``published`` (CLP-15-003), or the
            submit-report trigger's "now".
        stated: What the Offer and its report state; ``None`` when they
            state none of these values.

    Raises:
        ValueError: when *reference_time* has no time zone.
    """
    _require_aware(reference_time)
    stated = stated or StatedReportFields()
    if not fills_case_inputs(claims):
        return ReportCaseInputs.from_stated(stated)
    outcomes: dict[str, ClaimOutcome] = {}
    name = _stated_or_claimed("name", stated.name, claims.name, outcomes)
    summary = _stated_or_claimed(
        "summary", stated.summary, claims.summary, outcomes
    )
    states = [
        _vul_state(vul, reference_time) for vul in claims.vulnerabilities
    ]
    future_dates = [
        s.future_disclosure_date
        for s in states
        if s.future_disclosure_date is not None
    ]
    eligible = not any(
        s.public or s.exploit_public or s.attacks_observed for s in states
    )
    # A case that starts with P, X or A takes no embargo (EP-04-020), so no
    # future date becomes its proposed end then: the record must not call a
    # date applied that the case never took.
    earliest = min(future_dates) if future_dates and eligible else None
    for index, (vul, state) in enumerate(
        zip(claims.vulnerabilities, states, strict=True)
    ):
        prefix = f"vulnerabilities[{index}]."
        if state.public:
            outcomes[f"{prefix}disclosure_date"] = ClaimOutcome.APPLIED
        elif state.future_disclosure_date is not None and eligible:
            if stated.proposed_embargo_end is not None:
                outcomes[f"{prefix}disclosure_date"] = ClaimOutcome.OVERRIDDEN
            elif earliest is not None and (
                state.future_disclosure_date == earliest
            ):
                outcomes[f"{prefix}disclosure_date"] = ClaimOutcome.APPLIED
        if _exploitation(vul) in _STATES_SOMETHING:
            outcomes[f"{prefix}exploitation"] = ClaimOutcome.APPLIED
        for i in range(len(vul.first_known_exploitation_dates)):
            outcomes[f"{prefix}first_known_exploitation_dates[{i}]"] = (
                ClaimOutcome.APPLIED
            )
    item_vulnerabilities = _item_outcomes(claims, outcomes)
    return ReportCaseInputs(
        name=name,
        summary=summary,
        # No embargo end at all when the case starts with P, X or A: the
        # stated one is not taken either (EP-04-020).
        proposed_embargo_end=(
            stated.proposed_embargo_end
            if stated.proposed_embargo_end is not None and eligible
            else earliest
        ),
        public=any(s.public for s in states),
        exploit_public=any(s.exploit_public for s in states),
        attacks_observed=any(s.attacks_observed for s in states),
        item_vulnerabilities=item_vulnerabilities,
        references=list(claims.references),
        outcomes=outcomes,
        filled_from_document=True,
    )


def _case_split_signal(
    claims: ReportClaims, reference_time: datetime
) -> CaseSplitSignal | None:
    states = [
        _vul_state(vul, reference_time) for vul in claims.vulnerabilities
    ]
    if len(states) < 2:
        return None
    readers = {
        CaseSplitDifference.PUBLIC_STATUS: lambda s: s.public,
        CaseSplitDifference.EXPLOIT_PUBLIC: lambda s: s.exploit_public,
        CaseSplitDifference.ATTACKS_OBSERVED: lambda s: s.attacks_observed,
        CaseSplitDifference.FUTURE_DISCLOSURE_DATE: (
            lambda s: s.future_disclosure_date
        ),
    }
    differs = [
        difference
        for difference, read in readers.items()
        if len({read(s) for s in states}) > 1
    ]
    return CaseSplitSignal(differs_in=differs) if differs else None


def _same_party_name(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def _candidate_parties_signal(
    claims: ReportClaims, receiver_name: str | None
) -> CandidatePartiesSignal | None:
    others = [
        vendor
        for vendor in claims.known_affected_vendors
        if receiver_name is None or not _same_party_name(vendor, receiver_name)
    ]
    return CandidatePartiesSignal(vendors=others) if others else None


def claims_signals(
    claims: ReportClaims,
    *,
    reference_time: datetime,
    receiver_name: str | None,
) -> tuple[CaseSplitSignal | None, CandidatePartiesSignal | None]:
    """Return the case-split and candidate-parties signals *claims* raise.

    The case-split signal names each way the document's vulnerabilities
    differ: public status, X, A, or future disclosure date (CSAF-04-006).
    The candidate-parties signal names the known-affected vendors other than
    the receiver; there is one when those vendors are several, or include a
    vendor whose name is not *receiver_name*, compared without regard to case
    or surrounding space (CSAF-04-007).  A receiver with no ``name`` differs
    from every vendor.  A document of any category raises them: a signal
    changes no case data and never acts (CSAF-04-008), so the limit of
    CSAF-02-002 does not apply to it.

    Raises:
        ValueError: when *reference_time* has no time zone.
    """
    _require_aware(reference_time)
    return (
        _case_split_signal(claims, reference_time),
        _candidate_parties_signal(claims, receiver_name),
    )


__all__ = [
    "CSAF_VULNERABILITY_REPORT",
    "ReportCaseInputs",
    "SSVC_EXPLOITATION_KEYS",
    "StatedReportFields",
    "case_inputs_from_claims",
    "case_reference_from_claim",
    "claims_signals",
    "fills_case_inputs",
    "makes_vulnerability_item",
    "vulnerability_item_from_claims",
]
