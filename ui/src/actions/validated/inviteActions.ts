/**
 * Multi-vendor invite action handlers
 */

import type { DemoState } from '../../types'
import { getVendorColor } from '../../constants'
import {
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
} from '../../state/stateUpdaters'
import { getParticipant, getVendors, getActiveParticipants } from '../../state/participantHelpers'

/**
 * Generalized vendor invitation handler - works for inviting any vendor number
 */
export function handleInviteVendor(state: DemoState, inviterId: string = 'vendor-1'): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Get the inviter participant
  const inviter = getParticipant(state, inviterId)
  if (!inviter) return state

  // Calculate next vendor number based on existing vendors
  const existingVendors = getVendors(state)
  const nextVendorNumber = existingVendors.length + 1
  const nextVendorId = `vendor-${nextVendorNumber}`

  // Create new vendor participant
  // Per Vultron protocol: inviting a vendor = sending them the vulnerability report
  // They start at RM.RECEIVED and VFD.Vfd, just like Vendor 1 did when the report was submitted
  // Vendor becomes aware (Vfd) but cannot announce fix ready until report is validated
  // IMPORTANT: Per working_with_others.md lines 100-115:
  // - If embargo is ACTIVE, inviting participant SHALL propose existing embargo to invited participant
  // - Invited participant SHOULD accept the existing embargo
  // - Inviting participant SHOULD NOT share full report unless embargo is accepted
  // - Invited participant MAY propose revision after accepting
  const hasActiveEmbargo = state.emState === 'ACTIVE' || state.emState === 'REVISE'
  const newVendor = {
    id: nextVendorId,
    name: nextVendorNumber === 1 ? 'Vendor' : `Vendor ${nextVendorNumber}`,
    role: 'VENDOR',
    color: getVendorColor(nextVendorNumber),
    rmState: 'RECEIVED',  // They received the vulnerability report
    vfdState: 'Vfd',  // Vendor aware - must validate before progressing VFD
    embargoAccepted: false,  // Must explicitly accept embargo if one exists
    embargoProposedToParticipant: hasActiveEmbargo,  // Track if embargo was proposed to them
    hasPublished: false,
    hasClosed: false,
    visible: true,  // Visible immediately - they have the report and need to decide on embargo
    laneIndex: nextVendorNumber,  // Dynamic lane placement
  }

  // Add new vendor to participants
  const newParticipants = new Map(state.participants)
  newParticipants.set(nextVendorId, newVendor)

  // Adjust caseactor lane index to make room for new vendor
  const caseactor = newParticipants.get('caseactor')
  const oldCaseActorLane = caseactor?.laneIndex ?? nextVendorNumber + 1
  const newCaseActorLane = nextVendorNumber + 1

  if (caseactor) {
    const updatedCaseActor = { ...caseactor, laneIndex: newCaseActorLane }
    newParticipants.set('caseactor', updatedCaseActor)
    console.log(`Updated CaseActor from lane ${oldCaseActorLane} to lane ${newCaseActorLane}`)
  }

  // IMPORTANT: Update existing timeline events - shift CaseActor events to new lane
  const updatedTimelineEvents = state.timelineEvents.map(event => {
    if (event.lane === oldCaseActorLane) {
      console.log(`Shifting event '${event.label}' from lane ${oldCaseActorLane} to lane ${newCaseActorLane}`)
      return { ...event, lane: newCaseActorLane }
    }
    return event
  })

  // Track this vendor as invited
  const newInvitedVendors = new Set(state.invitedVendors)
  newInvitedVendors.add(nextVendorId)

  newState = {
    ...newState,
    participants: newParticipants,
    timelineEvents: updatedTimelineEvents,
    invitedVendors: newInvitedVendors,
  }

  // Get updated participant references from newState (after adjusting lane indices)
  const updatedInviter = getParticipant(newState, inviterId)
  const updatedCaseActorCheck = getParticipant(newState, 'caseactor')
  const updatedNewVendor = getParticipant(newState, nextVendorId)

  if (!updatedInviter || !updatedCaseActorCheck || !updatedNewVendor) {
    console.error('Failed to get participants:', { updatedInviter, updatedCaseActorCheck, updatedNewVendor })
    return newState
  }

  console.log(`After update - CaseActor laneIndex: ${updatedCaseActorCheck.laneIndex}, ${newVendor.name} laneIndex: ${updatedNewVendor.laneIndex}`)

  // Build events array manually to avoid TypeScript issues with conditional spreads
  const inviteEvents = []
  let timestampOffset = 0

  // Decision node in inviter's lane
  inviteEvents.push({
    id: eventId,
    actor: updatedInviter.name,
    participantId: inviterId,
    label: `Submit Report to ${newVendor.name}`,
    x: nextX,
    lane: updatedInviter.laneIndex,
    type: 'decision' as const,
    timestamp: now + timestampOffset,
    consequences: [
      `VulnerabilityReport sent to ${newVendor.name}`,
      'Offer(VulnerabilityReport) activity created',
      `Report sent to ${newVendor.name} inbox`,
      `${newVendor.name} enters case at RM.RECEIVED`,
    ],
  })
  timestampOffset++

  // Consequence nodes in ALL other participants' lanes (excluding inviter, new vendor, and caseactor)
  // This includes Finder and all existing vendors who didn't send the invite
  const otherParticipants = getActiveParticipants(newState).filter(p =>
    p.id !== inviterId &&
    p.id !== nextVendorId &&
    p.id !== 'caseactor'
  )

  otherParticipants.forEach(participant => {
    inviteEvents.push({
      id: `${eventId}-${participant.id}-consequence`,
      actor: participant.name,
      participantId: participant.id,
      label: `Report Sent to ${newVendor.name}`,
      x: nextX,
      lane: participant.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${updatedInviter.name} sent report to ${newVendor.name}`,
        `${newVendor.name} will receive report`,
        'Case expanded to include additional vendor',
      ],
    })
    timestampOffset++
  })

  // Consequence node in new vendor's lane (they receive the report)
  const embargoConsequences = hasActiveEmbargo
    ? [
        'Offer received in inbox',
        'VulnerabilityReport stored in DataLayer',
        `Existing embargo proposed to ${newVendor.name}`,
        `${newVendor.name} must accept embargo to proceed`,
        `${newVendor.name} RM state → RECEIVED`,
        `${newVendor.name} VFD state → Vfd (aware)`,
      ]
    : [
        'Offer received in inbox',
        'VulnerabilityReport stored in DataLayer',
        `${newVendor.name} RM state → RECEIVED`,
        `${newVendor.name} VFD state → Vfd (aware)`,
      ]

  inviteEvents.push({
    id: `${eventId}-${nextVendorId}-consequence`,
    actor: newVendor.name,
    participantId: nextVendorId,
    label: hasActiveEmbargo ? 'Report + Embargo Received' : 'Report Received',
    x: nextX,
    lane: updatedNewVendor.laneIndex,
    type: 'consequence' as const,
    causedBy: eventId,
    timestamp: now + timestampOffset,
    consequences: embargoConsequences,
  })
  timestampOffset++

  // Consequence node in CaseActor lane (use updated caseactor from earlier)
  inviteEvents.push({
    id: `${eventId}-caseactor-consequence`,
    actor: 'CaseActor',
    participantId: 'caseactor',
    label: `${newVendor.name} Added`,
    x: nextX,
    lane: updatedCaseActorCheck.laneIndex,
    type: 'consequence' as const,
    causedBy: eventId,
    timestamp: now + timestampOffset,
    consequences: [
      `${newVendor.name} participant created`,
      `${newVendor.name} added to case participants`,
      'Case now has multiple vendors',
      'Authoritative ledger updated',
    ],
  })

  console.log(`Creating invite events - Decision at lane ${updatedInviter.laneIndex}, ${newVendor.name} consequence at lane ${updatedNewVendor.laneIndex}, CaseActor consequence at lane ${updatedCaseActorCheck.laneIndex}`)

  newState = addTimelineEvents(newState, inviteEvents)

  newState = addEventLogEntries(newState, [`${inviter.name} sent vulnerability report to ${newVendor.name}`])
  newState = incrementXPosition(newState)

  return newState
}

// Legacy function name for backward compatibility - now just calls handleInviteVendor
export function handleInviteSecondVendor(state: DemoState, inviterId: string = 'vendor-1'): DemoState {
  return handleInviteVendor(state, inviterId)
}

/**
 * DEPRECATED: This function is no longer used since vendors are immediately visible when invited.
 * Kept for backward compatibility only.
 */
export function handleAcceptSecondVendorInvite(state: DemoState): DemoState {
  console.warn('handleAcceptSecondVendorInvite is deprecated - vendors are now immediately visible')
  // No-op: vendors are immediately visible when invited, no separate accept step needed
  return state
}

/**
 * DEPRECATED: This function is no longer used since vendors are immediately visible when invited.
 * Kept for backward compatibility only.
 */
export function handleRejectSecondVendorInvite(state: DemoState): DemoState {
  console.warn('handleRejectSecondVendorInvite is deprecated - vendors are now immediately visible')
  // No-op: vendors are immediately visible when invited, no separate reject step needed
  return state
}
