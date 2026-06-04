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

  // Embargo proposed - accept/reject
  if (state.phase === 'embargo-proposed' && !finder.embargoAccepted) {
    return [{
      id: 'finder-accept-embargo',
      label: 'Accept Embargo',
      description: 'Accept the 90-day embargo proposal',
      enabled: true,
    }, {
      id: 'finder-reject-embargo',
      label: 'Reject Embargo',
      description: 'Reject the embargo proposal',
      enabled: true,
    }]
  }

  // Active case phases
  const activeCasePhases = ['report-invalidated', 'embargo-accepted', 'finder-asked', 'vendor-replied', 'fix-ready', 'fix-deployed']
  if (activeCasePhases.includes(state.phase) && !finder.hasClosed) {
    const actions: Action[] = [{
      id: 'finder-add-note',
      label: state.phase === 'vendor-replied' ? 'Ask Another Question' : 'Ask Question',
      description: state.phase === 'vendor-replied'
        ? 'Add another note to the case asking for more information'
        : 'Add a note to the case asking for information',
      enabled: true,
    }]

    // Add invite second vendor option if not already invited and at least one vendor is active
    if (!state.secondVendorInvited && activeVendors.length >= 1) {
      actions.push({
        id: 'finder-invite-vendor',
        label: 'Invite Second Vendor',
        description: 'Invite another vendor to participate in this case',
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

  const activeVendors = getActiveVendors(state)
  const isVendor1 = vendorId === 'vendor-1'

  // Report received - validate or invalidate
  if (state.phase === 'report-received') {
    return [{
      id: 'validate-report',
      label: 'Validate Report',
      description: 'Mark the report as valid (RM: RECEIVED → VALID)',
      enabled: true,
    }, {
      id: 'invalidate-report',
      label: 'Invalidate Report',
      description: 'Mark the report as invalid (RM: RECEIVED → INVALID)',
      enabled: true,
    }]
  }

  // Report invalidated - re-validate or close
  if (state.phase === 'report-invalidated') {
    return [{
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
  }

  // Embargo proposed - accept/reject
  if (state.phase === 'embargo-proposed' && !vendor.embargoAccepted) {
    return [{
      id: 'accept-embargo',
      label: 'Accept Embargo',
      description: 'Accept the 90-day embargo proposal',
      enabled: true,
    }, {
      id: 'reject-embargo',
      label: 'Reject Embargo',
      description: 'Reject the embargo proposal',
      enabled: true,
    }]
  }

  // Active embargo phases
  const embargoPhases = ['embargo-accepted', 'finder-asked', 'vendor-replied', 'fix-ready', 'fix-deployed']
  if (embargoPhases.includes(state.phase)) {
    const actions: Action[] = []

    // Reply to questions
    if (state.phase === 'finder-asked') {
      actions.push({
        id: 'vendor-reply-note',
        label: 'Reply to Question',
        description: 'Respond to Finder\'s question about workarounds',
        enabled: true,
      })
    }

    // Invite second vendor (only first vendor can do this for now)
    if (isVendor1 && !state.secondVendorInvited && !hasSecondVendor(state)) {
      actions.push({
        id: 'vendor-invite-second-vendor',
        label: 'Invite Second Vendor',
        description: 'Invite another vendor to collaborate on this case',
        enabled: true,
      })
    }

    // VFD progression
    if (vendor.vfdState === 'Vfd' && ['embargo-accepted', 'finder-asked', 'vendor-replied'].includes(state.phase)) {
      actions.push({
        id: 'notify-fix-ready',
        label: 'Notify Fix Ready',
        description: 'Vendor notifies that a fix is ready',
        enabled: true,
      })
    }

    if (vendor.vfdState === 'VFd') {
      actions.push({
        id: 'notify-fix-deployed',
        label: 'Notify Fix Deployed',
        description: 'Vendor notifies that the fix has been deployed',
        enabled: true,
      })
    }

    // Publication
    if (vendor.vfdState === 'VFD' && !state.pxaState.includes('P')) {
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

  // Post-publication phases
  if (['vendor-published', 'finder-published', 'finder-closed'].includes(state.phase) && !vendor.hasClosed) {
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

    // Publish if still not published
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

  // Second vendor just joined - show their available actions
  if (vendorId === 'vendor-2' && vendor.rmState === 'ACCEPTED') {
    const actions: Action[] = []

    // VFD progression for second vendor
    if (vendor.vfdState === 'Vfd') {
      actions.push({
        id: 'notify-fix-ready',
        label: 'Notify Fix Ready',
        description: 'Vendor notifies that a fix is ready',
        enabled: true,
      })
    }

    if (vendor.vfdState === 'VFd') {
      actions.push({
        id: 'notify-fix-deployed',
        label: 'Notify Fix Deployed',
        description: 'Vendor notifies that the fix has been deployed',
        enabled: true,
      })
    }

    if (vendor.vfdState === 'VFD' && !state.pxaState.includes('P')) {
      actions.push({
        id: 'vendor-notify-published',
        label: 'Notify Published',
        description: 'Vendor notifies that vulnerability is publicly disclosed',
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

  // Can propose embargo after validation
  if (state.phase === 'report-validated' || state.phase === 'embargo-rejected') {
    return [{
      id: 'propose-embargo',
      label: 'Propose 90-day Embargo',
      description: 'Propose a 90-day coordinated disclosure embargo',
      enabled: true,
    }]
  }

  return []
}

export function getExternalActions(state: DemoState): Action[] {
  // External events available after embargo is active
  if (state.emState === 'ACTIVE') {
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
