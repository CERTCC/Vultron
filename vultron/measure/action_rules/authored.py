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
"""The authored action rules: the claim (ADR-0216, SHD-05-006).

Each pattern and action of ``CS_ACTION_RULES`` carries over as one or more
authored rules, in that table's order, each recording its source pair
(SHD-05-006, SHD-05-022).  The decisions behind each rule are the user's,
rule by rule, on #6676 (D1 to D17 there):

* A publication is any publication and always a valid action: only the
  first causes P (D1).  A public exploit makes the public aware, but that is
  not a publication (D10), so every publication rule names its member of
  ``Actions`` and the comparison decides, position by position, whether it
  is the move ``cs.public_becomes_aware``.
* A rule suggests and never forbids, so a costly rule, such as publishing
  before the vendor is aware, stays (D2).
* The Vulnerabilities Equities Process pair does not carry over (D3).
* A rule is narrowed with RM, EM or PEC parts where those states change
  what it is, and never widened (D4).  A rule whose CS pattern matches a
  state where an ephemeral state forces another event (``pX``) is split so
  it matches only positions where its move exists.
* Closing the case is ``rm.close`` for a participant whose RM state is not
  Closed, matched only where ``rm.close`` exists (``RM_CLOSABLE``) (D5); it
  is housekeeping, with no desideratum (D16).
* Every rule has a reason; it names desiderata only where its reason is one
  (D10, D11).  The reasons quote the legacy table where it has one.
* Ending the embargo once the public knows, an exploit is public or attacks
  are seen stays as a rule: Vultron ends it then, but the protocol only says
  it should (D8, #6709).
* The embargo rules carry the documentation's advice on terms: accept the
  shortest proposal, propose a revision to extend, propose shorter terms,
  and reject rarely (D14, ``docs/topics/process_models/em/defaults.md``).

"Non-vendor" is :data:`NON_VENDOR`.  The table is built on first use
(:func:`authored_rules`): checking a desideratum against the move-advice list
walks the chance model.
"""

from __future__ import annotations

from functools import cache

from vultron.core.scoring.potential_actions import Actions
from vultron.core.states.em import EM, EM_EMBARGO_ACTIVE
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM, RM_CLOSABLE
from vultron.enums.roles import CVDRole
from vultron.measure.action_rules.model import (
    ANY_ROLE,
    AuthoredRule,
    Roles,
    RulePattern,
    SourcePair,
)

NON_VENDOR: frozenset[CVDRole] = frozenset(
    {CVDRole.REPORTER, CVDRole.DEPLOYER, CVDRole.COORDINATOR}
)
"""The roles of the source table's "non-vendor": a participant other than the
vendor that acts in the case."""

NOT_THE_OWNER: frozenset[CVDRole] = frozenset(
    {
        CVDRole.REPORTER,
        CVDRole.VENDOR,
        CVDRole.DEPLOYER,
        CVDRole.COORDINATOR,
    }
)
"""The roles that ask the case owner to end an embargo rather than end it."""

_OWNER: frozenset[CVDRole] = frozenset({CVDRole.CASE_OWNER})
_VENDOR: frozenset[CVDRole] = frozenset({CVDRole.VENDOR})
_DEPLOYER: frozenset[CVDRole] = frozenset({CVDRole.DEPLOYER})

_IN_FORCE = frozenset(EM_EMBARGO_ACTIVE)
_NOT_STARTED = frozenset({EM.NONE, EM.PROPOSED})
_NO_ACTIVE_EMBARGO = frozenset({EM.NONE, EM.EXITED})
_FIX_GATE = frozenset({RM.ACCEPTED, RM.DEFERRED})
_CLOSABLE = frozenset(RM_CLOSABLE)
_INVITED = frozenset({EmbargoConsentState.INVITED})

#: The documentation's advice on embargo terms (D14).
_TERMS_ADVICE = (
    "the shortest proposed embargo wins: accept the shorter proposal and"
    " negotiate a longer one by revision"
    " (docs/topics/process_models/em/defaults.md)"
)
#: R16's reason: publishing before any vendor is aware stays unconditional
#: (D2), and is mostly worth it when the case has no vendor to wait for.
_R16_REASON = "Defense; mostly relevant when no vendor is in the case"

_REJECT_REASON = (
    f"Coordination; rejection is rarely the advised answer: {_TERMS_ADVICE}"
)


def _carry(
    source: str,
    source_action: Actions,
    *,
    reason: str,
    action: Actions | str | None = None,
    roles: Roles = ANY_ROLE,
    desiderata: tuple[str, ...] = (),
    cs: str | None = None,
    rm: frozenset[RM] | None = None,
    em: frozenset[EM] | None = None,
    proposal: frozenset[EmbargoConsentState] | None = None,
    blind_spot: int | None = None,
) -> AuthoredRule:
    """One carried-over rule from the pair *source*, *source_action*.

    *action* defaults to *source_action*, and the CS part *cs* to the
    source pattern.
    """
    return AuthoredRule(
        pattern=RulePattern(cs=cs or source, rm=rm, em=em, proposal=proposal),
        roles=roles,
        action=source_action if action is None else action,
        reason=reason,
        desiderata=desiderata,
        source=SourcePair(pattern=source, action=source_action),
        blind_spot=blind_spot,
    )


def _terminate(source: str, event: str) -> AuthoredRule:
    return _carry(
        source,
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        action="em.terminate",
        roles=_OWNER,
        em=_IN_FORCE,
        reason=f"Exit criteria met: {event}",
    )


def _ask_to_terminate(
    source: str, event: str
) -> tuple[AuthoredRule, AuthoredRule]:
    return (
        _carry(
            source,
            Actions.INITIATE_EMBARGO_TERMINATION,
            action="em.terminate",
            roles=_OWNER,
            em=_IN_FORCE,
            reason=f"Exit criteria met: {event}",
        ),
        _carry(
            source,
            Actions.INITIATE_EMBARGO_TERMINATION,
            roles=NOT_THE_OWNER,
            em=_IN_FORCE,
            reason=(
                f"Exit criteria met: {event}; ask the case owner to end the"
                " embargo"
            ),
        ),
    )


def _embargo_moves(em: EM) -> list[AuthoredRule]:
    """``..dpxa`` "negotiate or establish an embargo", split by EM (D4, D14)."""
    source = "..dpxa"
    negotiate = Actions.NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO
    at = frozenset({em})
    if em is EM.NONE:
        return [
            _carry(
                source,
                negotiate,
                action="em.propose",
                em=at,
                reason="Coordination: propose an embargo",
                desiderata=("E≺P", "D≺P"),
            )
        ]
    if em is EM.ACTIVE:
        return [
            _carry(
                source,
                negotiate,
                action="em.propose",
                em=at,
                reason=(
                    "Coordination: to extend the embargo, propose a revision"
                    " (docs/topics/process_models/em/defaults.md)"
                ),
                desiderata=("D≺P",),
                blind_spot=6492,
            )
        ]
    starts = em is EM.PROPOSED
    served = ("E≺P", "D≺P") if starts else ("D≺P",)
    what = "proposed embargo" if starts else "proposed revision"
    return [
        _carry(
            source,
            negotiate,
            action="em.accept",
            roles=_OWNER,
            em=at,
            reason=f"Coordination: accept the {what}; {_TERMS_ADVICE}",
            desiderata=served,
        ),
        _carry(
            source,
            negotiate,
            action="em.reject",
            roles=_OWNER,
            em=at,
            reason=_REJECT_REASON,
        ),
        _carry(
            source,
            negotiate,
            action="em.propose",
            em=at,
            reason=(
                f"Coordination: to shorten the {what}, propose shorter"
                f" terms; {_TERMS_ADVICE}"
            ),
        ),
        _carry(
            source,
            negotiate,
            action="pec.agree",
            roles=_VENDOR,
            em=at,
            proposal=_INVITED,
            reason=(
                f"Coordination: agree to the {what}; unscored until #6677"
            ),
            desiderata=served,
        ),
        _carry(
            source,
            negotiate,
            action="pec.decline",
            roles=_VENDOR,
            em=at,
            proposal=_INVITED,
            reason=f"{_REJECT_REASON}; unscored until #6677",
        ),
    ]


def _close(source: str, unless: str | None) -> AuthoredRule:
    reason = "Housekeeping: no action required"
    if unless is not None:
        reason = f"{reason} (unless monitoring for {unless})"
    return _carry(
        source,
        Actions.CLOSE_CASE,
        action="rm.close",
        rm=_CLOSABLE,
        reason=reason,
    )


@cache
def authored_rules() -> tuple[AuthoredRule, ...]:
    """The authored action rules, in the order of their source pairs in
    ``CS_ACTION_RULES``."""
    a = Actions
    return (
        # R1 ...P.. (D8, D9)
        _terminate("...P..", "the public is aware"),
        _carry(
            "...P..",
            a.PUBLISH_VULNERABILITY,
            reason="Defense; a record for future reference",
        ),
        # R2 ....X. (D8, D10, D11)
        _terminate("....X.", "an exploit is public"),
        _carry("....X.", a.PUBLISH_VULNERABILITY, reason="Defense"),
        _carry(
            "....X.",
            a.PUBLICIZE_PUBLISHED_EXPLOITS,
            reason="SA: draw attention to the published exploit",
        ),
        _carry(
            "....X.",
            a.MONITOR_FOR_EXPLOIT_REFINEMENT,
            reason="SA",
            desiderata=("F≺A",),
        ),
        _carry("....X.", a.PUBLISH_DETECTION_FOR_EXPLOITS, reason="Detection"),
        # R3 .....A (D8, D10, D11)
        _terminate(".....A", "attacks are observed"),
        _carry(".....A", a.PUBLISH_VULNERABILITY, reason="Defense"),
        _carry(".....A", a.MONITOR_FOR_ADDITIONAL_ATTACKS, reason="SA"),
        _carry(".....A", a.PUBLISH_DETECTION_FOR_ATTACKS, reason="Detection"),
        # R4 VfdpX., R5 Vfdp.A (D8)
        *_ask_to_terminate("VfdpX.", "an exploit is public"),
        *_ask_to_terminate("Vfdp.A", "attacks are observed"),
        # R6, R7 (D11)
        _carry(
            "....x.",
            a.MONITOR_FOR_EXPLOIT_PUBLICATION,
            reason="SA",
            desiderata=("F≺X", "D≺X"),
        ),
        _carry(
            ".....a",
            a.MONITOR_FOR_ATTACKS,
            reason="SA",
            desiderata=("F≺A", "D≺A"),
        ),
        # R8 vfdP..
        _carry(
            "vfdP..",
            a.PAY_ATTENTION_TO_PUBLIC_REPORTS,
            action="cs.vendor_becomes_aware",
            roles=_VENDOR,
            reason="SA",
            desiderata=("V≺X", "V≺A"),
        ),
        _carry(
            "vfdP..",
            a.ESCALATE_VENDOR_NOTIFICATION_PRIORITY,
            roles=NON_VENDOR,
            reason="Coordination",
            desiderata=("V≺X", "V≺A"),
        ),
        # R9 ...pxa: vigilance split by EM (D11 entry 9)
        _carry(
            "...pxa",
            a.MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA,
            em=_IN_FORCE,
            reason="SA: watch for the embargo's exit criteria",
            desiderata=("ExOwn≺P",),
        ),
        _carry(
            "...pxa",
            a.MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA,
            em=_NOT_STARTED,
            reason="SA: avoid entering an embargo that should not start",
        ),
        _carry(
            "...pxa",
            a.MAINTAIN_ANY_EXISTING_EMBARGO,
            em=_IN_FORCE,
            reason="Coordination",
            desiderata=("F≺P", "D≺P"),
        ),
        # R10 VfdP.. (D11 entry 10, D12)
        _carry(
            "VfdP..",
            a.ESCALATE_VIGILANCE_FOR_EXPLOITS,
            reason="SA",
            desiderata=("F≺X", "D≺X"),
        ),
        _carry(
            "VfdP..",
            a.ESCALATE_VIGILANCE_FOR_ATTACKS,
            reason="SA",
            desiderata=("F≺A", "D≺A"),
        ),
        _carry("VfdP..", a.PUBLISH_MITIGATION, reason="Defense"),
        _carry("VfdP..", a.PUBLICIZE_MITIGATION, reason="Defense"),
        _carry(
            "VfdP..",
            a.ESCALATE_FIX_PRIORITY,
            roles=NON_VENDOR,
            reason="Coordination",
            desiderata=("F≺X", "F≺A"),
        ),
        # R11 V..p..
        _carry(
            "V..p..",
            a.PUBLISH_VULNERABILITY,
            em=_NO_ACTIVE_EMBARGO,
            reason="Defense (if no active embargo)",
            desiderata=("P≺X", "P≺A"),
        ),
        _carry(
            "V..p..",
            a.PUBLISH_MITIGATION,
            em=_NO_ACTIVE_EMBARGO,
            reason="Defense (if no active embargo)",
            desiderata=("P≺X", "P≺A"),
        ),
        # R12 .fdP.. (D12)
        _carry(".fdP..", a.PUBLISH_MITIGATION, reason="Defense"),
        # R13 ...pX.: the exploit makes the public aware (D10)
        _carry("...pX.", a.PUBLISH_VULNERABILITY, reason="Defense"),
        _carry("...pX.", a.PUBLISH_MITIGATION, reason="Defense"),
        # R14 ...PX. (D9)
        _carry("...PX.", a.PUBLISH_VULNERABILITY, reason="Defense"),
        _carry("...PX.", a.PUBLISH_MITIGATION, reason="Defense"),
        # R15 ...p.A
        _carry(
            "...p.A",
            a.PUBLISH_VULNERABILITY,
            reason="Defense",
            desiderata=("P≺X",),
        ),
        _carry(
            "...p.A",
            a.PUBLISH_MITIGATION,
            reason="Defense",
            desiderata=("P≺X",),
        ),
        # R16 vfdp.. (D2: kept, unconditional; its cost shows in the advice)
        _carry(
            "vfdp..",
            a.PUBLISH_VULNERABILITY,
            reason=_R16_REASON,
            desiderata=("P≺X", "P≺A"),
        ),
        _carry(
            "vfdp..",
            a.PUBLISH_MITIGATION,
            reason=_R16_REASON,
            desiderata=("P≺X", "P≺A"),
        ),
        # R17 Vfd...: no F at VfdpX., where pX forces P
        _carry(
            "Vfd...",
            a.CREATE_FIX,
            action="cs.fix_is_ready",
            roles=_VENDOR,
            cs="Vfdpx.",
            rm=_FIX_GATE,
            reason="Defense",
            desiderata=("F≺P", "F≺X", "F≺A", "F_i≺ExOwn"),
        ),
        _carry(
            "Vfd...",
            a.CREATE_FIX,
            action="cs.fix_is_ready",
            roles=_VENDOR,
            cs="VfdP..",
            rm=_FIX_GATE,
            reason="Defense",
            desiderata=("F≺X", "F≺A"),
        ),
        _carry(
            "Vfd...",
            a.ENCOURAGE_VENDOR_TO_CREATE_FIX,
            roles=NON_VENDOR,
            reason="Coordination",
            desiderata=("F≺P", "F≺X", "F≺A"),
        ),
        # R18 VFd...: no D at VFdpX., where pX forces P
        _carry(
            "VFd...",
            a.DEPLOY_FIX,
            action="cs.fix_is_deployed",
            roles=_VENDOR,
            cs="VFdpx.",
            rm=_FIX_GATE,
            reason="Defense",
            desiderata=("D≺P", "D≺X", "D≺A"),
        ),
        _carry(
            "VFd...",
            a.DEPLOY_FIX,
            action="cs.fix_is_deployed",
            roles=_DEPLOYER,
            cs="VFdpx.",
            rm=_FIX_GATE,
            reason="Defense",
            desiderata=("D≺P", "D≺X", "D≺A"),
        ),
        _carry(
            "VFd...",
            a.DEPLOY_FIX,
            action="cs.fix_is_deployed",
            roles=_DEPLOYER,
            cs="VFdP..",
            rm=_FIX_GATE,
            reason="Defense",
            desiderata=("D≺X", "D≺A"),
        ),
        # R19 .fdPxA: narrowed to VfdPxA, where vP does not force V (D13)
        _carry(
            ".fdPxA",
            a.PUBLISH_EXPLOIT_CODE,
            action="cs.exploit_made_public",
            cs="VfdPxA",
            reason=(
                "Defense, Detection; usually a move of negative value: it"
                " costs F≺X and D≺X"
            ),
        ),
        # R20 VFdPxa
        _carry(
            "VFdPxa",
            a.PUBLISH_EXPLOIT_CODE,
            action="cs.exploit_made_public",
            reason="Defense, Detection, Accelerate deployment",
            desiderata=("X≺A",),
        ),
        # R21 vfd...: no V at vfdpX., where pX forces P
        _carry(
            "vfd...",
            a.NOTIFY_VENDOR,
            action="cs.vendor_becomes_aware",
            roles=NON_VENDOR,
            cs="vfdpx.",
            reason="Coordination",
            desiderata=("V≺P", "V≺X", "V≺A"),
        ),
        _carry(
            "vfd...",
            a.NOTIFY_VENDOR,
            action="cs.vendor_becomes_aware",
            roles=NON_VENDOR,
            cs="vfdP..",
            reason="Coordination",
            desiderata=("V≺X", "V≺A"),
        ),
        # R22 to R26: kept unnarrowed (D17)
        _carry(
            ".FdP..",
            a.ESCALATE_DEPLOYMENT_PRIORITY,
            reason="Coordination",
            desiderata=("D≺X", "D≺A"),
        ),
        _carry(
            ".f..X.",
            a.ESCALATE_FIX_PRIORITY,
            reason="Coordination",
            desiderata=("F≺A",),
        ),
        _carry(
            ".f...A",
            a.ESCALATE_FIX_PRIORITY,
            reason="Coordination",
            desiderata=("F≺X",),
        ),
        _carry(
            ".Fd.X.",
            a.ESCALATE_DEPLOYMENT_PRIORITY,
            reason="Coordination",
            desiderata=("D≺A",),
        ),
        _carry(
            ".Fd..A",
            a.ESCALATE_DEPLOYMENT_PRIORITY,
            reason="Coordination",
            desiderata=("D≺X",),
        ),
        # R27 ..dpxa: split by EM (D4, D14); EXITED has no EM move to suggest
        *_embargo_moves(EM.NONE),
        *_embargo_moves(EM.PROPOSED),
        *_embargo_moves(EM.ACTIVE),
        *_embargo_moves(EM.REVISE),
        # R28 Vfdp..
        _carry(
            "Vfdp..",
            a.MOTIVATE_VENDOR_TO_FIX,
            roles=NON_VENDOR,
            reason="Coordination",
            desiderata=("F≺P", "F≺X", "F≺A"),
        ),
        _carry(
            "Vfdp..",
            a.PUBLISH_VULNERABILITY,
            reason=(
                "Coordination: motivate the vendor to fix and deployers to"
                " mitigate"
            ),
            desiderata=("P≺X", "P≺A"),
        ),
        # R29 VFdpxa: avoid starting an embargo unless exigent (D15)
        _carry(
            "VFdpxa",
            a.SCRUTINIZE_APPROPRIATENESS_OF_EMBARGO_INITIATION,
            em=_NOT_STARTED,
            reason=(
                "Avoid starting an embargo unless exigent: the case is at the"
                " edge of where an embargo helps"
            ),
            desiderata=("D≺P",),
        ),
        # R30 VFdp..
        _carry(
            "VFdp..",
            a.ENCOURAGE_VENDOR_TO_DEPLOY_FIX,
            roles=NON_VENDOR,
            reason="Coordination",
            desiderata=("D≺P", "D≺X", "D≺A"),
        ),
        _carry(
            "VFdp..",
            a.PUBLISH_VULNERABILITY,
            reason="Accelerate deployment",
            desiderata=("P≺X", "P≺A"),
        ),
        _carry(
            "VFdp..",
            a.PUBLISH_FIX,
            reason="Accelerate deployment",
            desiderata=("P≺X", "P≺A"),
        ),
        # R31, R32, R33
        _carry(
            "VFdP..",
            a.PROMOTE_FIX_DEPLOYMENT,
            reason="Accelerate deployment",
            desiderata=("D≺X", "D≺A"),
        ),
        _carry(
            "VFDp..",
            a.PUBLISH_VULNERABILITY,
            reason="Document for future reference; acknowledge contributions",
            desiderata=("P≺X", "P≺A"),
        ),
        _carry(
            ".fd.xa",
            a.DISCOURAGE_EXPLOIT_PUBLICATION,
            reason="Limit attacker advantage",
            desiderata=("F≺X", "D≺X"),
        ),
        # R34 vfdpx. INITIATE_VEP_USGOV: not carried over (D3)
        # R35 to R38: housekeeping (D5, D16)
        _close("VFDPXA", None),
        _close("VFDPxa", "X or A"),
        _close("VFDPXa", "A"),
        _close("VFDPxA", "X"),
    )
