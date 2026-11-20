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

One mapping, in two halves, serves every side of a report:

- :func:`proposed_case_inputs_from_claims` is the half that judges no date,
  so a proposal can carry its result as ``caseInputs`` (CP-01-022, CP-01-023);
- :func:`case_inputs_from_proposal` is the date step, which judges the
  disclosure date at a reference time (CSAF-03-001, CSAF-03-003);
- :func:`case_inputs_from_claims` composes the two and names what became of
  each claimed value (CSAF-04-004);
- :func:`proposed_claim_outcomes` names the values the first half used, for
  the record of a report receiver that carries them on its proposal.

The CASE_MANAGER runs the date step at the instant it creates a case from a
proposal: on the proposal's ``caseInputs`` when it carries them (CP-01-024),
else on its own reading of the carried Offer's document (CP-01-025).  The
Reporter's submit-report trigger fills the report name, summary and proposed
embargo end its request leaves unstated, measured against its own "now"
(CSAF-04-010).  The reference time is a parameter, so no caller reads a clock
below its act's edge (ADR-0176).
A value the Offer or the report states always wins over the document's
(CSAF-02-003), and only a document of category ``csaf_vulnerability_report``
fills anything (CSAF-02-001, CSAF-02-002).

:func:`claims_signals` raises the receiver-local case-split and
candidate-parties signals (CSAF-04-006, CSAF-04-007).  A signal only shows
that a split or a party may be needed; nothing here acts on one
(CSAF-04-008).
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models._helpers import timestamp_serializer
from vultron.core.models.case_proposal import (
    ProposedCaseInputs,
    ProposedVulnerabilityItem,
)
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
    ClaimsReading,
    ReportClaims,
    VulnerabilityClaims,
)
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
    VulnerabilityItemNote,
    ids_from_csaf,
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
    """A new case's inputs, with the disclosure date judged.

    Filled from a report's document (:func:`case_inputs_from_claims`) or from
    a proposal's ``caseInputs`` (:func:`case_inputs_from_proposal`).  From a
    document, ``name``, ``summary`` and ``proposed_embargo_end`` are the
    stated value when there is one, else the document's; from ``caseInputs``,
    the proposer's.  ``proposed_embargo_end`` is ``None`` when P, X or A is
    set, since the case then starts with no embargo (EP-04-020).
    ``public``, ``exploit_public`` and ``attacks_observed`` are the P, X and
    A: what a document states for any of its vulnerabilities, or the X and A
    ``caseInputs`` state and the P its disclosure date gives; no field of the
    report or Offer states them.  ``outcomes`` names
    each document value this mapping used (``APPLIED``) or set aside for a
    stated one (``OVERRIDDEN``); a value it names nowhere stays display only
    (CSAF-04-004).  ``filled_from_document`` is ``False`` when the document
    may fill nothing (CSAF-02-002): the stated fields then pass through and
    no outcome is given.

    ``proposed_items`` are the case's vulnerability items and
    ``reference_links`` its references, as content with no id: from a
    document, its vulnerabilities with a ``cve`` or an ``ids`` entry
    (CSAF-03-008) and its document-level references (CSAF-03-009).  The
    case's creator builds the objects (:func:`vulnerability_item_from_proposed`,
    :func:`case_reference_from_link`), so this mapping mints no id.
    """

    model_config = ConfigDict(frozen=True)

    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    proposed_embargo_end: datetime | None = None
    public: bool = False
    exploit_public: bool = False
    attacks_observed: bool = False
    proposed_items: list[ProposedVulnerabilityItem] = Field(
        default_factory=list
    )
    reference_links: list[CaseReferenceLink] = Field(default_factory=list)
    outcomes: dict[NonEmptyString, ClaimOutcome] = Field(default_factory=dict)
    filled_from_document: bool = False

    _serialize_proposed_embargo_end = timestamp_serializer(
        "proposed_embargo_end"
    )

    @classmethod
    def from_stated(cls, stated: StatedReportFields) -> ReportCaseInputs:
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


def filling_reading(
    readings: Sequence[ClaimsReading],
) -> ClaimsReading | None:
    """The one reading that fills case inputs: the first of the right category.

    A report may carry several CSAF documents.  Only the first of category
    ``csaf_vulnerability_report`` speaks for the case; every other value stays
    display only, so two documents never compete for one input
    (CSAF-02-001).
    """
    return next((r for r in readings if fills_case_inputs(r.claims)), None)


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


def _exploit_public(vul: VulnerabilityClaims) -> bool:
    """SSVC Exploitation ``PoC`` sets X (CSAF-03-004)."""
    return _exploitation(vul) is SSVC_2_Exploitation.POC


def _attacks_observed(vul: VulnerabilityClaims) -> bool:
    """``Active``, or a first known exploitation date, sets A (CSAF-03-005)."""
    return _exploitation(vul) is SSVC_2_Exploitation.ACTIVE or bool(
        vul.first_known_exploitation_dates
    )


def _vul_state(
    vul: VulnerabilityClaims, reference_time: datetime
) -> _VulState:
    future = _is_future(vul.disclosure_date, reference_time)
    return _VulState(
        public=vul.disclosure_date is not None and not future,
        exploit_public=_exploit_public(vul),
        attacks_observed=_attacks_observed(vul),
        future_disclosure_date=vul.disclosure_date if future else None,
    )


def makes_vulnerability_item(vul: VulnerabilityClaims) -> bool:
    """Whether *vul* names its vulnerability, so it becomes an item.

    A vulnerability item is what later messages and projections refer to
    (CM-05-003), so an entry with neither a ``cve`` nor an ``ids`` entry
    makes none (CSAF-03-008).
    """
    return vul.cve is not None or bool(vul.ids)


def reference_link_from_claim(claim: ClaimedReference) -> CaseReferenceLink:
    """The Link a claimed reference states for the case (CSAF-03-009).

    The claim's ``url`` is the Link's ``href`` and its ``summary`` the
    Link's ``name``.  The Link carries no ``rel``: a CSAF reference says
    nothing of what kind of resource it names, and its ``category``
    (``self`` or ``external``) is about the document, not the resource.
    """
    return CaseReferenceLink(href=claim.url, name=claim.summary)


def case_reference_from_link(
    link: CaseReferenceLink, *, published: datetime
) -> CaseReference:
    """The case reference a stated Link becomes (CSAF-03-009, CP-01-024).

    The reference's ``url`` is the Link without its ``name``, which becomes
    the reference's own ``name``.  *published* is the instant of the act
    that creates it (ADR-0176).
    """
    return CaseReference(
        url=CaseReferenceLink(
            href=link.href, media_type=link.media_type, rel=list(link.rel)
        ),
        name=link.name,
        published=published,
        updated=published,
    )


def case_reference_from_claim(
    claim: ClaimedReference, *, published: datetime
) -> CaseReference:
    """The case reference a claimed reference becomes (CSAF-03-009).

    The claim's ``url`` is the ``href`` of the reference's ``url`` Link and
    its ``summary`` the reference's ``name``
    (:func:`reference_link_from_claim`, :func:`case_reference_from_link`).
    *published* is the instant of the act that creates it (ADR-0176).
    """
    return case_reference_from_link(
        reference_link_from_claim(claim), published=published
    )


def proposed_item_from_claims(
    vul: VulnerabilityClaims,
) -> ProposedVulnerabilityItem:
    """The vulnerability item *vul* states, with no id yet (CSAF-03-008).

    Its ``ids`` and ``notes`` are copied as claimed, its ``cve`` becoming
    the first ``ids`` entry, with system ``CVE`` (CM-05-018,
    :func:`ids_from_csaf`), and its ``title`` becoming the item's AS2
    ``name`` (CM-05-018); no identifier is interpreted (CM-05-008).  The
    item's names differ from CSAF's where a wire name would mean two things
    (VM-10-012): an id's ``text`` is its ``identifier``, the ``notes`` are
    the item's ``vul_notes``, and a note's ``text``, ``title`` and
    ``audience`` are its ``content``, ``name`` and ``intended_audience``.
    Each of its references becomes a Link (:func:`reference_link_from_claim`).

    Raises:
        ValueError: when *vul* names no vulnerability
            (:func:`makes_vulnerability_item`).
    """
    if not makes_vulnerability_item(vul):
        raise ValueError(
            "a CSAF vulnerability with no cve and no ids names no"
            " vulnerability, so it makes no vulnerability item (CSAF-03-008)"
        )
    return ProposedVulnerabilityItem(
        ids=ids_from_csaf(
            vul.cve,
            (
                VulnerabilityItemId(
                    system_name=i.system_name, identifier=i.text
                )
                for i in vul.ids
            ),
        ),
        name=vul.title,
        vul_notes=[
            VulnerabilityItemNote(
                category=note.category,
                content=note.text,
                name=note.title,
                intended_audience=note.audience,
            )
            for note in vul.notes
        ],
        reference_links=[reference_link_from_claim(r) for r in vul.references],
    )


def vulnerability_item_from_proposed(
    item: ProposedVulnerabilityItem, *, published: datetime
) -> VulnerabilityItem:
    """The vulnerability item a stated item becomes, field for field.

    Each of its Links becomes a case reference held inline on the item
    (:func:`case_reference_from_link`).  The item and its references are
    stamped *published*, the instant of the act that creates them
    (ADR-0176); the item's id is minted here.
    """
    return VulnerabilityItem(
        ids=list(item.ids),
        name=item.name,
        vul_notes=list(item.vul_notes),
        references=[
            case_reference_from_link(link, published=published)
            for link in item.reference_links
        ],
        published=published,
        updated=published,
    )


def vulnerability_item_from_claims(
    vul: VulnerabilityClaims, *, published: datetime
) -> VulnerabilityItem:
    """The vulnerability item *vul* becomes, field for field (CSAF-03-008).

    :func:`proposed_item_from_claims`, then
    :func:`vulnerability_item_from_proposed`.

    Raises:
        ValueError: when *vul* names no vulnerability
            (:func:`makes_vulnerability_item`).
    """
    return vulnerability_item_from_proposed(
        proposed_item_from_claims(vul), published=published
    )


def _item_outcomes(
    claims: ReportClaims, outcomes: dict[str, ClaimOutcome]
) -> None:
    """Mark the values the case's items and references take ``APPLIED``.

    The document-level references all become case references (CSAF-03-009);
    a vulnerability's identity fields become its item's only when it names
    the vulnerability (CSAF-03-008), and otherwise stay display only.
    """
    for index in range(len(claims.references)):
        outcomes[f"references[{index}]"] = ClaimOutcome.APPLIED
    for index, vul in enumerate(claims.vulnerabilities):
        if not makes_vulnerability_item(vul):
            continue
        prefix = f"vulnerabilities[{index}]."
        if vul.cve is not None:
            outcomes[f"{prefix}cve"] = ClaimOutcome.APPLIED
        if vul.title is not None:
            outcomes[f"{prefix}title"] = ClaimOutcome.APPLIED
        for name in ("ids", "notes", "references"):
            for i in range(len(getattr(vul, name))):
                outcomes[f"{prefix}{name}[{i}]"] = ClaimOutcome.APPLIED


def _stated_or_claimed(
    path: str,
    stated: str | None,
    claimed: str | None,
    outcomes: dict[str, ClaimOutcome],
) -> str | None:
    """Take *stated* over *claimed*, recording the claim's outcome at *path*."""
    if claimed is not None:
        outcomes[path] = (
            ClaimOutcome.APPLIED if stated is None else ClaimOutcome.OVERRIDDEN
        )
    return _prefer_stated(stated, claimed)


def _prefer_stated(stated: str | None, claimed: str | None) -> str | None:
    """*stated* when it is given, else *claimed* (CSAF-02-003)."""
    return stated if stated is not None else claimed


def proposed_case_inputs_from_claims(
    claims: ReportClaims, *, stated: StatedReportFields | None = None
) -> ProposedCaseInputs:
    """The case inputs *claims* state, with no date judged (CP-01-023).

    The part of the CSAF-03 mapping that needs no reference time: the name
    and summary (CSAF-03-006, CSAF-03-007), X and A (CSAF-03-004,
    CSAF-03-005), the vulnerability items (CSAF-03-008), the references
    (CSAF-03-009) and the earliest ``disclosure_date`` as the document
    states it.  A name or summary *stated* gives beats the document's
    (CSAF-02-003).  Reads no clock, so a report receiver can carry the
    result on its proposal as ``caseInputs`` (CP-01-022) and the
    CASE_MANAGER judges the date when it builds the case
    (:func:`case_inputs_from_proposal`).  A document of any category but
    ``csaf_vulnerability_report`` states nothing (CSAF-02-002): only the
    stated name and summary are returned.
    """
    stated = stated or StatedReportFields()
    if not fills_case_inputs(claims):
        return ProposedCaseInputs(name=stated.name, summary=stated.summary)
    dates = [
        vul.disclosure_date
        for vul in claims.vulnerabilities
        if vul.disclosure_date is not None
    ]
    return ProposedCaseInputs(
        name=_prefer_stated(stated.name, claims.name),
        summary=_prefer_stated(stated.summary, claims.summary),
        exploit_public=any(_exploit_public(v) for v in claims.vulnerabilities),
        attacks_observed=any(
            _attacks_observed(v) for v in claims.vulnerabilities
        ),
        proposed_items=[
            proposed_item_from_claims(vul)
            for vul in claims.vulnerabilities
            if makes_vulnerability_item(vul)
        ],
        reference_links=[
            reference_link_from_claim(ref) for ref in claims.references
        ],
        disclosure_date=min(dates) if dates else None,
    )


def case_inputs_from_proposal(
    proposed: ProposedCaseInputs,
    *,
    reference_time: datetime,
    proposed_embargo_end: datetime | None = None,
) -> ReportCaseInputs:
    """Judge *proposed*'s disclosure date at *reference_time*: the date step.

    The one step both sources of a new case's inputs pass through: a
    proposal's ``caseInputs`` (CP-01-024) and the CASE_MANAGER's own reading
    of the carried Offer's CSAF document (CP-01-025,
    :func:`case_inputs_from_claims`).

    - A ``disclosure_date`` no later than *reference_time* sets P
      (CSAF-03-003); one later is the proposed embargo end (CSAF-03-001),
      unless *proposed_embargo_end*, the end of the Offer's own
      ``proposedEmbargo``, is given, which beats it (CSAF-02-003).
    - When P, X or A is set, the case starts with no embargo (EP-04-020):
      no end is returned, not even *proposed_embargo_end*.

    Every other input passes through as stated: an empty item list or a
    false X stays so (CP-01-024).  No outcome is given and
    ``filled_from_document`` is ``False``: no document was read.

    Raises:
        ValueError: when *reference_time* has no time zone.
    """
    _require_aware(reference_time)
    date = proposed.disclosure_date
    judged = ReportCaseInputs(
        name=proposed.name,
        summary=proposed.summary,
        public=date is not None and not _is_future(date, reference_time),
        exploit_public=proposed.exploit_public,
        attacks_observed=proposed.attacks_observed,
        proposed_items=list(proposed.proposed_items),
        reference_links=list(proposed.reference_links),
    )
    if not judged.embargo_eligible:
        return judged
    end = proposed_embargo_end if proposed_embargo_end is not None else date
    return judged.model_copy(update={"proposed_embargo_end": end})


def _undated_outcomes(
    claims: ReportClaims, stated: StatedReportFields
) -> dict[str, ClaimOutcome]:
    """The outcomes of every value the mapping uses that is not a date.

    The name and summary, the SSVC Exploitation values that set X or A, the
    first known exploitation dates, and the values the items and references
    take (CSAF-03-004 to CSAF-03-009).  Shared by the receiver's
    :func:`proposed_claim_outcomes` and the CASE_MANAGER's
    :func:`case_inputs_from_claims`, which add the disclosure dates.
    """
    outcomes: dict[str, ClaimOutcome] = {}
    _stated_or_claimed("name", stated.name, claims.name, outcomes)
    _stated_or_claimed("summary", stated.summary, claims.summary, outcomes)
    for index, vul in enumerate(claims.vulnerabilities):
        prefix = f"vulnerabilities[{index}]."
        if _exploitation(vul) in _STATES_SOMETHING:
            outcomes[f"{prefix}exploitation"] = ClaimOutcome.APPLIED
        for i in range(len(vul.first_known_exploitation_dates)):
            outcomes[f"{prefix}first_known_exploitation_dates[{i}]"] = (
                ClaimOutcome.APPLIED
            )
    _item_outcomes(claims, outcomes)
    return outcomes


def proposed_claim_outcomes(
    claims: ReportClaims, *, stated: StatedReportFields | None = None
) -> dict[str, ClaimOutcome]:
    """Name each value :func:`proposed_case_inputs_from_claims` used.

    What a report receiver's own record marks once it has carried the
    document's values on its proposal as ``caseInputs`` (CSAF-04-004): a
    value it took is ``APPLIED``, a name or summary *stated* beats is
    ``OVERRIDDEN``.  The earliest ``disclosure_date`` is ``APPLIED`` because
    the proposal carries it, unjudged (CP-01-023); a later one stays display
    only.  Reads no clock.  A document of any category but
    ``csaf_vulnerability_report`` fills nothing, so no outcome is given
    (CSAF-02-002).
    """
    stated = stated or StatedReportFields()
    if not fills_case_inputs(claims):
        return {}
    outcomes = _undated_outcomes(claims, stated)
    dates = [
        vul.disclosure_date
        for vul in claims.vulnerabilities
        if vul.disclosure_date is not None
    ]
    earliest = min(dates) if dates else None
    for index, vul in enumerate(claims.vulnerabilities):
        if earliest is not None and vul.disclosure_date == earliest:
            outcomes[f"vulnerabilities[{index}].disclosure_date"] = (
                ClaimOutcome.APPLIED
            )
    return outcomes


def _claim_outcomes(
    claims: ReportClaims,
    *,
    stated: StatedReportFields,
    reference_time: datetime,
    eligible: bool,
) -> dict[str, ClaimOutcome]:
    """Name each document value the mapping used or set aside (CSAF-04-004).

    A past ``disclosure_date`` is ``APPLIED``: it sets P.  A future one is
    ``OVERRIDDEN`` by a stated embargo end, ``APPLIED`` when it is the
    earliest and none is stated, and display only when the case starts with
    P, X or A, since the case then takes no embargo end (EP-04-020).
    """
    outcomes = _undated_outcomes(claims, stated)
    states = [
        _vul_state(vul, reference_time) for vul in claims.vulnerabilities
    ]
    future_dates = [
        s.future_disclosure_date
        for s in states
        if s.future_disclosure_date is not None
    ]
    earliest = min(future_dates) if future_dates and eligible else None
    for index, state in enumerate(states):
        path = f"vulnerabilities[{index}].disclosure_date"
        if state.public:
            outcomes[path] = ClaimOutcome.APPLIED
        elif state.future_disclosure_date is not None and eligible:
            if stated.proposed_embargo_end is not None:
                outcomes[path] = ClaimOutcome.OVERRIDDEN
            elif state.future_disclosure_date == earliest:
                outcomes[path] = ClaimOutcome.APPLIED
    return outcomes


def case_inputs_from_claims(
    claims: ReportClaims,
    *,
    reference_time: datetime,
    stated: StatedReportFields | None = None,
) -> ReportCaseInputs:
    """Fill the case inputs *stated* leaves unstated from *claims*.

    The mapping (CSAF-03) is :func:`proposed_case_inputs_from_claims`, which
    judges no date, then the date step :func:`case_inputs_from_proposal`:

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
            CASE_MANAGER's creation of the case from the proposal that
            carries the Offer, never the Offer's ``published`` (CLP-15-003),
            or the submit-report trigger's "now".
        stated: What the Offer and its report state; ``None`` when they
            state none of these values.

    Raises:
        ValueError: when *reference_time* has no time zone.
    """
    _require_aware(reference_time)
    stated = stated or StatedReportFields()
    if not fills_case_inputs(claims):
        return ReportCaseInputs.from_stated(stated)
    inputs = case_inputs_from_proposal(
        proposed_case_inputs_from_claims(claims, stated=stated),
        reference_time=reference_time,
        proposed_embargo_end=stated.proposed_embargo_end,
    )
    return inputs.model_copy(
        update={
            "outcomes": _claim_outcomes(
                claims,
                stated=stated,
                reference_time=reference_time,
                eligible=inputs.embargo_eligible,
            ),
            "filled_from_document": True,
        }
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
    "case_inputs_from_proposal",
    "case_reference_from_claim",
    "case_reference_from_link",
    "claims_signals",
    "filling_reading",
    "fills_case_inputs",
    "makes_vulnerability_item",
    "proposed_case_inputs_from_claims",
    "proposed_claim_outcomes",
    "proposed_item_from_claims",
    "reference_link_from_claim",
    "vulnerability_item_from_claims",
    "vulnerability_item_from_proposed",
]
