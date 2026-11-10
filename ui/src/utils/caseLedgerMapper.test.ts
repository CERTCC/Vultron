/**
 * Unit tests of the Log Replay mapper's lanes over a committed recording.
 *
 * `rv` is the smallest registered scenario: a Reporter, one Vendor and the
 * CASE_MANAGER. The recording is loaded with a `?raw` import, as
 * `App-logreplay.tsx` loads it, so a regenerated recording needs no edit here.
 */

import { describe, expect, it } from 'vitest'

import rcvcvLedgerRaw from '../recordings/rcvcv/case-actor.jsonl?raw'
import rvLedgerRaw from '../recordings/rv/case-actor.jsonl?raw'
import { PARTICIPANT_ROLES } from '../constants'
import { buildTimelineFromCaseLedger } from './caseLedgerMapper'
import { normalizeLedger, parseCaseLedger, type RejectedLedgerLine } from './caseLedgerParser'

const parsed = parseCaseLedger(rvLedgerRaw, 'rv')
const entries = normalizeLedger(parsed.entries)
const state = buildTimelineFromCaseLedger(entries)

describe('buildTimelineFromCaseLedger on the rv recording', () => {
  it('reads a non-empty recording with no rejected line', () => {
    expect(entries.length).toBeGreaterThan(0)
    expect(parsed.rejected).toEqual([])
  })

  it('draws the Reporter on top, then the Vendor, then the CASE_MANAGER', () => {
    const lanes = [...state.participants.values()].sort((a, b) => a.laneIndex - b.laneIndex)
    expect(lanes.map((p) => p.id)).toEqual(['reporter', 'vendor-1', 'casemanager'])
  })

  it('names and labels the Reporter and CASE_MANAGER lanes', () => {
    const reporter = state.participants.get('reporter')
    const caseManager = state.participants.get('casemanager')
    expect(reporter?.name).toBe('Reporter')
    expect(reporter?.role).toBe(PARTICIPANT_ROLES.reporter)
    expect(caseManager?.name).toBe('Case Manager')
    expect(caseManager?.role).toBe('CASE_MANAGER')
  })

  it('places every timeline event in a known lane', () => {
    expect(state.timelineEvents.length).toBeGreaterThan(0)
    const laneIndices = new Set([...state.participants.values()].map((p) => p.laneIndex))
    for (const event of state.timelineEvents) expect(laneIndices).toContain(event.lane)
  })

  it('puts the report node in the Reporter lane', () => {
    const reportEntries = entries.filter((e) => e.semanticType === 'add_report_to_case')
    expect(reportEntries).toHaveLength(1)
    const report = state.timelineEvents.find((e) => e.id === `${reportEntries[0].id}-decision`)
    expect(report).toBeDefined()
    expect(report?.lane).toBe(state.participants.get('reporter')?.laneIndex)
  })
})

/** The distinct VFD states a lane passes through, in step order. */
function vfdPath(state: ReturnType<typeof buildTimelineFromCaseLedger>, lane: string): string[] {
  const path: string[] = []
  for (const snapshot of state.stepSnapshots ?? []) {
    const vfd = snapshot.vfd[lane]
    if (vfd !== undefined && path[path.length - 1] !== vfd) path.push(vfd)
  }
  return path
}

describe('the VFD state read from vfState and dState', () => {
  it('takes a Vendor up the ladder from its vfState snapshots', () => {
    // rv's Vendor is not a DEPLOYER, so its statuses carry no dState: VF ends at VFd.
    expect(vfdPath(state, 'vendor-1')).toEqual(['vfd', 'Vfd', 'VFd'])
    expect(state.participants.get('vendor-1')?.vfd).toBe('VFd')
  })

  it('reads dState for a Vendor that is also a DEPLOYER', () => {
    // rcvcv's VendorDeployer (the `actor4:` host, lane vendor-3) deploys the fix.
    const rcvcv = buildTimelineFromCaseLedger(normalizeLedger(parseCaseLedger(rcvcvLedgerRaw).entries))
    expect(vfdPath(rcvcv, 'vendor-3')).toEqual(['vfd', 'Vfd', 'VFd', 'VFD'])
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
