/**
 * Functions to determine which actions are available for each participant.
 *
 * VALIDATED FORK (see ui/CLAUDE.md §9, Step 5): machine-state gating (RM / EM /
 * VFD / PXA) is derived from the committed protocol artifact via
 * `isLegalTransition(...)` rather than hardcoded state-name comparisons. The
 * pattern throughout is:
 *
 *     isLegalTransition(machine, currentState, trigger)  // machine legality (JSON)
 *       && <demo overlay conditions>                     // non-machine policy
 *
 * The overlays that intentionally stay hand-written (they have no machine slot
 * per protocolActions.ts) are: embargo-before-participation (late-joiner
 * consent), `isPublic` early-termination, pending-note reply gating, invite
 * availability, `phase` routing, and label/action-id selection between EM
 * negotiation phases. Where the demo surfaces a transition in only *some* of
 * the machine-legal source states (a deliberate happy-path narrowing, e.g. no
 * re-deferring an ACCEPTED report), that narrowing is an explicit `=== STATE`
 * overlay layered on top of the legality check and is commented as such.
 *
 * NOTE: this fork drops the `DECLINED` RM pseudo-state the original carries.
 * `DECLINED` is not a real RM state in protocol_states.json and was never
 * actually written anywhere (no decline action/handler exists — invited vendors
 * enter directly at RM.RECEIVED), so its guards were inert. A vendor "declining"
 * a report is, at the protocol level, either `invalidate` (→INVALID→CLOSED) or
 * `defer` (→DEFERRED→CLOSED) — both already represented. See ui/CLAUDE.md §9.
 */

import type { DemoState, Action } from '../types'
import { getParticipant, getActiveVendors, getVendors } from './participantHelpers'
import { isLegalTransition } from '../protocol'

/**
 * Build the "Submit Report to Vendor N" (invite) action, or null if unavailable.
 *
 * Inviting another vendor is a DEMO-overlay action — the Vultron protocol has no
 * invite/report-forwarding transition (see protocolActions.ts, `kind:'demo'`), so
 * this is a policy choice, not a machine gate. Policy: any active participant may
 * invite another vendor **as long as the case is not yet closed**, independent of
 * the case-level `phase`. This is grounded in the protocol's separation of Report
 * Management (closure) from publicity/PXA: coordination — including onboarding a
 * newly-discovered affected vendor — legitimately continues after publication,
 * "long after the RM process has closed a case" is possible (cs_model.md). So the
 * only real limit is that the case itself is still open.
 *
 * "Case not yet closed" = at least one participant is still active (not everyone
 * has RM.CLOSED). The individual caller has already confirmed IT is active.
 */
function buildInviteAction(state: DemoState): Action | null {
  // Case is closed only when every visible participant has closed.
  const anyStillOpen = Array.from(state.participants.values())
    .some(p => p.visible && !p.hasClosed)
  if (!anyStillOpen) return null

  const nextVendorNumber = getVendors(state).length + 1
  const nextVendorId = `vendor-${nextVendorNumber}`
  if (state.invitedVendors.has(nextVendorId)) return null

  return {
    id: 'invite-vendor',
    label: `Submit Report to Vendor ${nextVendorNumber}`,
    description: 'Send the vulnerability report to another vendor for collaboration',
    enabled: true,
  }
}

export function getFinderActions(state: DemoState): Action[] {
  const finder = getParticipant(state, 'finder')
  if (!finder) return []

  const activeVendors = getActiveVendors(state)
  const anyVendorVFD = activeVendors.some(v => v.vfdState === 'VFD')

  // Before a report exists there is exactly one action: submit it. `start` is the
  // only pre-case phase; every other phase means a case exists. (Submit itself has
  // no machine slot — it's the demo bootstrap that seeds RM.RECEIVED, §9.)
  if (state.phase === 'start') {
    return [{
      id: 'submit-report',
      label: 'Submit Report',
      description: 'Create and submit a vulnerability report to the Vendor',
      enabled: true,
    }]
  }

  // Once the Finder has closed, they have no further actions.
  if (finder.hasClosed) return []

  // A case exists and the Finder is still participating. Every action below is
  // gated by its own machine-legality (from protocol_states.json) plus an explicit
  // documented overlay — NOT by the case-level `phase` string. This keeps the
  // available actions caused by the artifact rather than by phase bookkeeping.
  const actions: Action[] = []

  // Embargoes SHALL terminate when P/X/A occur (early_termination.md), so no
  // embargo accept/reject/propose once public.
  const isPublic = state.pxaState.includes('P') || state.pxaState.includes('X') || state.pxaState.includes('A')

  // EM accept/reject of the initial proposal — `accept`/`reject` legal from
  // PROPOSED; overlay: Finder hasn't accepted and case isn't public.
  if (isLegalTransition('em', state.emState, 'accept') && state.emState === 'PROPOSED' && !finder.embargoAccepted && !isPublic) {
    actions.push({
      id: 'finder-accept-embargo',
      label: 'Accept Embargo',
      description: 'Accept the 90-day embargo proposal',
      enabled: true,
    }, {
      id: 'finder-reject-embargo',
      label: 'Reject Embargo',
      description: 'Reject the embargo proposal',
      enabled: true,
    })
  }

  // Propose revision — `propose` legal from ACTIVE/REVISE; overlay: this Finder is
  // already in the embargo and case isn't public.
  if (isLegalTransition('em', state.emState, 'propose') && (state.emState === 'ACTIVE' || state.emState === 'REVISE') && !isPublic && finder.embargoAccepted) {
    actions.push({
      id: 'finder-propose-revision',
      label: 'Propose Embargo Revision',
      description: 'Propose a revision to the active embargo terms',
      enabled: true,
    })
  }

  // Accept/reject a pending revision — `accept`/`reject` legal from REVISE; overlay:
  // Finder hasn't responded and didn't propose it (proposing implies acceptance).
  if (isLegalTransition('em', state.emState, 'accept') && state.emState === 'REVISE' && !isPublic && !finder.embargoAccepted && state.embargoProposerId !== 'finder') {
    actions.push({
      id: 'finder-accept-revision',
      label: 'Accept Embargo Revision',
      description: 'Accept the proposed revision to embargo terms',
      enabled: true,
    }, {
      id: 'finder-reject-revision',
      label: 'Reject Embargo Revision',
      description: 'Reject the proposed revision (keeps current embargo terms)',
      enabled: true,
    })
  }

  // Ask a question — always available to an active Finder (notes have no machine
  // slot; the label just reflects whether a vendor has answered yet).
  const anyVendorReplied = activeVendors.some(v => v.hasRepliedToCurrentNote)
  actions.push({
    id: 'finder-add-note',
    label: anyVendorReplied ? 'Ask Another Question' : 'Ask Question',
    description: anyVendorReplied
      ? 'Add another note to the case asking for more information'
      : 'Add a note to the case asking for information',
    enabled: true,
  })

  // Submit report to additional vendors while the case is open.
  const invite = buildInviteAction(state)
  if (invite) actions.push(invite)

  // Acknowledge publication once the vuln is public and a vendor has a deployed
  // fix (Pxa + some vendor at VFD); overlay-only (acknowledgement has no machine
  // slot). Kept before close so it appears while still relevant.
  if (state.pxaState === 'Pxa' && anyVendorVFD && !finder.hasPublished) {
    actions.push({
      id: 'finder-notify-published',
      label: 'Acknowledge Publication',
      description: 'Finder acknowledges publication',
      enabled: true,
    })
  }

  // Close — `close` legal from the Finder's RM state (ACCEPTED/DEFERRED); overlay:
  // the demo lets the Finder close only after publication (P present).
  if (isLegalTransition('rm', finder.rmState, 'close') && state.pxaState.includes('P')) {
    actions.push({
      id: 'finder-close-case',
      label: 'Close Case',
      description: 'Finder closes their participation in the case',
      enabled: true,
    })
  }

  return actions
}

export function getVendorActions(state: DemoState, vendorId: string): Action[] {
  const vendor = getParticipant(state, vendorId)
  if (!vendor || !vendor.visible) return []

  // If vendor has closed their participation, they have no actions
  if (vendor.hasClosed) return []

  // NOTE: the original demo had a `rmState === 'DECLINED'` guard here for
  // declined invitations. This fork drops it — DECLINED is not a real RM state
  // (protocol_states.json) and was never written (no decline action exists;
  // invited vendors enter at RM.RECEIVED). See the file header / CLAUDE.md §9.

  // Per Vultron protocol (working_with_others.md lines 107-115):
  // If vendor joined a case with an existing embargo, they must accept/reject embargo FIRST
  // before they can proceed with other actions
  // UNLESS embargo has terminated due to P, X, or A (per early_termination.md)
  const isPublic = state.pxaState.includes('P') || state.pxaState.includes('X') || state.pxaState.includes('A')

  if (vendor.embargoProposedToParticipant && !vendor.embargoAccepted && !isPublic) {
    // Determine if this is a revision scenario or late-joiner scenario
    const isRevisionScenario = state.emState === 'REVISE'

    return [{
      id: 'accept-embargo',
      label: isRevisionScenario ? 'Accept Embargo Revision' : 'Accept Existing Embargo',
      description: isRevisionScenario
        ? 'Accept the revised embargo terms to participate in the case'
        : 'Accept the active embargo agreement to join the case',
      enabled: true,
    }, {
      id: 'reject-embargo',
      label: isRevisionScenario ? 'Reject Embargo Revision' : 'Reject Embargo',
      description: isRevisionScenario
        ? 'Reject the revised embargo terms (will prevent full participation)'
        : 'Reject the embargo proposal (will prevent full participation)',
      enabled: true,
    }]
  }

  // Per Vultron protocol (working_with_others.md lines 112-115):
  // "The inviting Participant SHOULD NOT share the vulnerability report with the newly invited
  // Participant unless the new Participant has accepted the existing embargo."
  // If vendor rejected an ACTIVE embargo, they cannot participate (no actions available)
  // HOWEVER: During REVISE state, all vendors can participate and vote on the revision
  // ALSO: Per early_termination.md lines 32-39, if embargo is terminated (EXITED or by P/X/A), vendor can participate
  const hasActiveEmbargo = state.emState === 'ACTIVE' && !isPublic
  if (hasActiveEmbargo && !vendor.embargoAccepted && !vendor.embargoProposedToParticipant) {
    // Vendor rejected ACTIVE embargo - they are excluded from participation
    // No actions available until embargo ends or a revision is proposed
    return []
  }
  // If embargo was EXITED (terminated), P/X/A occurred, or in REVISE state, vendors can participate
  // The barrier to participation no longer exists or is temporarily lifted for revision voting

  // An active, participating vendor. Every action below is gated by its own
  // machine-legality (from protocol_states.json via isLegalTransition) plus an
  // explicit, documented non-machine overlay — NOT by the case-level `phase`
  // string. This is deliberate: the four machines (RM/EM/VFD/PXA) are independent
  // per the Vultron protocol, so e.g. fix development legitimately continues after
  // publication (cs/index.md: "both Fix Ready and Public Awareness are necessary
  // for Fix Deployment" in the shrinkwrap model). Gating on `phase` — a single
  // last-action-wins string — previously hid legal actions (e.g. a vendor still at
  // VFD=Vfd lost Notify Fix Ready once the Finder acknowledged publication).
  const actions: Action[] = []

  // ---- EM: embargo consent / revision (independent of VFD; not after public) ----
  // `accept`/`reject` legal from PROPOSED; overlay: not yet accepted, not public.
  if (isLegalTransition('em', state.emState, 'accept') && state.emState === 'PROPOSED' && !vendor.embargoAccepted && !isPublic) {
    actions.push({
      id: 'accept-embargo',
      label: 'Accept Embargo',
      description: 'Accept the 90-day embargo proposal',
      enabled: true,
    }, {
      id: 'reject-embargo',
      label: 'Reject Embargo',
      description: 'Reject the embargo proposal',
      enabled: true,
    })
  }

  // Propose revision — `propose` legal from ACTIVE/REVISE; overlay: this vendor is
  // in the embargo and case isn't public.
  if (isLegalTransition('em', state.emState, 'propose') && (state.emState === 'ACTIVE' || state.emState === 'REVISE') && !isPublic && vendor.embargoAccepted) {
    actions.push({
      id: 'vendor-propose-revision',
      label: 'Propose Embargo Revision',
      description: 'Propose a revision to the active embargo terms',
      enabled: true,
    })
  }

  // Accept/reject a pending revision — `accept`/`reject` legal from REVISE; overlay:
  // vendor hasn't responded and didn't propose it (proposing implies acceptance).
  if (isLegalTransition('em', state.emState, 'accept') && state.emState === 'REVISE' && !isPublic && !vendor.embargoAccepted && state.embargoProposerId !== vendorId) {
    actions.push({
      id: 'vendor-accept-revision',
      label: 'Accept Embargo Revision',
      description: 'Accept the proposed revision to embargo terms',
      enabled: true,
    }, {
      id: 'vendor-reject-revision',
      label: 'Reject Embargo Revision',
      description: 'Reject the proposed revision (keeps current embargo terms)',
      enabled: true,
    })
  }

  // ---- RM lifecycle: buttons follow trigger legality from the current rmState ----
  // (validate/invalidate from RECEIVED; validate from INVALID; accept/defer from
  // VALID; accept/close from DEFERRED; close from ACCEPTED). Labels vary by source
  // state, but each is gated purely by isLegalTransition so surfaced transitions
  // track protocol_states.json.
  if (isLegalTransition('rm', vendor.rmState, 'validate')) {
    actions.push({
      id: 'validate-report',
      label: vendor.rmState === 'INVALID' ? 'Re-validate Report' : 'Validate Report',
      description: vendor.rmState === 'INVALID'
        ? 'Mark the report as valid after reconsideration (RM: INVALID → VALID)'
        : 'Mark the report as valid (RM: RECEIVED → VALID)',
      enabled: true,
    })
  }
  if (isLegalTransition('rm', vendor.rmState, 'invalidate')) {
    actions.push({
      id: 'invalidate-report',
      label: 'Invalidate Report',
      description: 'Mark the report as invalid (RM: RECEIVED → INVALID)',
      enabled: true,
    })
  }
  if (isLegalTransition('rm', vendor.rmState, 'accept')) {
    actions.push({
      id: 'accept-report',
      label: vendor.rmState === 'DEFERRED' ? 'Resume Work (Accept)' : 'Accept Report',
      description: vendor.rmState === 'DEFERRED'
        ? 'Resume work on the deferred report (RM: DEFERRED → ACCEPTED)'
        : 'Accept the report and commit to working on it (RM: VALID → ACCEPTED)',
      enabled: true,
    })
  }
  if (isLegalTransition('rm', vendor.rmState, 'defer')) {
    actions.push({
      id: 'defer-report',
      label: 'Defer Report',
      description: 'Defer the report for later consideration (RM: VALID → DEFERRED)',
      enabled: true,
    })
  }

  // ---- Notes: reply to a pending Finder question (no machine slot) ----
  if (state.hasPendingFinderNote && !vendor.hasRepliedToCurrentNote) {
    actions.push({
      id: 'vendor-reply-note',
      label: 'Reply to Question',
      description: 'Respond to Finder\'s question',
      enabled: true,
    })
  }

  // ---- VFD: fix development, independent of publicity ----
  // `fix_is_ready` legal from Vfd, `fix_is_deployed` from VFd (artifact). Overlay:
  // `canProgressVFD` couples VFD to RM.ACCEPTED (Fix Ready requires the vendor to
  // have accepted; not a single machine transition — see protocolActions/§9). NB:
  // NOT gated on publicity — a vendor may (and per the shrinkwrap model, typically
  // does) advance/deploy a fix after the vuln is public.
  const canProgressVFD = vendor.rmState === 'ACCEPTED'
  if (isLegalTransition('vfd', vendor.vfdState, 'fix_is_ready') && canProgressVFD) {
    actions.push({
      id: 'notify-fix-ready',
      label: 'Notify Fix Ready',
      description: 'Vendor notifies that a fix is ready',
      enabled: true,
    })
  }
  if (isLegalTransition('vfd', vendor.vfdState, 'fix_is_deployed') && canProgressVFD) {
    actions.push({
      id: 'notify-fix-deployed',
      label: 'Notify Fix Deployed',
      description: 'Vendor notifies that the fix has been deployed',
      enabled: true,
    })
  }

  // ---- Publication: case-wide P transition ----
  // `public_becomes_aware` legality IS the "not already public" check; overlay:
  // vendor only publishes once their own fix is deployed (VFD). (Composite — PXA +
  // EM terminate — so gating stays hand-written.)
  if (vendor.vfdState === 'VFD' && isLegalTransition('pxa', state.pxaState, 'public_becomes_aware')) {
    actions.push({
      id: 'vendor-notify-published',
      label: 'Notify Published',
      description: 'Vendor notifies that vulnerability is publicly disclosed',
      enabled: true,
    })
  }

  // ---- Close ----
  // `close` legal from ACCEPTED/DEFERRED/INVALID (artifact). Overlay differs by
  // source: an INVALID or DEFERRED report can be closed immediately (dead-ends);
  // an ACCEPTED report only closes after the vendor has deployed a fix (VFD) and
  // the vuln is public (P) — the demo's "finished coordinating" rule.
  if (isLegalTransition('rm', vendor.rmState, 'close')) {
    const closeableNow =
      vendor.rmState === 'INVALID' ||
      vendor.rmState === 'DEFERRED' ||
      (vendor.vfdState === 'VFD' && state.pxaState.includes('P'))
    if (closeableNow) {
      const label =
        vendor.rmState === 'INVALID' ? 'Close Invalid Report'
        : vendor.rmState === 'DEFERRED' ? 'Close Deferred Report'
        : 'Close Case'
      actions.push({
        id: 'vendor-close-case',
        label,
        description: 'Vendor closes their participation in the case',
        enabled: true,
      })
    }
  }

  // ---- Invite: onboard another vendor while the case is open (demo overlay) ----
  const invite = buildInviteAction(state)
  if (invite) actions.push(invite)

  return actions
}

export function getCaseActorActions(state: DemoState): Action[] {
  const caseActor = getParticipant(state, 'caseactor')
  if (!caseActor || !caseActor.visible) return []

  // Per Vultron protocol (early_termination.md lines 32-39):
  // "Embargoes SHALL terminate immediately when information about the vulnerability becomes public."
  // Once P (public awareness) is reached, no embargo can be proposed or maintained
  const isPublic = state.pxaState.includes('P')

  // Per Vultron protocol: CaseActor can propose embargo when:
  // - EM is NONE (no embargo yet) - can propose at ANY time after case starts
  // - EM was rejected and returned to NONE - can propose again
  // - At least one vendor is in active RM state (case exists)
  // - Vulnerability is NOT yet public (P state not reached)
  // Protocol allows embargo proposals independent of RM states (even if vendor has invalidated).
  // `propose` legality from the current emState gates the machine step (NONE→PROPOSED);
  // the overlay is "after case start, not public". Check emState only, NOT phase.
  const canProposeEmbargo = isLegalTransition('em', state.emState, 'propose') && state.emState === 'NONE' && state.phase !== 'start' && !isPublic

  const actions: Action[] = []

  if (canProposeEmbargo) {
    actions.push({
      id: 'propose-embargo',
      label: 'Propose Embargo',
      description: 'Propose a 90-day coordinated disclosure embargo',
      enabled: true,
    })
  }

  // Per Vultron protocol: CaseActor can propose and respond to embargo revisions.
  // `propose` is machine-legal from ACTIVE (→REVISE); the demo surfaces a CaseActor
  // revision proposal only from ACTIVE (not from REVISE — a re-propose), hence the
  // explicit `=== 'ACTIVE'` overlay on top of the legality check.
  const canProposeRevision = isLegalTransition('em', state.emState, 'propose') && state.emState === 'ACTIVE' && !isPublic

  if (canProposeRevision) {
    actions.push({
      id: 'caseactor-propose-revision',
      label: 'Propose Embargo Revision',
      description: 'Propose a revision to the active embargo terms',
      enabled: true,
    })
  }

  // If there's a pending revision that CaseActor didn't propose, they can accept/reject it
  // (`accept`/`reject` machine-legal from REVISE); not-self-proposed AND not-already-
  // responded are the overlay. The `!caseActor.embargoAccepted` guard mirrors the
  // Finder/Vendor revision filters — without it the CaseActor keeps seeing accept/
  // reject after accepting, because their accept leaves EM in REVISE while consensus
  // is still pending (CaseActor acceptance doesn't count toward consensus, so it
  // doesn't fire REVISE → ACTIVE the way a reject does). The flag is UI-only: it is
  // never read by `allParticipantsAccepted` (finder + active vendors only).
  if (isLegalTransition('em', state.emState, 'accept') && state.emState === 'REVISE' && !isPublic && !caseActor.embargoAccepted && state.embargoProposerId !== 'caseactor') {
    actions.push({
      id: 'caseactor-accept-revision',
      label: 'Accept Embargo Revision',
      description: 'Accept the proposed revision to embargo terms',
      enabled: true,
    }, {
      id: 'caseactor-reject-revision',
      label: 'Reject Embargo Revision',
      description: 'Reject the proposed revision (keeps current embargo terms)',
      enabled: true,
    })
  }

  // The Case Actor (coordinator) can also onboard another vendor while the case
  // is open — same policy as finder/vendors (buildInviteAction). Previously this
  // was fully absent for the Case Actor.
  const invite = buildInviteAction(state)
  if (invite) actions.push(invite)

  return actions
}

export function getExternalActions(state: DemoState): Action[] {
  // External events can happen at any time after a case exists
  // They are independent of the EM state machine
  // Per the Vultron protocol, PXA events represent real-world occurrences
  // that are outside the control of any participant
  if (state.phase !== 'start') {
    const actions: Action[] = []

    // Exploit publication. `exploit_made_public` is machine-legal from exactly
    // the pxaState values without an X (pxa/pxA/Pxa/PxA), so its legality IS the
    // "not already published" check.
    if (isLegalTransition('pxa', state.pxaState, 'exploit_made_public')) {
      actions.push({
        id: 'trigger-exploit',
        label: 'Exploit Published (External)',
        description: 'Simulate an exploit being published in the wild',
        enabled: true,
      })
    }

    // Attacks observed. `attacks_are_observed` is machine-legal from exactly the
    // pxaState values without an A, so its legality IS the "not already observed" check.
    if (isLegalTransition('pxa', state.pxaState, 'attacks_are_observed')) {
      actions.push({
        id: 'trigger-attacks',
        label: 'Attacks Observed (External)',
        description: 'Simulate attacks being observed in the wild',
        enabled: true,
      })
    }

    return actions
  }

  return []
}
