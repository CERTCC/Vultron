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
rule by rule, on #6676:

* A publication is any publication and always a valid action: only the
  first causes P (D1).  A rule that publishes where P may already have
  happened names its member of ``Actions``; one that matches only positions
  where P has not names ``cs.public_becomes_aware``.
* A rule suggests and never forbids, so a costly rule, such as publishing
  before the vendor is aware, stays (D2).
* The Vulnerabilities Equities Process pair does not carry over (D3).
* A rule is narrowed with RM, EM or PEC parts where those states change
  what it is, and never widened (D4).  A rule whose CS pattern matches a
  state where an ephemeral state forces another event (``pX``) is split so
  it matches only positions where its move exists.
* Closing the case is ``rm.close`` for a participant whose RM state is not
  Closed, matched only where ``rm.close`` exists (``RM_CLOSABLE``) (D5).

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
_NO_ACTIVE_EMBARGO = frozenset({EM.NONE, EM.EXITED})
_FIX_GATE = frozenset({RM.ACCEPTED, RM.DEFERRED})
_CLOSABLE = frozenset(RM_CLOSABLE)
_INVITED = frozenset({EmbargoConsentState.INVITED})

_PUBLISH = "cs.public_becomes_aware"


def _carry(
    source: str,
    source_action: Actions,
    *,
    action: Actions | str | None = None,
    roles: Roles = ANY_ROLE,
    desiderata: tuple[str, ...],
    cs: str | None = None,
    rm: frozenset[RM] | None = None,
    em: frozenset[EM] | None = None,
    proposal: frozenset[EmbargoConsentState] | None = None,
    blind_spot: int | None = None,
    note: str | None = None,
) -> AuthoredRule:
    """One carried-over rule from the pair *source*, *source_action*.

    *action* defaults to *source_action*, and the CS part *cs* to the
    source pattern.
    """
    return AuthoredRule(
        pattern=RulePattern(cs=cs or source, rm=rm, em=em, proposal=proposal),
        roles=roles,
        action=source_action if action is None else action,
        desiderata=desiderata,
        source=SourcePair(pattern=source, action=source_action),
        blind_spot=blind_spot,
        note=note,
    )


def _terminate(source: str, desiderata: tuple[str, ...]) -> AuthoredRule:
    return _carry(
        source,
        Actions.TERMINATE_ANY_EXISTING_EMBARGO,
        action="em.terminate",
        roles=_OWNER,
        em=_IN_FORCE,
        desiderata=desiderata,
    )


def _ask_to_terminate(
    source: str, desiderata: tuple[str, ...]
) -> tuple[AuthoredRule, AuthoredRule]:
    return (
        _carry(
            source,
            Actions.INITIATE_EMBARGO_TERMINATION,
            action="em.terminate",
            roles=_OWNER,
            em=_IN_FORCE,
            desiderata=desiderata,
        ),
        _carry(
            source,
            Actions.INITIATE_EMBARGO_TERMINATION,
            roles=NOT_THE_OWNER,
            em=_IN_FORCE,
            desiderata=desiderata,
            note="ask the case owner to end the embargo",
        ),
    )


def _publish(
    source: str,
    source_action: Actions,
    desiderata: tuple[str, ...],
    *,
    move: bool,
    em: frozenset[EM] | None = None,
    note: str | None = None,
) -> AuthoredRule:
    return _carry(
        source,
        source_action,
        action=_PUBLISH if move else None,
        em=em,
        desiderata=desiderata,
        note=note,
    )


def _embargo_moves(em: EM, propose_note: str | None) -> list[AuthoredRule]:
    """``..dpxa`` "negotiate or establish an embargo", split by EM (D4)."""
    source, negotiate = (
        "..dpxa",
        Actions.NEGOTIATE_OR_ESTABLISH_DISCLOSURE_EMBARGO,
    )
    at = frozenset({em})
    if em in (EM.NONE, EM.ACTIVE):
        revision = em is EM.ACTIVE
        return [
            _carry(
                source,
                negotiate,
                action="em.propose",
                em=at,
                desiderata=("D≺P",) if revision else ("E≺P", "D≺P"),
                blind_spot=6492 if revision else None,
                note=propose_note,
            )
        ]
    return [
        _carry(
            source,
            negotiate,
            action="em.accept",
            roles=_OWNER,
            em=at,
            desiderata=("E≺P", "D≺P") if em is EM.PROPOSED else ("D≺P",),
        ),
        _carry(
            source,
            negotiate,
            action="em.reject",
            roles=_OWNER,
            em=at,
            desiderata=("P≺X", "P≺A"),
            note="a refused proposal leaves publication free",
        ),
        _carry(
            source,
            negotiate,
            action="pec.agree",
            roles=_VENDOR,
            em=at,
            proposal=_INVITED,
            desiderata=("E≺P", "D≺P") if em is EM.PROPOSED else ("D≺P",),
            note="the vendor's answer to the proposal; unscored until #6677",
        ),
        _carry(
            source,
            negotiate,
            action="pec.decline",
            roles=_VENDOR,
            em=at,
            proposal=_INVITED,
            desiderata=("P≺X", "P≺A"),
            note="the vendor's answer to the proposal; unscored until #6677",
        ),
    ]


def _close(source: str, note: str | None) -> AuthoredRule:
    return _carry(
        source,
        Actions.CLOSE_CASE,
        action="rm.close",
        rm=_CLOSABLE,
        desiderata=("X≺A",),
        note=note,
    )


@cache
def authored_rules() -> tuple[AuthoredRule, ...]:
    """The authored action rules, in the order of their source pairs in
    ``CS_ACTION_RULES``."""
    a = Actions
    return (
        # R1 ...P..
        _terminate("...P..", ("P≺X", "P≺A")),
        _publish(
            "...P..", a.PUBLISH_VULNERABILITY, ("P≺X", "P≺A"), move=False
        ),
        # R2 ....X.
        _terminate("....X.", ("P≺A",)),
        _publish("....X.", a.PUBLISH_VULNERABILITY, ("P≺A",), move=False),
        _publish(
            "....X.", a.PUBLICIZE_PUBLISHED_EXPLOITS, ("P≺A",), move=False
        ),
        _carry(
            "....X.", a.MONITOR_FOR_EXPLOIT_REFINEMENT, desiderata=("D≺A",)
        ),
        _publish(
            "....X.", a.PUBLISH_DETECTION_FOR_EXPLOITS, ("P≺A",), move=False
        ),
        # R3 .....A
        _terminate(".....A", ("P≺X",)),
        _publish(".....A", a.PUBLISH_VULNERABILITY, ("P≺X",), move=False),
        _carry(
            ".....A", a.MONITOR_FOR_ADDITIONAL_ATTACKS, desiderata=("P≺X",)
        ),
        _publish(
            ".....A", a.PUBLISH_DETECTION_FOR_ATTACKS, ("P≺X",), move=False
        ),
        # R4 VfdpX., R5 Vfdp.A
        *_ask_to_terminate("VfdpX.", ("P≺A",)),
        *_ask_to_terminate("Vfdp.A", ("P≺X",)),
        # R6, R7
        _carry(
            "....x.",
            a.MONITOR_FOR_EXPLOIT_PUBLICATION,
            desiderata=("F≺X", "D≺X"),
        ),
        _carry(".....a", a.MONITOR_FOR_ATTACKS, desiderata=("F≺A", "D≺A")),
        # R8 vfdP..
        _carry(
            "vfdP..",
            a.PAY_ATTENTION_TO_PUBLIC_REPORTS,
            action="cs.vendor_becomes_aware",
            roles=_VENDOR,
            desiderata=("V≺X", "V≺A"),
        ),
        _carry(
            "vfdP..",
            a.ESCALATE_VENDOR_NOTIFICATION_PRIORITY,
            roles=NON_VENDOR,
            desiderata=("V≺X", "V≺A"),
        ),
        # R9 ...pxa
        _carry(
            "...pxa",
            a.MAINTAIN_VIGILANCE_FOR_EMBARGO_EXIT_CRITERIA,
            desiderata=("ExOwn≺P",),
        ),
        _carry(
            "...pxa",
            a.MAINTAIN_ANY_EXISTING_EMBARGO,
            em=_IN_FORCE,
            desiderata=("F≺P", "D≺P"),
        ),
        # R10 VfdP..
        _carry(
            "VfdP..", a.ESCALATE_VIGILANCE_FOR_EXPLOITS, desiderata=("F≺X",)
        ),
        _carry(
            "VfdP..", a.ESCALATE_VIGILANCE_FOR_ATTACKS, desiderata=("F≺A",)
        ),
        _publish("VfdP..", a.PUBLISH_MITIGATION, ("D≺A",), move=False),
        _publish("VfdP..", a.PUBLICIZE_MITIGATION, ("D≺A",), move=False),
        _carry(
            "VfdP..",
            a.ESCALATE_FIX_PRIORITY,
            roles=NON_VENDOR,
            desiderata=("F≺X", "F≺A"),
        ),
        # R11 V..p..
        _publish(
            "V..p..",
            a.PUBLISH_VULNERABILITY,
            ("P≺X", "P≺A"),
            move=True,
            em=_NO_ACTIVE_EMBARGO,
            note="if no active embargo",
        ),
        _publish(
            "V..p..",
            a.PUBLISH_MITIGATION,
            ("P≺X", "P≺A"),
            move=True,
            em=_NO_ACTIVE_EMBARGO,
            note="if no active embargo",
        ),
        # R12 .fdP..
        _publish(".fdP..", a.PUBLISH_MITIGATION, ("D≺A",), move=False),
        # R13 ...pX.
        _publish("...pX.", a.PUBLISH_VULNERABILITY, ("P≺A",), move=True),
        _publish("...pX.", a.PUBLISH_MITIGATION, ("P≺A",), move=True),
        # R14 ...PX.
        _publish("...PX.", a.PUBLISH_VULNERABILITY, ("P≺A",), move=False),
        _publish("...PX.", a.PUBLISH_MITIGATION, ("P≺A",), move=False),
        # R15 ...p.A
        _publish("...p.A", a.PUBLISH_VULNERABILITY, ("P≺X",), move=True),
        _publish("...p.A", a.PUBLISH_MITIGATION, ("P≺X",), move=True),
        # R16 vfdp.. (D2: kept, unconditional; its cost shows in the advice)
        _publish("vfdp..", a.PUBLISH_VULNERABILITY, ("P≺X", "P≺A"), move=True),
        _publish("vfdp..", a.PUBLISH_MITIGATION, ("P≺X", "P≺A"), move=True),
        # R17 Vfd...: no F at VfdpX., where pX forces P
        _carry(
            "Vfd...",
            a.CREATE_FIX,
            action="cs.fix_is_ready",
            roles=_VENDOR,
            cs="Vfdpx.",
            rm=_FIX_GATE,
            desiderata=("F≺P", "F≺X", "F≺A", "F_i≺ExOwn"),
        ),
        _carry(
            "Vfd...",
            a.CREATE_FIX,
            action="cs.fix_is_ready",
            roles=_VENDOR,
            cs="VfdP..",
            rm=_FIX_GATE,
            desiderata=("F≺X", "F≺A"),
        ),
        _carry(
            "Vfd...",
            a.ENCOURAGE_VENDOR_TO_CREATE_FIX,
            roles=NON_VENDOR,
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
            desiderata=("D≺P", "D≺X", "D≺A"),
        ),
        _carry(
            "VFd...",
            a.DEPLOY_FIX,
            action="cs.fix_is_deployed",
            roles=_DEPLOYER,
            cs="VFdpx.",
            rm=_FIX_GATE,
            desiderata=("D≺P", "D≺X", "D≺A"),
        ),
        _carry(
            "VFd...",
            a.DEPLOY_FIX,
            action="cs.fix_is_deployed",
            roles=_DEPLOYER,
            cs="VFdP..",
            rm=_FIX_GATE,
            desiderata=("D≺X", "D≺A"),
        ),
        # R19 .fdPxA: narrowed to VfdPxA, where vP does not force V
        _carry(
            ".fdPxA",
            a.PUBLISH_EXPLOIT_CODE,
            action="cs.exploit_made_public",
            cs="VfdPxA",
            desiderata=("X≺A",),
            note="defense and detection; X≺A is already lost here",
        ),
        # R20 VFdPxa
        _carry(
            "VFdPxa",
            a.PUBLISH_EXPLOIT_CODE,
            action="cs.exploit_made_public",
            desiderata=("X≺A",),
        ),
        # R21 vfd...: no V at vfdpX., where pX forces P
        _carry(
            "vfd...",
            a.NOTIFY_VENDOR,
            action="cs.vendor_becomes_aware",
            roles=NON_VENDOR,
            cs="vfdpx.",
            desiderata=("V≺P", "V≺X", "V≺A"),
        ),
        _carry(
            "vfd...",
            a.NOTIFY_VENDOR,
            action="cs.vendor_becomes_aware",
            roles=NON_VENDOR,
            cs="vfdP..",
            desiderata=("V≺X", "V≺A"),
        ),
        # R22 to R26
        _carry(
            ".FdP..", a.ESCALATE_DEPLOYMENT_PRIORITY, desiderata=("D≺X", "D≺A")
        ),
        _carry(".f..X.", a.ESCALATE_FIX_PRIORITY, desiderata=("F≺A",)),
        _carry(".f...A", a.ESCALATE_FIX_PRIORITY, desiderata=("F≺X",)),
        _carry(".Fd.X.", a.ESCALATE_DEPLOYMENT_PRIORITY, desiderata=("D≺A",)),
        _carry(".Fd..A", a.ESCALATE_DEPLOYMENT_PRIORITY, desiderata=("D≺X",)),
        # R27 ..dpxa: split by EM (D4); EXITED has no EM move to suggest
        *_embargo_moves(EM.NONE, None),
        *_embargo_moves(EM.PROPOSED, None),
        *_embargo_moves(
            EM.ACTIVE,
            "propose a revision that extends the embargo, to buy time",
        ),
        *_embargo_moves(EM.REVISE, None),
        # R28 Vfdp..
        _carry(
            "Vfdp..",
            a.MOTIVATE_VENDOR_TO_FIX,
            roles=NON_VENDOR,
            desiderata=("F≺P", "F≺X", "F≺A"),
        ),
        _publish("Vfdp..", a.PUBLISH_VULNERABILITY, ("P≺X", "P≺A"), move=True),
        # R29 VFdpxa
        _carry(
            "VFdpxa",
            a.SCRUTINIZE_APPROPRIATENESS_OF_EMBARGO_INITIATION,
            desiderata=("D≺P",),
        ),
        # R30 VFdp..
        _carry(
            "VFdp..",
            a.ENCOURAGE_VENDOR_TO_DEPLOY_FIX,
            roles=NON_VENDOR,
            desiderata=("D≺P", "D≺X", "D≺A"),
        ),
        _publish("VFdp..", a.PUBLISH_VULNERABILITY, ("P≺X", "P≺A"), move=True),
        _publish("VFdp..", a.PUBLISH_FIX, ("P≺X", "P≺A"), move=True),
        # R31, R32, R33
        _carry("VFdP..", a.PROMOTE_FIX_DEPLOYMENT, desiderata=("D≺X", "D≺A")),
        _publish("VFDp..", a.PUBLISH_VULNERABILITY, ("P≺X", "P≺A"), move=True),
        _carry(
            ".fd.xa",
            a.DISCOURAGE_EXPLOIT_PUBLICATION,
            desiderata=("F≺X", "D≺X"),
        ),
        # R34 vfdpx. INITIATE_VEP_USGOV: not carried over (D3)
        # R35 to R38 (D5)
        _close("VFDPXA", None),
        _close("VFDPxa", "unless monitoring for X or A"),
        _close("VFDPXa", "unless monitoring for A"),
        _close("VFDPxA", "unless monitoring for X"),
    )
