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
import { getActiveLanes, getTotalLaneCount } from '../state/participantHelpers'

export function handleInviteSecondVendor(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Create second vendor participant
  const vendor2 = {
    id: 'vendor-2',
    name: 'Vendor 2',
    role: PARTICIPANT_ROLES.vendor2,
    color: PARTICIPANT_COLORS.vendor2,
    rmState: 'INVITED',
    vfdState: 'vfd',
    embargoAccepted: state.emState === 'ACTIVE',  // Auto-accept embargo if already active
    hasPublished: false,
    hasClosed: false,
    visible: false,  // Will become visible when they accept
    laneIndex: 2,  // Insert between vendor-1 and caseactor
  }

  // Add vendor-2 to participants
  const newParticipants = new Map(state.participants)
  newParticipants.set('vendor-2', vendor2)

  // Adjust caseactor lane index to make room
  const caseactor = newParticipants.get('caseactor')
  if (caseactor) {
    newParticipants.set('caseactor', { ...caseactor, laneIndex: 3 })
  }

  newState = { ...newState, participants: newParticipants, secondVendorInvited: true }

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Invite Vendor 2',
      x: nextX,
      lane: 1,
      type: 'decision',
      timestamp: now,
      consequences: [
        'RmInviteToCaseActivity created',
        'Invitation sent to Vendor 2',
        'Vendor 2 can accept or reject',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['Vendor invited Vendor 2 to the case'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleAcceptSecondVendorInvite(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Make vendor-2 visible and update their state
  newState = updateParticipant(newState, 'vendor-2', {
    visible: true,
    rmState: 'ACCEPTED',
    vfdState: 'Vfd',
  })

  newState = { ...newState, secondVendorAccepted: true }

  const activeLanes = getActiveLanes(newState)
  const vendor2 = newState.participants.get('vendor-2')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Accept Invitation',
      x: nextX,
      lane: vendor2?.laneIndex || 2,
      type: 'decision',
      timestamp: now,
      consequences: [
        'RmAcceptInviteToCaseActivity created',
        'Vendor 2 joins the case',
        'Vendor 2 RM → ACCEPTED',
        'Can now work independently on the vulnerability',
      ],
    },
    {
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Vendor 2 Added',
      x: nextX,
      lane: 3,
      type: 'consequence',
      timestamp: now + 1,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'Vendor 2 participant created',
        'Vendor 2 added to case participants',
        'Case now has multiple vendors',
        'Each vendor tracks VFD independently',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['Vendor 2 accepted invitation and joined the case'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleRejectSecondVendorInvite(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  // Remove vendor-2 from participants
  const newParticipants = new Map(state.participants)
  newParticipants.delete('vendor-2')

  // Restore caseactor lane index
  const caseactor = newParticipants.get('caseactor')
  if (caseactor) {
    newParticipants.set('caseactor', { ...caseactor, laneIndex: 2 })
  }

  newState = { ...newState, participants: newParticipants, secondVendorInvited: false }

  newState = addEventLogEntries(newState, ['Vendor 2 rejected invitation'])
  newState = incrementXPosition(newState)

  return newState
}
