/**
 * Functions to determine which actions are available for each participant
 */

import type { DemoState, Action } from '../types'
import { getParticipant, getActiveVendors, hasSecondVendor } from './participantHelpers'

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
    if (!state.secondVendorInvited) {
      actions.push({
        id: 'finder-invite-vendor',
        label: 'Submit Report to Vendor 2',
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
    // Check EM state, NOT phase, since phase changes with VFD progression
    if (state.emState === 'PROPOSED' && !finder.embargoAccepted) {
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

    // Add submit report to second vendor option if not already sent
    // Available even if all vendors have closed (e.g., to try another vendor)
    if (!state.secondVendorInvited) {
      actions.push({
        id: 'finder-invite-vendor',
        label: 'Submit Report to Vendor 2',
        description: 'Send the vulnerability report to another vendor',
        enabled: true,
      })
    }

    // Close case if any vendor has deployed AND published
    if (anyVendorVFD && state.pxaState.includes('P') && !finder.hasClosed) {
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
  if (state.phase === 'vendor-closed' && !finder.hasClosed && state.pxaState.includes('P')) {
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

    if (state.pxaState.includes('P')) {
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

    if (state.pxaState.includes('P')) {
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

  // If vendor declined invitation, they have no actions
  if (vendor.rmState === 'DECLINED') return []

  const isVendor1 = vendorId === 'vendor-1'
  const vendorActivePhases = ['report-received', 'report-validated', 'report-accepted', 'report-deferred', 'report-invalidated', 'embargo-proposed', 'embargo-rejected', 'embargo-accepted', 'finder-asked', 'fix-ready', 'fix-deployed', 'vendor-published']

  // Per-participant RM state: vendor marked report as invalid
  // Per Vultron protocol: INVALID can transition to VALID (reconsideration) or CLOSED
  // While INVALID, vendors can communicate but should NOT progress VFD
  if (vendor.rmState === 'INVALID') {
    const actions: Action[] = [{
      id: 'validate-report',
      label: 'Re-validate Report',
      description: 'Mark the report as valid after reconsideration (RM: INVALID → VALID)',
      enabled: true,
    }, {
      id: 'vendor-close-case',
      label: 'Close Invalid Report',
      description: 'Close the case for this invalid report (RM: INVALID → CLOSED)',
      enabled: true,
    }]

    // Allow replying to questions even while report is invalid
    if (state.phase === 'finder-asked' && !vendor.hasRepliedToCurrentNote) {
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

    // Embargo response actions (EM state machine - independent of VFD and phase)
    // Check EM state, NOT phase, since phase changes with VFD progression
    if (state.emState === 'PROPOSED' && !vendor.embargoAccepted) {
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

    // Validation actions - vendor must validate before progressing VFD
    if (vendor.rmState === 'RECEIVED') {
      actions.push({
        id: 'validate-report',
        label: 'Validate Report',
        description: 'Mark the report as valid (RM: RECEIVED → VALID)',
        enabled: true,
      }, {
        id: 'invalidate-report',
        label: 'Invalidate Report',
        description: 'Mark the report as invalid (RM: RECEIVED → INVALID)',
        enabled: true,
      })
    }

    // Prioritization actions - after validation, vendor must accept or defer
    // Per Vultron protocol: VALID → ACCEPTED or VALID → DEFERRED
    if (vendor.rmState === 'VALID') {
      actions.push({
        id: 'accept-report',
        label: 'Accept Report',
        description: 'Accept the report and commit to working on it (RM: VALID → ACCEPTED)',
        enabled: true,
      }, {
        id: 'defer-report',
        label: 'Defer Report',
        description: 'Defer the report for later consideration (RM: VALID → DEFERRED)',
        enabled: true,
      })
    }

    // Resume work on deferred report
    // Per Vultron protocol: DEFERRED → ACCEPTED or DEFERRED → CLOSED
    if (vendor.rmState === 'DEFERRED') {
      actions.push({
        id: 'accept-report',
        label: 'Resume Work (Accept)',
        description: 'Resume work on the deferred report (RM: DEFERRED → ACCEPTED)',
        enabled: true,
      }, {
        id: 'vendor-close-case',
        label: 'Close Deferred Report',
        description: 'Close the deferred report (RM: DEFERRED → CLOSED)',
        enabled: true,
      })
    }

    // Reply to questions - each vendor can reply independently
    // Per Vultron protocol: notes are case-wide with inReplyTo relationships
    if (state.phase === 'finder-asked' && !vendor.hasRepliedToCurrentNote) {
      actions.push({
        id: 'vendor-reply-note',
        label: 'Reply to Question',
        description: 'Respond to Finder\'s question',
        enabled: true,
      })
    }

    // Submit report to second vendor (only first vendor can do this for now)
    if (isVendor1 && !state.secondVendorInvited && !hasSecondVendor(state)) {
      actions.push({
        id: 'vendor-invite-second-vendor',
        label: 'Submit Report to Vendor 2',
        description: 'Send the vulnerability report to another vendor for collaboration',
        enabled: true,
      })
    }

    // VFD progression - each vendor can progress independently
    // Per Vultron protocol: Fix Ready can only occur when vendor is in RM.ACCEPTED state
    // Vendors in VALID or DEFERRED must first accept before progressing VFD
    const canProgressVFD = vendor.rmState === 'ACCEPTED'

    if (vendor.vfdState === 'Vfd' && canProgressVFD) {
      actions.push({
        id: 'notify-fix-ready',
        label: 'Notify Fix Ready',
        description: 'Vendor notifies that a fix is ready',
        enabled: true,
      })
    }

    if (vendor.vfdState === 'VFd' && canProgressVFD) {
      actions.push({
        id: 'notify-fix-deployed',
        label: 'Notify Fix Deployed',
        description: 'Vendor notifies that the fix has been deployed',
        enabled: true,
      })
    }

    // Publication - triggers case-wide P (Public Awareness) transition
    // Per Vultron protocol: P is a one-way case-wide state transition (pxa → Pxa)
    // Once ANY participant publishes and P is set, the transition cannot occur again
    if (vendor.vfdState === 'VFD' && !state.pxaState.includes('P')) {
      actions.push({
        id: 'vendor-notify-published',
        label: 'Notify Published',
        description: 'Vendor notifies that vulnerability is publicly disclosed',
        enabled: true,
      })
    }

    // Close case - available after both fix deployed (VFD) AND published (P)
    if (vendor.vfdState === 'VFD' && state.pxaState.includes('P') && !vendor.hasClosed) {
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

    // Reply to questions
    if (state.phase === 'finder-asked') {
      actions.push({
        id: 'vendor-reply-note',
        label: 'Reply to Question',
        description: 'Respond to Finder\'s question',
        enabled: true,
      })
    }

    // Publish if case is not yet public
    if (vendor.vfdState === 'VFD' && !state.pxaState.includes('P') && state.phase === 'finder-closed') {
      actions.push({
        id: 'vendor-notify-published',
        label: 'Notify Published',
        description: 'Vendor notifies that vulnerability is publicly disclosed',
        enabled: true,
      })
    }

    // Close case
    if (vendor.vfdState === 'VFD' && state.pxaState.includes('P')) {
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

  // Per Vultron protocol: CaseActor can propose embargo when:
  // - EM is NONE (no embargo yet) - can propose at ANY time after case starts
  // - EM was rejected and returned to NONE - can propose again
  // - At least one vendor is in active RM state (case exists)
  // Protocol allows embargo proposals independent of RM states (even if vendor has invalidated)
  // EM state machine is independent - check emState only, NOT phase
  const canProposeEmbargo = state.emState === 'NONE' && state.phase !== 'start'

  if (canProposeEmbargo) {
    return [{
      id: 'propose-embargo',
      label: 'Propose Embargo',
      description: 'Propose a 90-day coordinated disclosure embargo',
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

    // Exploit publication (if not already published)
    if (!state.pxaState.includes('X')) {
      actions.push({
        id: 'trigger-exploit',
        label: 'Exploit Published (External)',
        description: 'Simulate an exploit being published in the wild',
        enabled: true,
      })
    }

    // Attacks observed (if not already observed)
    if (!state.pxaState.includes('A')) {
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
