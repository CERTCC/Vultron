/**
 * Maps CaseLogEntry events to timeline events for visualization
 */

import type { DemoState, ParticipantState } from '../types'
import type { TimelineEvent } from '../types'
import { PARTICIPANT_COLORS, PARTICIPANT_ROLES, INITIAL_X_POSITION } from '../constants'
import { extractActorType, extractParticipantStatus, type CaseLogEntry } from './jsonlParser'

const EVENT_SPACING = 200

/**
 * Initialize demo state from log entries
 */
export function initializeStateFromLogs(entries: CaseLogEntry[]): DemoState {
  const participants = new Map<string, ParticipantState>()

  // Find all unique actors from the logs
  const actorTypes = new Set<string>()
  entries.forEach(entry => {
    if (entry.payloadSnapshot?.actor) {
      const actorType = extractActorType(entry.payloadSnapshot.actor)
      actorTypes.add(actorType)
    }
  })

  let laneIndex = 0

  // Initialize Finder if present
  if (actorTypes.has('finder')) {
    participants.set('finder', {
      id: 'finder',
      name: 'Finder',
      role: PARTICIPANT_ROLES.finder,
      color: PARTICIPANT_COLORS.finder,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: true,
      laneIndex: laneIndex++,
    })
  }

  // Initialize Vendor if present
  if (actorTypes.has('vendor-1')) {
    participants.set('vendor-1', {
      id: 'vendor-1',
      name: 'Vendor',
      role: PARTICIPANT_ROLES.vendor,
      color: PARTICIPANT_COLORS.vendor1,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: true,
      laneIndex: laneIndex++,
    })
  }

  // Initialize CaseActor if present
  if (actorTypes.has('caseactor')) {
    participants.set('caseactor', {
      id: 'caseactor',
      name: 'Case Actor',
      role: PARTICIPANT_ROLES.caseactor,
      color: PARTICIPANT_COLORS.caseactor,
      rmState: 'N/A',
      vfdState: 'N/A',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible: true,
      laneIndex: laneIndex++,
    })
  }

  return {
    phase: 'replay',
    participants,
    emState: 'NONE',
    pxaState: 'pxa',
    timelineEvents: [],
    eventLog: [],
    nextXPosition: INITIAL_X_POSITION,
    invitedVendors: new Set<string>(),
  }
}

/**
 * Convert a CaseLogEntry to timeline events
 */
export function mapLogEntryToTimelineEvents(
  entry: CaseLogEntry,
  state: DemoState,
  eventIndex: number
): { events: TimelineEvent[], stateUpdates: Partial<DemoState> } {
  const events: TimelineEvent[] = []
  const stateUpdates: Partial<DemoState> = {}

  const xPosition = INITIAL_X_POSITION + (eventIndex * EVENT_SPACING)

  switch (entry.eventType) {
    // submit_report and engage_case are now handled by the grouping logic in buildTimelineFromLogs
    // This function only handles individual status updates and other events
    case 'submit_report':
    case 'engage_case':
      // These are handled in buildTimelineFromLogs grouping logic
      break

    case 'add_participant_status': {
      const status = extractParticipantStatus(entry.payloadSnapshot)
      if (status) {
        const actorType = extractActorType(entry.payloadSnapshot?.object?.attributedTo)
        const participantId = actorType
        const participant = state.participants.get(participantId)

        if (participant) {
          const label = `Status: ${status.rmState} ${status.vfdState}`

          events.push({
            id: `${entry.id}-status`,
            actor: participantId,
            participantId,
            label,
            x: xPosition,
            lane: participant.laneIndex,
            type: 'consequence',
            consequences: [],
            timestamp: new Date(entry.receivedAt).getTime(),
          })

          // Update case status if present
          if (status.caseStatus) {
            stateUpdates.emState = status.caseStatus.emState
            stateUpdates.pxaState = status.caseStatus.pxaState
          }
        }
      }
      break
    }

    case 'remove_embargo_event_from_case': {
      const actorType = extractActorType(entry.payloadSnapshot?.actor)
      const participantId = actorType
      const participant = state.participants.get(participantId)

      if (participant) {
        events.push({
          id: `${entry.id}-decision`,
          actor: participantId,
          participantId,
          label: 'Embargo Terminated',
          x: xPosition,
          lane: participant.laneIndex,
          type: 'decision',
          consequences: [],
          timestamp: new Date(entry.receivedAt).getTime(),
        })

        stateUpdates.emState = 'EXITED'
      }
      break
    }

    case 'demo_verification':
      // Skip demo verification events - they're not relevant for visualization
      break

    default:
      // For unknown event types, create a generic event
      console.log(`Unknown event type: ${entry.eventType}`)
      break
  }

  return { events, stateUpdates }
}

/**
 * Process all log entries and build complete timeline
 * Groups related events (decision + consequences) by timestamp
 */
export function buildTimelineFromLogs(entries: CaseLogEntry[]): DemoState {
  let state = initializeStateFromLogs(entries)

  // Group entries by timestamp and event type to identify decision+consequence clusters
  const eventGroups = new Map<string, CaseLogEntry[]>()

  entries.forEach((entry) => {
    // Group by event type and approximate timestamp (within 1 second)
    const timestamp = new Date(entry.receivedAt).getTime()
    const roundedTime = Math.floor(timestamp / 1000) * 1000
    const groupKey = `${entry.eventType}:${roundedTime}`

    if (!eventGroups.has(groupKey)) {
      eventGroups.set(groupKey, [])
    }
    eventGroups.get(groupKey)!.push(entry)
  })

  let visualEventIndex = 0

  // Process each group
  Array.from(eventGroups.values()).forEach((group) => {
    if (group.length === 0) return

    const firstEntry = group[0]
    const xPosition = INITIAL_X_POSITION + (visualEventIndex * EVENT_SPACING)

    // Determine which entry represents the decision (the actor who initiated it)
    let decisionEntry: CaseLogEntry | null = null
    const consequenceEntries: CaseLogEntry[] = []

    // For submit_report: finder is the decision maker
    // For engage_case: vendor is the decision maker
    if (firstEntry.eventType === 'submit_report') {
      decisionEntry = group.find(e => extractActorType(e.payloadSnapshot?.actor) === 'finder') || group[0]
      consequenceEntries.push(...group.filter(e => e !== decisionEntry))
    } else if (firstEntry.eventType === 'engage_case') {
      decisionEntry = group.find(e => extractActorType(e.payloadSnapshot?.actor) === 'vendor-1') || group[0]
      consequenceEntries.push(...group.filter(e => e !== decisionEntry))
    } else {
      // For other events, process them individually
      group.forEach((entry) => {
        const { events, stateUpdates } = mapLogEntryToTimelineEvents(entry, state, visualEventIndex)
        state = {
          ...state,
          ...stateUpdates,
          timelineEvents: [...state.timelineEvents, ...events],
        }
        if (events.length > 0) {
          const logMessage = `[${new Date(entry.receivedAt).toLocaleTimeString()}] ${entry.eventType}`
          state.eventLog.push(logMessage)
        }
      })
      return
    }

    if (!decisionEntry) return

    // Create decision node
    const decisionActorType = extractActorType(decisionEntry.payloadSnapshot?.actor)
    const decisionParticipant = state.participants.get(decisionActorType)

    if (!decisionParticipant) return

    const decisionId = `${decisionEntry.id}-decision`
    const events: TimelineEvent[] = [{
      id: decisionId,
      actor: decisionActorType,
      participantId: decisionActorType,
      label: firstEntry.eventType === 'submit_report' ? 'Submit Report' : 'Engage Case',
      x: xPosition,
      lane: decisionParticipant.laneIndex,
      type: 'decision',
      consequences: [],
      timestamp: new Date(decisionEntry.receivedAt).getTime(),
    }]

    // Create consequence nodes for each other participant who received this event
    consequenceEntries.forEach((consEntry) => {
      const consActorType = extractActorType(consEntry.payloadSnapshot?.actor)
      const consParticipant = state.participants.get(consActorType)

      if (consParticipant && consActorType !== decisionActorType) {
        events.push({
          id: `${decisionId}-consequence-${consActorType}`,
          actor: consActorType,
          participantId: consActorType,
          label: firstEntry.eventType === 'submit_report' ? 'Report Received' : 'Case Notification',
          x: xPosition,
          lane: consParticipant.laneIndex,
          type: 'consequence',
          consequences: [],
          causedBy: decisionId,
          timestamp: new Date(consEntry.receivedAt).getTime() + 1,
        })
      }
    })

    state = {
      ...state,
      timelineEvents: [...state.timelineEvents, ...events],
    }

    const logMessage = `[${new Date(decisionEntry.receivedAt).toLocaleTimeString()}] ${decisionEntry.eventType}`
    state.eventLog.push(logMessage)

    visualEventIndex++
  })

  return state
}
