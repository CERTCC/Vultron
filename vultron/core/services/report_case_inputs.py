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

from vultron.core.models.report_claims import (
    CandidatePartiesSignal,
    CaseSplitDifference,
    CaseSplitSignal,
    ClaimOutcome,
    ReportClaims,
    VulnerabilityClaims,
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


class ReportCaseInputs(BaseModel):
    """The case inputs a report states, filled from its document.

    ``name``, ``summary`` and ``proposed_embargo_end`` are the stated value
    when there is one, else the document's.  ``public``, ``exploit_public``
    and ``attacks_observed`` are the P, X and A the document states for any
    of its vulnerabilities; no Vultron field states them.  ``outcomes`` names
    each document value this mapping used (``APPLIED``) or set aside for a
    stated one (``OVERRIDDEN``); a value it names nowhere stays display only
    (CSAF-04-004).  ``filled_from_document`` is ``False`` when the document
    may fill nothing (CSAF-02-002): the stated fields then pass through and
    no outcome is given.
    """

    model_config = ConfigDict(frozen=True)

    name: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    proposed_embargo_end: datetime | None = None
    public: bool = False
    exploit_public: bool = False
    attacks_observed: bool = False
    outcomes: dict[NonEmptyString, ClaimOutcome] = Field(default_factory=dict)
    filled_from_document: bool = False

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
    - an entry in ``first_known_exploitation_dates`` sets A (CSAF-03-005).

    A value *stated* gives beats the document's, which is then recorded
    ``OVERRIDDEN`` (CSAF-02-003); a past ``disclosure_date`` still sets P,
    because no Vultron field states P.  When the document sets P, X or A,
    the case starts with no embargo (EP-04-020), so no future date is taken
    as its end, and those dates stay display only.

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
        return ReportCaseInputs(
            name=stated.name,
            summary=stated.summary,
            proposed_embargo_end=stated.proposed_embargo_end,
        )
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
        elif state.future_disclosure_date is not None:
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
    return ReportCaseInputs(
        name=name,
        summary=summary,
        proposed_embargo_end=(
            stated.proposed_embargo_end
            if stated.proposed_embargo_end is not None
            else earliest
        ),
        public=any(s.public for s in states),
        exploit_public=any(s.exploit_public for s in states),
        attacks_observed=any(s.attacks_observed for s in states),
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
    from every vendor.  A document that may fill no case input raises no
    signal (CSAF-02-002).

    Raises:
        ValueError: when *reference_time* has no time zone.
    """
    _require_aware(reference_time)
    if not fills_case_inputs(claims):
        return None, None
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
    "claims_signals",
    "fills_case_inputs",
]
