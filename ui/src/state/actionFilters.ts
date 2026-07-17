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

export function getFinderActions(state: DemoState): Action[] {
  const finder = getParticipant(state, 'finder')
  if (!finder) return []

  const activeVendors = getActiveVendors(state)
  const anyVendorVFD = activeVendors.some(v => v.vfdState === 'VFD')

  // Start phase - submit report
  if (state.phase === 'start') {
    return [{
      id: 'submit-report',
      label: 'Submit Report',
      description: 'Create and submit a vulnerability report to the Vendor',
      enabled: true,
    }]
  }

  // Report received phase - case is active, participants can communicate
  if (state.phase === 'report-received' && !finder.hasClosed) {
    const actions: Action[] = []

    // Finder can ask questions once case exists (RM.RECEIVED is an active state)
    actions.push({
      id: 'finder-add-note',
      label: 'Ask Question',
      description: 'Add a note to the case asking for information',
      enabled: true,
    })

    // Finder can send report to additional vendors at any time after case exists
    // This is available even if all vendors have closed (e.g., to try another vendor)
    const allVendors = getVendors(state)
    const nextVendorNumber = allVendors.length + 1
    const nextVendorId = `vendor-${nextVendorNumber}`
    const canInviteMore = !state.invitedVendors.has(nextVendorId)

    if (canInviteMore) {
      actions.push({
        id: 'finder-invite-vendor',
        label: `Submit Report to Vendor ${nextVendorNumber}`,
        description: 'Send the vulnerability report to another vendor',
        enabled: true,
      })
    }

    return actions
  }

  // NOTE: Embargo handling and communication are independent per Vultron protocol

  // Finder can communicate throughout the CVD process (after report is received)
  // Only blocked when: Finder has closed, or case hasn't started yet
  const caseIsActive = state.phase !== 'start' && !finder.hasClosed

  if (caseIsActive) {
    const actions: Action[] = []

    // Embargo response actions (EM state machine - independent of other activities and phase)
    // Per Vultron protocol (early_termination.md + negotiating.md):
    // Embargoes SHALL terminate when P, X, or A occur - no accept/reject after that
    const isPublic = state.pxaState.includes('P') || state.pxaState.includes('X') || state.pxaState.includes('A')

    // EM accept/reject of the initial proposal — gated by machine legality
    // (`accept`/`reject` are legal from PROPOSED) plus the demo overlay that the
    // Finder hasn't already accepted and the case isn't public.
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

    // Per Vultron protocol (em/index.md): Active participants can propose revisions.
    // `propose` is machine-legal from ACTIVE (→REVISE) and REVISE (→REVISE); the
    // demo overlay additionally requires this Finder to already be in the embargo.
    if (isLegalTransition('em', state.emState, 'propose') && (state.emState === 'ACTIVE' || state.emState === 'REVISE') && !isPublic && finder.embargoAccepted) {
      actions.push({
        id: 'finder-propose-revision',
        label: 'Propose Embargo Revision',
        description: 'Propose a revision to the active embargo terms',
        enabled: true,
      })
    }

    // If there's a pending revision proposal, Finder can accept/reject it
    // (`accept`/`reject` are machine-legal from REVISE) UNLESS Finder proposed it
    // themselves (proposing implies acceptance) — that's the demo overlay.
    if (isLegalTransition('em', state.emState, 'accept') && state.emState === 'REVISE' && !isPublic && !finder.embargoAccepted && state.embargoProposerId !== 'finder') {
      // Show accept/reject when Finder hasn't accepted the revision yet and didn't propose it
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

    // Check if any vendor has replied to the current question
    const anyVendorReplied = activeVendors.some(v => v.hasRepliedToCurrentNote)

    // Communication actions - available regardless of embargo status
    actions.push({
      id: 'finder-add-note',
      label: anyVendorReplied ? 'Ask Another Question' : 'Ask Question',
      description: anyVendorReplied
        ? 'Add another note to the case asking for more information'
        : 'Add a note to the case asking for information',
      enabled: true,
    })

    // Add submit report to additional vendors option
    // Available even if all vendors have closed (e.g., to try another vendor)
    const allVendors = getVendors(state)
    const nextVendorNumber = allVendors.length + 1
    const nextVendorId = `vendor-${nextVendorNumber}`
    const canInviteMore = !state.invitedVendors.has(nextVendorId)

    if (canInviteMore) {
      actions.push({
        id: 'finder-invite-vendor',
        label: `Submit Report to Vendor ${nextVendorNumber}`,
        description: 'Send the vulnerability report to another vendor',
        enabled: true,
      })
    }

    // Close case - available once publication has occurred.
    // RM `close` legality (legal from the Finder's ACCEPTED state in this fork)
    // gates the machine step; the `pxaState.includes('P')` overlay is the demo
    // policy that the Finder only closes after publication.
    if (isLegalTransition('rm', finder.rmState, 'close') && state.pxaState.includes('P') && !finder.hasClosed) {
      actions.push({
        id: 'finder-close-case',
        label: 'Close Case',
        description: 'Finder closes their participation in the case',
        enabled: true,
      })
    }

    // Acknowledge publication if published and finder hasn't acknowledged
    if (state.pxaState === 'Pxa' && anyVendorVFD && !finder.hasPublished) {
      actions.push({
        id: 'finder-notify-published',
        label: 'Acknowledge Publication',
        description: 'Finder acknowledges publication',
        enabled: true,
      })
    }

    return actions
  }

  // Vendor closed
  if (state.phase === 'vendor-closed' && !finder.hasClosed && state.pxaState.includes('P') && isLegalTransition('rm', finder.rmState, 'close')) {
    return [{
      id: 'finder-close-case',
      label: 'Close Case',
      description: 'Finder closes their participation in the case',
      enabled: true,
    }]
  }

  // Vendor published
  if (state.phase === 'vendor-published' && !finder.hasClosed) {
    const actions: Action[] = [{
      id: 'finder-add-note',
      label: 'Ask Question',
      description: 'Add a note to the case asking for information',
      enabled: true,
    }]

    if (!finder.hasPublished) {
      actions.push({
        id: 'finder-notify-published',
        label: 'Acknowledge Publication',
        description: 'Finder acknowledges publication',
        enabled: true,
      })
    }

    if (state.pxaState.includes('P') && isLegalTransition('rm', finder.rmState, 'close')) {
      actions.push({
        id: 'finder-close-case',
        label: 'Close Case',
        description: 'Finder closes their participation in the case',
        enabled: true,
      })
    }

    return actions
  }

  // Finder published or vendor closed
  if (['finder-published', 'vendor-closed'].includes(state.phase) && !finder.hasClosed) {
    const actions: Action[] = [{
      id: 'finder-add-note',
      label: 'Ask Question',
      description: 'Add a note to the case asking for information',
      enabled: true,
    }]

    if (state.pxaState.includes('P') && isLegalTransition('rm', finder.rmState, 'close')) {
      actions.push({
        id: 'finder-close-case',
        label: 'Close Case',
        description: 'Finder closes their participation in the case',
        enabled: true,
      })
    }

    return actions
  }

  return []
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

  const vendorActivePhases = ['report-received', 'report-validated', 'report-accepted', 'report-deferred', 'report-invalidated', 'embargo-proposed', 'embargo-rejected', 'embargo-accepted', 'finder-asked', 'fix-ready', 'fix-deployed', 'vendor-published']

  // Per-participant RM state: vendor marked report as invalid.
  // From INVALID the machine permits `validate` (→VALID, reconsideration) and
  // `close` (→CLOSED); both buttons are gated by that legality. The INVALID
  // *phase routing* (this whole branch) and the "don't progress VFD while
  // invalid" rule are demo overlay. We assert legality to stay in sync with
  // protocol_states.json even though this branch is only entered when INVALID.
  if (vendor.rmState === 'INVALID') {
    const actions: Action[] = []

    if (isLegalTransition('rm', vendor.rmState, 'validate')) {
      actions.push({
        id: 'validate-report',
        label: 'Re-validate Report',
        description: 'Mark the report as valid after reconsideration (RM: INVALID → VALID)',
        enabled: true,
      })
    }

    if (isLegalTransition('rm', vendor.rmState, 'close')) {
      actions.push({
        id: 'vendor-close-case',
        label: 'Close Invalid Report',
        description: 'Close the case for this invalid report (RM: INVALID → CLOSED)',
        enabled: true,
      })
    }

    // Allow replying to questions even while report is invalid
    if (state.hasPendingFinderNote && !vendor.hasRepliedToCurrentNote) {
      actions.push({
        id: 'vendor-reply-note',
        label: 'Reply to Question',
        description: 'Respond to Finder\'s question',
        enabled: true,
      })
    }

    return actions
  }

  // NOTE: Embargo handling is now moved into vendorActivePhases block below
  // This ensures VFD and EM are independent per Vultron protocol

  // Active case phases for vendors (includes pre-embargo and embargo phases)
  if (vendorActivePhases.includes(state.phase)) {
    const actions: Action[] = []

    // Embargo response actions (EM state machine - independent of VFD and phase).
    // `accept`/`reject` legal from PROPOSED gates the machine step; the overlay
    // is "this vendor hasn't accepted and the case isn't public". Check EM
    // state, NOT phase, since phase changes with VFD progression.
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

    // Per Vultron protocol (em/index.md): Active participants can propose revisions.
    // `propose` is machine-legal from ACTIVE (→REVISE) and REVISE (→REVISE); the
    // overlay additionally requires this vendor to already be in the embargo.
    if (isLegalTransition('em', state.emState, 'propose') && (state.emState === 'ACTIVE' || state.emState === 'REVISE') && !isPublic && vendor.embargoAccepted) {
      actions.push({
        id: 'vendor-propose-revision',
        label: 'Propose Embargo Revision',
        description: 'Propose a revision to the active embargo terms',
        enabled: true,
      })
    }

    // If there's a pending revision proposal, vendor can accept/reject it
    // (`accept`/`reject` machine-legal from REVISE) UNLESS vendor proposed it
    // themselves (proposing implies acceptance) — demo overlay.
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

    // RM lifecycle buttons. The branch by `rmState` selects the right labels /
    // descriptions for each state; each button is gated by the legality of its
    // trigger from the current rmState (validate/invalidate from RECEIVED;
    // accept/defer from VALID; accept/close from DEFERRED), so the surfaced
    // transitions follow protocol_states.json rather than hardcoded source→dest.

    // Validation actions - vendor must validate before progressing VFD
    if (vendor.rmState === 'RECEIVED') {
      if (isLegalTransition('rm', vendor.rmState, 'validate')) {
        actions.push({
          id: 'validate-report',
          label: 'Validate Report',
          description: 'Mark the report as valid (RM: RECEIVED → VALID)',
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
    }

    // Prioritization actions - after validation, vendor must accept or defer.
    // Per Vultron protocol: VALID → ACCEPTED or VALID → DEFERRED.
    if (vendor.rmState === 'VALID') {
      if (isLegalTransition('rm', vendor.rmState, 'accept')) {
        actions.push({
          id: 'accept-report',
          label: 'Accept Report',
          description: 'Accept the report and commit to working on it (RM: VALID → ACCEPTED)',
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
    }

    // Resume work on deferred report.
    // Per Vultron protocol: DEFERRED → ACCEPTED or DEFERRED → CLOSED.
    if (vendor.rmState === 'DEFERRED') {
      if (isLegalTransition('rm', vendor.rmState, 'accept')) {
        actions.push({
          id: 'accept-report',
          label: 'Resume Work (Accept)',
          description: 'Resume work on the deferred report (RM: DEFERRED → ACCEPTED)',
          enabled: true,
        })
      }
      if (isLegalTransition('rm', vendor.rmState, 'close')) {
        actions.push({
          id: 'vendor-close-case',
          label: 'Close Deferred Report',
          description: 'Close the deferred report (RM: DEFERRED → CLOSED)',
          enabled: true,
        })
      }
    }

    // Reply to questions - each vendor can reply independently
    // Per Vultron protocol: notes are case-wide with inReplyTo relationships.
    // Gated on the case-level pending-note flag (not `phase`) so that an RM
    // transition by this or another vendor (e.g. defer) doesn't remove the option.
    if (state.hasPendingFinderNote && !vendor.hasRepliedToCurrentNote) {
      actions.push({
        id: 'vendor-reply-note',
        label: 'Reply to Question',
        description: 'Respond to Finder\'s question',
        enabled: true,
      })
    }

    // Submit report to additional vendors (any vendor can do this)
    const vendorCount = getVendors(state).length
    const nextVendorNumber = vendorCount + 1
    const nextVendorId = `vendor-${nextVendorNumber}`
    const canInviteMore = !state.invitedVendors.has(nextVendorId)

    if (canInviteMore) {
      actions.push({
        id: 'vendor-invite-next-vendor',
        label: `Submit Report to Vendor ${nextVendorNumber}`,
        description: 'Send the vulnerability report to another vendor for collaboration',
        enabled: true,
      })
    }

    // VFD progression - each vendor can progress independently. The VFD step
    // legality comes from the artifact (`fix_is_ready` from Vfd, `fix_is_deployed`
    // from VFd); `canProgressVFD` is the demo overlay coupling VFD to RM:
    // per Vultron protocol Fix Ready can only occur once the vendor is in
    // RM.ACCEPTED, so vendors in VALID/DEFERRED must accept first. (That RM→VFD
    // coupling is not itself a single machine transition — see protocolActions.)
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

    // Publication - triggers the case-wide P (Public Awareness) PXA transition.
    // `public_becomes_aware` legality (true only from a non-P pxaState) IS the
    // "not already public" check; the `vfdState === 'VFD'` overlay is the demo
    // rule that a vendor only publishes once their fix is deployed. (Publication
    // is a composite — PXA + EM terminate — so gating stays hand-written here.)
    if (vendor.vfdState === 'VFD' && isLegalTransition('pxa', state.pxaState, 'public_becomes_aware')) {
      actions.push({
        id: 'vendor-notify-published',
        label: 'Notify Published',
        description: 'Vendor notifies that vulnerability is publicly disclosed',
        enabled: true,
      })
    }

    // Close case - available after both fix deployed (VFD) AND published (P).
    // RM `close` legality gates the machine step (legal from the vendor's
    // ACCEPTED state); the VFD/P overlay is the demo rule that a vendor only
    // closes after deploying a fix and publication has occurred.
    if (vendor.vfdState === 'VFD' && state.pxaState.includes('P') && !vendor.hasClosed && isLegalTransition('rm', vendor.rmState, 'close')) {
      actions.push({
        id: 'vendor-close-case',
        label: 'Close Case',
        description: 'Vendor closes their participation in the case',
        enabled: true,
      })
    }

    return actions
  }

  // Post-publication phases (including when another vendor closed)
  if (['vendor-published', 'finder-published', 'finder-closed', 'vendor-closed'].includes(state.phase) && !vendor.hasClosed) {
    const actions: Action[] = []

    // Reply to questions (gated on the case-level pending-note flag, not `phase`,
    // which here is always a post-publication value)
    if (state.hasPendingFinderNote && !vendor.hasRepliedToCurrentNote) {
      actions.push({
        id: 'vendor-reply-note',
        label: 'Reply to Question',
        description: 'Respond to Finder\'s question',
        enabled: true,
      })
    }

    // Publish if case is not yet public. `public_becomes_aware` legality is the
    // "not yet public" check; the VFD + finder-closed overlay is demo phase policy.
    if (vendor.vfdState === 'VFD' && isLegalTransition('pxa', state.pxaState, 'public_becomes_aware') && state.phase === 'finder-closed') {
      actions.push({
        id: 'vendor-notify-published',
        label: 'Notify Published',
        description: 'Vendor notifies that vulnerability is publicly disclosed',
        enabled: true,
      })
    }

    // Close case — RM `close` legality gates the step; VFD + P is demo overlay.
    if (vendor.vfdState === 'VFD' && state.pxaState.includes('P') && isLegalTransition('rm', vendor.rmState, 'close')) {
      actions.push({
        id: 'vendor-close-case',
        label: 'Close Case',
        description: 'Vendor closes their participation in the case',
        enabled: true,
      })
    }

    return actions
  }

  return []
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

  if (canProposeEmbargo) {
    return [{
      id: 'propose-embargo',
      label: 'Propose Embargo',
      description: 'Propose a 90-day coordinated disclosure embargo',
      enabled: true,
    }]
  }

  // Per Vultron protocol: CaseActor can propose and respond to embargo revisions.
  // `propose` is machine-legal from ACTIVE (→REVISE); the demo surfaces a CaseActor
  // revision proposal only from ACTIVE (not from REVISE — a re-propose), hence the
  // explicit `=== 'ACTIVE'` overlay on top of the legality check.
  const canProposeRevision = isLegalTransition('em', state.emState, 'propose') && state.emState === 'ACTIVE' && !isPublic

  if (canProposeRevision) {
    return [{
      id: 'caseactor-propose-revision',
      label: 'Propose Embargo Revision',
      description: 'Propose a revision to the active embargo terms',
      enabled: true,
    }]
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
    return [{
      id: 'caseactor-accept-revision',
      label: 'Accept Embargo Revision',
      description: 'Accept the proposed revision to embargo terms',
      enabled: true,
    }, {
      id: 'caseactor-reject-revision',
      label: 'Reject Embargo Revision',
      description: 'Reject the proposed revision (keeps current embargo terms)',
      enabled: true,
    }]
  }

  return []
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
