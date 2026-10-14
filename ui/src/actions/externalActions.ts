/**
 * External event action handlers (exploits, attacks)
 */

import type { DemoState } from '../types'
import {
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
  setPxaState,
} from '../state/stateUpdaters'
import { getActiveParticipants } from '../state/participantHelpers'
import { requireNextState } from '../protocol'

export function handleTriggerExploit(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  // Determine new PXA state. Per the Vultron protocol, exploit publication (X)
  // automatically implies public awareness (P): states pXa/pXA are not reachable
  // here because once an exploit is public, the public is aware. This is modeled
  // as a COMPOSITE of two legal pxa-machine steps — `exploit_made_public` then
  // `public_becomes_aware` — each computed from the protocol artifact, so the
  // result (pxa→PXa, pxA→PXA, etc.) is grounded in the JSON rather than hardcoded.
  const currentPxa = state.pxaState
  const afterExploit = requireNextState('pxa', currentPxa, 'exploit_made_public')
  // Apply the implied public-awareness step only when P is not already set; if it
  // is (Pxa/PxA), the exploit step above already produced a P-bearing state.
  const newPxa = afterExploit.includes('P')
    ? afterExploit
    : requireNextState('pxa', afterExploit, 'public_becomes_aware')

  let newState = state
  newState = setPxaState(newState, newPxa)

  // Per Vultron protocol (transitions.md:291-293): once the vuln is public, the
  // embargo's fate depends on its state (same rule as vendor publication):
  // - Active/Revise embargoes TERMINATE → EXITED (em `terminate`).
  // - A merely PROPOSED embargo was never active, so publication implicitly
  //   REJECTS it → NONE (em `reject`), NOT `terminate`.
  // Both destinations are computed from the protocol artifact.
  const hadActiveEmbargo = state.emState === 'ACTIVE' || state.emState === 'REVISE'
  const hadProposedEmbargo = state.emState === 'PROPOSED'

  if (newPxa.includes('P')) {
    if (hadActiveEmbargo) {
      newState = { ...newState, emState: requireNextState('em', state.emState, 'terminate') }
    } else if (hadProposedEmbargo) {
      newState = { ...newState, emState: requireNextState('em', state.emState, 'reject') }
    }
  }

  const activeLanes = getActiveParticipants(newState)

  // Create consequence nodes for all active participants
  const publicBecameAware = !currentPxa.includes('P') && newPxa.includes('P')
  const events = activeLanes.map((participant, index) => ({
    id: `${eventId}-${participant.id}-consequence`,
    actor: participant.name,
    participantId: participant.id,
    label: 'Exploit Published',
    x: nextX,
    lane: participant.laneIndex,
    type: 'consequence' as const,
    timestamp: now + index,
    consequences: [
      'External event: exploit published',
      ...(publicBecameAware ? ['Public becomes aware (automatic with X)'] : []),
      ...(hadActiveEmbargo ? ['Embargo TERMINATED (public awareness)'] : []),
      ...(hadProposedEmbargo ? ['Embargo proposal invalidated (public awareness)'] : []),
      `${participant.name} observes exploit`,
      'Participant pxa_state updated',
      `Case PXA state: ${currentPxa} → ${newPxa}`,
      ...(hadActiveEmbargo ? ['EM state: ACTIVE → EXITED'] : []),
      ...(hadProposedEmbargo ? ['EM state: PROPOSED → NONE'] : []),
      'Authoritative ledger updated',
    ],
  }))

  newState = addTimelineEvents(newState, events)

  const logEntries = []
  if (publicBecameAware) {
    logEntries.push('Exploit published in the wild (external event) - public becomes aware')
  } else {
    logEntries.push('Exploit published in the wild (external event)')
  }
  if (hadActiveEmbargo) {
    logEntries.push('⚠️ Embargo TERMINATED due to public awareness')
  } else if (hadProposedEmbargo) {
    logEntries.push('⚠️ Embargo proposal invalidated due to public awareness')
  }

  newState = addEventLogEntries(newState, logEntries)
  newState = incrementXPosition(newState)

  return newState
}

export function handleTriggerAttacks(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  // Determine new PXA state. Attacks being observed (A) is a single legal step in
  // the pxa machine (`attacks_are_observed`); destination computed from the
  // protocol artifact (pxa→pxA, pXa→pXA, Pxa→PxA, PXa→PXA). Unlike an exploit,
  // observing attacks does NOT imply public awareness, so no P is forced here.
  const currentPxa = state.pxaState
  const newPxa = requireNextState('pxa', currentPxa, 'attacks_are_observed')

  let newState = state
  newState = setPxaState(newState, newPxa)

  const activeLanes = getActiveParticipants(newState)

  // Create consequence nodes for all active participants
  const events = activeLanes.map((participant, index) => ({
    id: `${eventId}-${participant.id}-consequence`,
    actor: participant.name,
    participantId: participant.id,
    label: 'Attacks Observed',
    x: nextX,
    lane: participant.laneIndex,
    type: 'consequence' as const,
    timestamp: now + index,
    consequences: [
      'External event: attacks observed in the wild',
      `${participant.name} becomes aware`,
      'Participant pxa_state updated',
      `Case PXA state: ${currentPxa} → ${newPxa}`,
      'Authoritative ledger updated',
    ],
  }))

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['Attacks observed in the wild (external event)'])
  newState = incrementXPosition(newState)

  return newState
}
