/**
 * Unit tests of the Log Replay mapper.
 *
 * Over the `rv` recording, the smallest registered scenario (a Reporter, one
 * Vendor and the CASE_MANAGER), loaded with a `?raw` import as
 * `App-logreplay.tsx` loads it. The branches no recording reaches — the
 * `handleEntry` default branch and the recorded close path after a Leave — are
 * tested over hand-built ledgers. Every recording's whole replay is pinned by
 * `replayGolden.test.ts`.
 */

import { describe, expect, it } from 'vitest'

import rvLedgerRaw from '../recordings/rv/case-actor.jsonl?raw'
import inferredLedgerRaw from '../synthetic-ledgers/inferred-multistep-case-ledger.jsonl?raw'
import violationsLedgerRaw from '../synthetic-ledgers/violations-case-ledger.jsonl?raw'
import { PARTICIPANT_ROLES } from '../constants'
import { renderPhrase } from '../semanticRegistry'
import { buildTimelineFromCaseLedger } from './caseLedgerMapper'
import { normalizeLedger, parseCaseLedger, type CaseLedgerEntry, type RejectedLedgerLine } from './caseLedgerParser'
import type { CaseRole } from './replayLanes'
import { ACTORS, createCaseEntry, ledgerEntry, participantEntry, statePath, statusEntry } from './testing/ledgerEntries'

const parsed = parseCaseLedger(rvLedgerRaw, 'rv')
const entries = normalizeLedger(parsed.entries)
const state = buildTimelineFromCaseLedger(entries)

/** The participant labelled `name`. */
function laneNamed(s: ReturnType<typeof buildTimelineFromCaseLedger>, name: string) {
  const lane = [...s.participants.values()].find((p) => p.name === name)
  if (!lane) throw new Error(`no lane named ${name}`)
  return lane
}

describe('buildTimelineFromCaseLedger on the rv recording', () => {
  it('reads a non-empty recording with no rejected line', () => {
    expect(entries.length).toBeGreaterThan(0)
    expect(parsed.rejected).toEqual([])
  })

  it('draws the Reporter on top, then the Vendor, then the CASE_MANAGER, keyed on actor ids', () => {
    const lanes = [...state.participants.values()].sort((a, b) => a.laneIndex - b.laneIndex)
    expect(lanes.map((p) => p.name)).toEqual(['Reporter', 'Vendor', 'Case Manager'])
    expect(lanes.map((p) => p.id)).toEqual([
      'http://actor0:7999/api/v2/actors/actor0',
      'http://actor1:7999/api/v2/actors/actor1',
      'http://case-actor:7999/api/v2/actors/case-actor',
    ])
  })

  it('labels the Reporter and CASE_MANAGER lanes by their roles', () => {
    expect(laneNamed(state, 'Reporter').role).toBe(PARTICIPANT_ROLES.reporter)
    expect(laneNamed(state, 'Case Manager').role).toBe('CASE_MANAGER')
    expect(laneNamed(state, 'Case Manager').rmState).toBe('N/A')
  })

  it('places every timeline event in a known lane', () => {
    expect(state.timelineEvents.length).toBeGreaterThan(0)
    const laneIndices = new Set([...state.participants.values()].map((p) => p.laneIndex))
    for (const event of state.timelineEvents) expect(laneIndices).toContain(event.lane)
  })

  it('puts the report node in the Reporter lane, phrased as its submission', () => {
    const reportEntries = entries.filter((e) => e.semanticType === 'add_report_to_case')
    expect(reportEntries).toHaveLength(1)
    const report = state.timelineEvents.find((e) => e.id === `${reportEntries[0].id}-decision`)
    expect(report?.lane).toBe(laneNamed(state, 'Reporter').laneIndex)
    expect(report?.label).toBe(renderPhrase('submit_report', { actor: 'Reporter' }))
  })

})

describe('the VFD state read from vfState and dState', () => {
  it('takes a Vendor up the ladder from its vfState snapshots', () => {
    // rv's Vendor is not a DEPLOYER, so its statuses carry no dState: VF ends at VFd.
    const vendor = laneNamed(state, 'Vendor')
    expect(statePath(state, 'vfd', vendor.id)).toEqual(['vfd', 'Vfd', 'VFd'])
    expect(state.participants.get(vendor.id)?.vfd).toBe('VFd')
  })

  it('flags no VFD step of a recording as a violation or an inference', () => {
    expect(state.timelineEvents.filter((e) => e.violation || e.inferred)).toEqual([])
  })
})

describe('rejected ledger lines', () => {
  const rejected: RejectedLedgerLine[] = [
    { source: 'upload.jsonl', lineNumber: 4, problems: ['logIndex: missing (CaseLedgerEntry requires it)'], text: '{}' },
  ]
  const withRejected = buildTimelineFromCaseLedger(entries, rejected)

  it('are carried on the state for the replay view to show', () => {
    expect(withRejected.rejectedLines).toEqual(rejected)
    expect(state.rejectedLines).toEqual([])
  })

  it('head the event log with every problem', () => {
    expect(withRejected.eventLog.slice(0, 2)).toEqual([
      '⚠️ REJECTED upload.jsonl line 4: not a well-formed CaseLedgerEntry, not replayed',
      '  ↳ logIndex: missing (CaseLedgerEntry requires it)',
    ])
    expect(withRejected.eventLog.slice(2)).toEqual(state.eventLog)
  })

  it('leave the replayed timeline as it is', () => {
    expect(withRejected.timelineEvents).toEqual(state.timelineEvents)
  })
})

// ---------------------------------------------------------------------------
// Hand-built ledgers
// ---------------------------------------------------------------------------

const ROSTER: Record<string, CaseRole[]> = {
  [ACTORS.manager]: ['coordinator', 'case_manager'],
  [ACTORS.vendor]: ['vendor', 'case_owner'],
  [ACTORS.reporter]: ['reporter'],
}

const replay = (...rest: CaseLedgerEntry[]) => buildTimelineFromCaseLedger([createCaseEntry(ROSTER), ...rest])

describe('the handleEntry default branch', () => {
  it('logs a registered type with no handler in its phrase and draws no node', () => {
    const s = replay(ledgerEntry(1, 'engage_case', { type: 'Join', actor: ACTORS.vendor }))
    expect(s.timelineEvents.filter((e) => e.id.includes('/log/1-'))).toEqual([])
    expect(s.eventLog).toContain(`  ↳ engage_case: ${renderPhrase('engage_case', { actor: 'Vendor' })}`)
  })

  it('draws an unregistered type as an unrecognized node in its actor\'s lane', () => {
    const s = replay(ledgerEntry(1, 'frobnicate_case', { type: 'Frobnicate', actor: ACTORS.vendor }))
    const node = s.timelineEvents.find((e) => e.id.endsWith('/log/1-decision'))
    expect(node?.unrecognized).toBe(true)
    expect(node?.label).toBe('Unrecognized: Frobnicate case')
    expect(node?.unrecognizedNote).toContain('"frobnicate_case"')
    expect(node?.participantId).toBe(ACTORS.vendor)
    expect(node?.consequences).toEqual(['semanticType: frobnicate_case', 'payload type: Frobnicate'])
    expect(node?.violation).toBeUndefined()
    expect(s.eventLog).toContain('  ↳ UNRECOGNIZED semanticType "frobnicate_case" (not in the semantic registry)')
    // Its consequence nodes reach the other joined lanes, as any node's do.
    expect(s.timelineEvents.filter((e) => e.causedBy === node?.id).length).toBeGreaterThan(0)
  })

  it('draws an unregistered type with no actor in the CASE_MANAGER\'s lane', () => {
    const s = replay(ledgerEntry(1, 'frobnicate_case', { type: 'Frobnicate' }))
    const node = s.timelineEvents.find((e) => e.id.endsWith('/log/1-decision'))
    expect(node?.unrecognized).toBe(true)
    expect(node?.participantId).toBe(ACTORS.manager)
  })

  it('draws it in an Unattributed lane when the ledger names no lane at all', () => {
    const s = buildTimelineFromCaseLedger([ledgerEntry(0, 'frobnicate_case', { type: 'Frobnicate' })])
    expect(s.timelineEvents).toHaveLength(1)
    expect(s.timelineEvents[0].unrecognized).toBe(true)
    expect(s.participants.get(s.timelineEvents[0].participantId!)?.name).toBe('Unattributed')
  })
})

describe('the recorded close path after a Leave (isRecordedClosePath)', () => {
  // The Vendor is the receiver: seeded RECEIVED, then VALID, then it Leaves.
  const leave = ledgerEntry(3, 'close_case', { type: 'Leave', actor: ACTORS.vendor })
  const opening = [statusEntry(1, ACTORS.manager, ACTORS.vendor, 'VALID'), leave] as const
  const nodeFor = (s: ReturnType<typeof replay>, logIndex: number) =>
    s.timelineEvents.find((e) => e.id.endsWith(`/log/${logIndex}-decision`))

  it('logs, not flags, the case manager\'s next legal step strictly nearer CLOSED', () => {
    const s = replay(...opening, statusEntry(4, ACTORS.manager, ACTORS.vendor, 'DEFERRED'))
    expect(nodeFor(s, 4)).toBeUndefined()
    expect(s.eventLog).toContain('  ↳ recorded close path after Leave: Vendor RM VALID → DEFERRED → CLOSED')
    expect(s.participants.get(ACTORS.vendor)?.rmState).toBe('CLOSED')
  })

  it('logs the whole path when it is recorded step by step, then CLOSED', () => {
    const s = replay(
      ...opening,
      statusEntry(4, ACTORS.manager, ACTORS.vendor, 'DEFERRED'),
      statusEntry(5, ACTORS.manager, ACTORS.vendor, 'CLOSED')
    )
    expect(s.timelineEvents.filter((e) => e.violation)).toEqual([])
    expect(s.participants.get(ACTORS.vendor)?.rmState).toBe('CLOSED')
  })

  it('flags the same snapshot recorded by anyone but the case manager', () => {
    const s = replay(...opening, statusEntry(4, ACTORS.vendor, ACTORS.vendor, 'DEFERRED'))
    expect(nodeFor(s, 4)?.violation).toBe(true)
  })

  it('flags a repeated step', () => {
    const s = replay(
      ...opening,
      statusEntry(4, ACTORS.manager, ACTORS.vendor, 'DEFERRED'),
      statusEntry(5, ACTORS.manager, ACTORS.vendor, 'DEFERRED')
    )
    expect(nodeFor(s, 4)).toBeUndefined()
    expect(nodeFor(s, 5)?.violation).toBe(true)
  })

  it('flags a skipped rung', () => {
    // RECEIVED → ACCEPTED is two RM steps (validate, accept), not one.
    const s = replay(leave, statusEntry(4, ACTORS.manager, ACTORS.vendor, 'ACCEPTED'))
    expect(nodeFor(s, 4)?.violation).toBe(true)
  })
})

describe('the synthetic ledgers (synthetic-ledgers/README.md)', () => {
  const replayRaw = (raw: string) => buildTimelineFromCaseLedger(normalizeLedger(parseCaseLedger(raw).entries))
  const decisions = (s: ReturnType<typeof replayRaw>) => s.timelineEvents.filter((e) => e.type === 'decision')
  const logIndexOf = (id: string) => Number(id.match(/\/log\/(\d+)-decision$/)?.[1])

  it('flag exactly the three illegal steps of the violations ledger', () => {
    const s = replayRaw(violationsLedgerRaw)
    expect(decisions(s)).toHaveLength(8)
    expect(decisions(s).filter((e) => e.violation).map((e) => logIndexOf(e.id))).toEqual([2, 5, 7])
    expect(s.eventLog.filter((line) => line.includes('PROTOCOL VIOLATION'))).toHaveLength(3)
  })

  it('label the lanes by the roles the case records give them', () => {
    const s = replayRaw(violationsLedgerRaw)
    const lanes = [...s.participants.values()].sort((a, b) => a.laneIndex - b.laneIndex)
    expect(lanes.map((p) => p.name)).toEqual(['Reporter', 'Vendor', 'Case Manager'])
  })

  it('mark the multi-hop step of the inferred ledger as inferred, not a violation', () => {
    const s = replayRaw(inferredLedgerRaw)
    const marked = decisions(s).filter((e) => e.inferred || e.violation)
    expect(marked.map((e) => [logIndexOf(e.id), Boolean(e.inferred), Boolean(e.violation)])).toEqual([[1, true, false]])
  })
})

describe('handlers given an entry no lane can hold', () => {
  it.each([
    'validate_report',
    'add_note_to_case',
    'invite_actor_to_case',
    'accept_invite_actor_to_case',
    'reject_invite_actor_to_case',
    'offer_case_ownership_transfer',
    'accept_case_ownership_transfer',
    'offer_actor_to_case',
    'add_report_to_case',
  ])('log a %s entry with no actor in its phrase and draw no node', (semanticType) => {
    const s = replay(ledgerEntry(1, semanticType, { type: 'Activity' }))
    expect(s.timelineEvents.filter((e) => e.id.includes('/log/1-'))).toEqual([])
    expect(s.eventLog).toContain(`  ↳ ${semanticType}: ${renderPhrase(semanticType)}`)
  })
})

describe('the legacy verbs older uploaded logs carry', () => {
  it.each(['accept_case_manager_role', 'add_case_participant'])('log %s, never as unrecognized', (semanticType) => {
    const s = replay(ledgerEntry(1, semanticType, { type: 'Accept', actor: ACTORS.manager }))
    expect(s.timelineEvents.filter((e) => e.id.includes('/log/1-'))).toEqual([])
    expect(s.eventLog).toContain(`  ↳ ${semanticType}: ${renderPhrase(semanticType, { actor: 'Case Manager' })}`)
  })

  it('draws a create_note with its legacy Create(Note) form', () => {
    const s = replay(
      ledgerEntry(1, 'create_note', { type: 'Create', actor: ACTORS.reporter, object: { type: 'Note', name: 'Q' } })
    )
    const node = s.timelineEvents.find((e) => e.id.endsWith('/log/1-decision'))
    expect(node?.label).toBe(renderPhrase('create_note'))
    expect(node?.consequences).toEqual(['Create(Note)', 'Note: "Q"'])
  })

  it('closes the participant a legacy close_case names in attributedTo when the CASE_MANAGER is its actor', () => {
    const s = replay(
      ledgerEntry(1, 'close_case', {
        type: 'Leave',
        actor: ACTORS.manager,
        object: { type: 'VulnerabilityCase', attributedTo: ACTORS.vendor },
      })
    )
    const node = s.timelineEvents.find((e) => e.id.endsWith('/log/1-decision'))
    expect(node?.participantId).toBe(ACTORS.vendor)
    expect(s.participants.get(ACTORS.vendor)?.rmState).toBe('CLOSED')
  })
})

describe('the event log', () => {
  it('adds the entry\'s own phrase when the node depicts the act it follows', () => {
    const report = entries.find((e) => e.semanticType === 'add_report_to_case')!
    const depicted = renderPhrase('submit_report', { actor: 'Reporter' })
    const own = renderPhrase('add_report_to_case', { actor: 'Case Manager' })
    expect(report).toBeDefined()
    expect(state.eventLog.some((l) => l.endsWith(`] ${depicted} — ${own}`))).toBe(true)
  })

  it('gives a node whose label is its entry\'s phrase that phrase once', () => {
    const validate = state.eventLog.find((l) => l.includes(renderPhrase('validate_report', { actor: 'Vendor' })))
    expect(validate).toMatch(/\] Vendor validated the report$/)
  })
})

describe('a log whose records name no roles (an older upload)', () => {
  // Hosts that once picked the lanes (`//finder:`, `//vendor:`); nothing here
  // names a role, so none of them may decide a lane.
  const manager = 'http://vendor:7999/api/v2/actors/case-actor-1'
  const vendor = 'http://vendor:7999/api/v2/actors/vendor-1'
  const finder = 'http://finder:7999/api/v2/actors/finder-1'
  const s = buildTimelineFromCaseLedger([
    ledgerEntry(0, 'offer_case_manager_role', {
      type: 'Offer',
      actor: manager,
      object: {
        type: 'VulnerabilityCase',
        attributedTo: vendor,
        actorParticipantIndex: { [finder]: 'urn:p:0', [vendor]: 'urn:p:1', [manager]: 'urn:p:2' },
        caseStatuses: [{ type: 'CaseStatus', emState: 'ACTIVE', pxaState: 'pxa' }],
      },
    }),
    ledgerEntry(1, 'validate_report', { type: 'Accept', actor: vendor }),
  ])

  it('takes the actor of the bootstrap entry as the CASE_MANAGER', () => {
    expect(s.participants.get(manager)?.name).toBe('Case Manager')
    expect(s.participants.get(manager)?.rmState).toBe('N/A')
  })

  it('labels every other actor "Participant", never by its host', () => {
    expect([vendor, finder].map((id) => s.participants.get(id)?.name)).toEqual(['Participant', 'Participant 2'])
  })

  it('still seeds the case\'s attributedTo as the receiver, so its validation is legal', () => {
    const node = s.timelineEvents.find((e) => e.id.endsWith('/log/1-decision'))
    expect(node?.violation).toBeUndefined()
    expect(s.participants.get(vendor)?.rmState).toBe('VALID')
  })

  it('gives an unrecognized Reporter no RM=ACCEPTED seed', () => {
    expect(s.participants.get(finder)?.rmState).toBe('START')
  })
})

describe('lane fallbacks when an entry has no actor', () => {
  const nodeAt = (s: ReturnType<typeof replay>, logIndex: number) =>
    s.timelineEvents.find((e) => e.id.endsWith(`/log/${logIndex}-decision`))

  it.each([
    ['add_case_status_to_case', { type: 'Add', object: { type: 'CaseStatus', emState: 'EXITED', pxaState: 'pxa' } }],
    ['remove_embargo_event_from_case', { type: 'Remove' }],
    ['add_participant_status_to_participant', { type: 'Add', object: { type: 'ParticipantStatus', caseStatus: { type: 'CaseStatus', emState: 'EXITED' } } }],
    ['close_case', { type: 'Leave' }],
  ] as const)('draws %s in the CASE_MANAGER\'s lane', (semanticType, snapshot) => {
    const s = replay(ledgerEntry(1, semanticType, snapshot as never))
    expect(nodeAt(s, 1)?.participantId).toBe(ACTORS.manager)
  })

  it.each([
    ['add_case_status_to_case', { type: 'Add', object: { type: 'CaseStatus', emState: 'EXITED' } }],
    ['remove_embargo_event_from_case', { type: 'Remove' }],
    ['close_case', { type: 'Leave' }],
  ] as const)('draws %s in an Unattributed lane when the ledger has no lane', (semanticType, snapshot) => {
    const s = buildTimelineFromCaseLedger([ledgerEntry(0, semanticType, snapshot as never)])
    expect(s.participants.get(nodeAt(s, 0)!.participantId!)?.name).toBe('Unattributed')
  })

  it('draws a create_case with no actor and no receiver in the CASE_MANAGER\'s lane', () => {
    const s = buildTimelineFromCaseLedger([
      participantEntry(0, ACTORS.reporter, ['reporter']),
      participantEntry(0, ACTORS.manager, ['case_manager']),
      ledgerEntry(1, 'create_case', {
        type: 'Create',
        object: { type: 'VulnerabilityCase', actorParticipantIndex: { [ACTORS.reporter]: 'urn:p:0' } },
      }),
    ])
    expect(nodeAt(s, 1)?.participantId).toBe(ACTORS.manager)
    expect(s.participants.get(ACTORS.reporter)?.rmState).toBe('ACCEPTED')
  })
})
