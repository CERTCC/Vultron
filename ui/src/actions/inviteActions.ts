/**
 * Multi-vendor invite action handlers
 */

import type { DemoState } from '../types'
import { PARTICIPANT_COLORS, PARTICIPANT_ROLES } from '../constants'
import {
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
  updateParticipant,
} from '../state/stateUpdaters'
import { getParticipant } from '../state/participantHelpers'

export function handleInviteSecondVendor(state: DemoState, inviterId: string = 'vendor-1'): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Get the inviter participant
  const inviter = getParticipant(state, inviterId)
  if (!inviter) return state

  // Create second vendor participant
  // Per Vultron protocol: inviting a vendor = sending them the vulnerability report
  // They start at RM.RECEIVED and VFD.Vfd, just like Vendor 1 did when the report was submitted
  // Vendor becomes aware (Vfd) but cannot announce fix ready until report is validated
  const vendor2 = {
    id: 'vendor-2',
    name: 'Vendor 2',
    role: PARTICIPANT_ROLES.vendor2,
    color: PARTICIPANT_COLORS.vendor2,
    rmState: 'RECEIVED',  // They received the vulnerability report
    vfdState: 'Vfd',  // Vendor aware - must validate before progressing VFD
    embargoAccepted: state.emState === 'ACTIVE',  // Auto-accept embargo if already active
    hasPublished: false,
    hasClosed: false,
    visible: true,  // Visible immediately - they have the report and need to validate
    laneIndex: 2,  // Insert between vendor-1 and caseactor
  }

  // Add vendor-2 to participants
  const newParticipants = new Map(state.participants)
  newParticipants.set('vendor-2', vendor2)

  // Adjust caseactor lane index to make room for vendor-2
  const caseactor = newParticipants.get('caseactor')
  if (caseactor) {
    const updatedCaseActor = { ...caseactor, laneIndex: 3 }
    newParticipants.set('caseactor', updatedCaseActor)
    console.log('Updated CaseActor to lane:', updatedCaseActor.laneIndex)
  }

  // IMPORTANT: Update existing timeline events - shift CaseActor events from lane 2 to lane 3
  const updatedTimelineEvents = state.timelineEvents.map(event => {
    // If event is at lane 2 (old CaseActor position), move it to lane 3
    if (event.lane === 2) {
      console.log('Shifting event', event.label, 'from lane 2 to lane 3')
      return { ...event, lane: 3 }
    }
    return event
  })

  newState = {
    ...newState,
    participants: newParticipants,
    timelineEvents: updatedTimelineEvents,
    secondVendorInvited: true,
    secondVendorAccepted: true  // Vendor 2 is immediately visible (they received the report)
  }

  // Get updated participant references from newState (after adjusting lane indices)
  const updatedInviter = getParticipant(newState, inviterId)
  const updatedCaseActorCheck = getParticipant(newState, 'caseactor')

  if (!updatedInviter || !updatedCaseActorCheck) {
    console.error('Failed to get participants:', { updatedInviter, updatedCaseActorCheck })
    return newState
  }

  console.log('After update - CaseActor laneIndex:', updatedCaseActorCheck.laneIndex, 'Vendor-2 laneIndex:', vendor2.laneIndex)

  // Get the other actor (Finder or Vendor-1, whichever didn't invite)
  const otherActorId = inviterId === 'finder' ? 'vendor-1' : 'finder'
  const otherActor = getParticipant(newState, otherActorId)

  // Build events array manually to avoid TypeScript issues with conditional spreads
  const inviteEvents = []

  // Decision node in inviter's lane
  inviteEvents.push({
    id: eventId,
    actor: updatedInviter.name,
    participantId: inviterId,
    label: 'Submit Report to Vendor 2',
    x: nextX,
    lane: updatedInviter.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'VulnerabilityReport sent to Vendor 2',
      'Offer(VulnerabilityReport) activity created',
      'Report sent to Vendor 2 inbox',
      'Vendor 2 enters case at RM.RECEIVED',
    ],
  })

  // Consequence node in other actor's lane (if exists and still active)
  if (otherActor && !otherActor.hasClosed) {
    inviteEvents.push({
      id: `${eventId}-${otherActorId}-consequence`,
      actor: otherActor.name,
      participantId: otherActorId,
      label: 'Report Sent to Vendor 2',
      x: nextX,
      lane: otherActor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 1,
      consequences: [
        `${updatedInviter.name} sent report to Vendor 2`,
        'Vendor 2 will receive report',
        'Case may expand to multiple vendors',
      ],
    })
  }

  // Consequence node in Vendor 2's lane (they receive the report)
  const vendor2Updated = getParticipant(newState, 'vendor-2')
  inviteEvents.push({
    id: `${eventId}-vendor2-consequence`,
    actor: 'Vendor 2',
    participantId: 'vendor-2',
    label: 'Report Received',
    x: nextX,
    lane: vendor2Updated?.laneIndex ?? 2,
    type: 'consequence' as const,
    causedBy: eventId,
    timestamp: now + 2,
    consequences: [
      'Offer received in inbox',
      'VulnerabilityReport stored in DataLayer',
      'Vendor 2 RM state → RECEIVED',
      'Vendor 2 VFD state → Vfd (aware)',
    ],
  })

  // Consequence node in CaseActor lane (use updated caseactor from earlier)
  inviteEvents.push({
    id: `${eventId}-caseactor-consequence`,
    actor: 'CaseActor',
    participantId: 'caseactor',
    label: 'Vendor 2 Added',
    x: nextX,
    lane: updatedCaseActorCheck.laneIndex,
    type: 'consequence' as const,
    causedBy: eventId,
    timestamp: now + 3,
    consequences: [
      'Vendor 2 participant created',
      'Vendor 2 added to case participants',
      'Case now has multiple vendors',
      'Authoritative ledger updated',
    ],
  })

  console.log('Creating invite events - Decision at lane', updatedInviter.laneIndex, 'Vendor-2 consequence at lane', vendor2Updated?.laneIndex, 'CaseActor consequence at lane', updatedCaseActorCheck.laneIndex)

  newState = addTimelineEvents(newState, inviteEvents)

  newState = addEventLogEntries(newState, [`${inviter.name} sent vulnerability report to Vendor 2`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleAcceptSecondVendorInvite(state: DemoState): DemoState {
  console.log('handleAcceptSecondVendorInvite called')
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Make vendor-2 visible and update their state
  // NOTE: This handler is now obsolete since Vendor 2 becomes visible immediately when invited
  // Keeping for backward compatibility if somehow the old "accept invitation" flow is triggered
  newState = updateParticipant(newState, 'vendor-2', {
    visible: true,
    rmState: 'RECEIVED',  // They received the report and need to validate
    vfdState: 'Vfd',  // Vendor aware - can work on fix immediately
  })

  newState = { ...newState, secondVendorAccepted: true }

  const vendor2 = newState.participants.get('vendor-2')
  const finder = getParticipant(newState, 'finder')
  const vendor1 = getParticipant(newState, 'vendor-1')
  const caseactor = getParticipant(newState, 'caseactor')

  // Build events array manually to avoid TypeScript inference issues
  const acceptEvents = []

  // Decision node in Vendor 2's lane
  acceptEvents.push({
    id: eventId,
    actor: 'Vendor 2',
    participantId: 'vendor-2',
    label: 'Accept Invitation',
    x: nextX,
    lane: vendor2?.laneIndex || 2,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'AcceptInviteActorToCaseActivity created',
      'Vendor 2 joins the case',
      'Vendor 2 RM: START → RECEIVED',
      'Vendor 2 needs to validate the report',
    ],
  })

  // Consequence node in Finder's lane (if still active)
  if (finder && !finder.hasClosed) {
    acceptEvents.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Vendor 2 Joined',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 1,
      consequences: [
        'Vendor 2 accepted invitation',
        'Case now has multiple vendors',
        'Additional vendor can work on fix',
      ],
    })
  }

  // Consequence node in Vendor 1's lane (if still active)
  if (vendor1 && !vendor1.hasClosed) {
    acceptEvents.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Vendor 2 Joined',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 2,
      consequences: [
        'Vendor 2 accepted invitation',
        'Another vendor joins the case',
        'Vendors can coordinate on fix',
      ],
    })
  }

  // Consequence node in CaseActor's lane
  if (caseactor) {
    acceptEvents.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Vendor 2 Added',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + 3,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'Vendor 2 participant created',
        'Vendor 2 added to case participants',
        'Case now has multiple vendors',
        'Each vendor tracks VFD independently',
        'Authoritative ledger updated',
      ],
    })
  }

  console.log('Adding', acceptEvents.length, 'events for Vendor 2 accept')
  newState = addTimelineEvents(newState, acceptEvents)

  newState = addEventLogEntries(newState, ['Vendor 2 accepted invitation and joined the case'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleRejectSecondVendorInvite(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Keep vendor-2 visible but update their state to show rejection
  newState = updateParticipant(newState, 'vendor-2', {
    visible: true,
    rmState: 'DECLINED',
  })

  // Update flag to indicate rejection (but keep secondVendorInvited true since invitation happened)
  newState = { ...newState, secondVendorAccepted: false }

  const vendor2 = getParticipant(newState, 'vendor-2')
  const finder = getParticipant(newState, 'finder')
  const vendor1 = getParticipant(newState, 'vendor-1')
  const caseactor = getParticipant(newState, 'caseactor')

  const rejectEvents = []
  let timestampOffset = 0

  // Decision node in Vendor 2's lane
  if (vendor2) {
    rejectEvents.push({
      id: eventId,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Reject Invitation',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'decision' as const,
      timestamp: now,
      consequences: [
        'RejectInvitationActivity created',
        'Vendor 2 declines to join the case',
        'Vendor 2 RM → DECLINED',
        'Case continues with existing participants',
      ],
    })
    timestampOffset++
  }

  // Consequence node in Finder's lane (if still active)
  if (finder && !finder.hasClosed) {
    rejectEvents.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Invitation Declined',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Vendor 2 declined invitation',
        'Case continues without Vendor 2',
        'Can invite other vendors if needed',
      ],
    })
    timestampOffset++
  }

  // Consequence node in Vendor 1's lane (if still active)
  if (vendor1 && !vendor1.hasClosed) {
    rejectEvents.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Invitation Declined',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Vendor 2 declined invitation',
        'Case continues without Vendor 2',
        'Can continue work independently',
      ],
    })
    timestampOffset++
  }

  // Consequence node in CaseActor's lane
  if (caseactor) {
    rejectEvents.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Invitation Declined',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        'Vendor 2 declined invitation',
        'RejectInvitationActivity tracked',
        'Authoritative ledger updated',
        'Case participant count unchanged',
      ],
    })
  }

  newState = addTimelineEvents(newState, rejectEvents)

  newState = addEventLogEntries(newState, ['Vendor 2 rejected invitation'])
  newState = incrementXPosition(newState)

  return newState
}
