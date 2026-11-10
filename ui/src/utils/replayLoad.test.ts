/**
 * Unit tests of the Log Replay view's load and panel rules (`replayLoad.ts`).
 */

import { describe, expect, it } from 'vitest'

import rvLedgerRaw from '../recordings/rv/case-actor.jsonl?raw'
import { buildTimelineFromCaseLedger } from './caseLedgerMapper'
import { normalizeLedger, parseCaseLedger, type ParsedLedger, type RejectedLedgerLine } from './caseLedgerParser'
import { EMPTY_LEDGER, laneVfdState, ledgerLoadError, mergeLedgers } from './replayLoad'

const rv = parseCaseLedger(rvLedgerRaw, 'rv')

function rejectedLine(source: string, lineNumber: number, text = `{"line": ${lineNumber}}`): RejectedLedgerLine {
  return { source, lineNumber, problems: [`problem at ${lineNumber}`], text }
}

describe('mergeLedgers', () => {
  it('keeps every entry and every rejected line, in order', () => {
    const first: ParsedLedger = { entries: rv.entries.slice(0, 2), rejected: [rejectedLine('a.jsonl', 3)] }
    const second: ParsedLedger = { entries: rv.entries.slice(2, 3), rejected: [rejectedLine('b.jsonl', 1)] }
    const merged = mergeLedgers([first, second])
    expect(merged.entries).toEqual(rv.entries.slice(0, 3))
    expect(merged.rejected.map((line) => line.source)).toEqual(['a.jsonl', 'b.jsonl'])
  })

  it('lists a line rejected again in a later part once, at its first source', () => {
    const replica: ParsedLedger = { entries: [], rejected: [rejectedLine('actor1/case-actor.jsonl', 4, '{"bad": 1}')] }
    const canonical: ParsedLedger = { entries: [], rejected: [rejectedLine('case-actor/case-actor.jsonl', 4, '{"bad": 1}')] }
    const merged = mergeLedgers([replica, canonical, replica])
    expect(merged.rejected.map((line) => line.source)).toEqual(['actor1/case-actor.jsonl'])
  })

  it('starts from nothing, which is also what Start Over returns to', () => {
    expect(EMPTY_LEDGER).toEqual({ entries: [], rejected: [] })
    expect(mergeLedgers([EMPTY_LEDGER, rv])).toEqual(rv)
  })
})

describe('ledgerLoadError', () => {
  it('lets a load with a well-formed line through, rejected lines and all', () => {
    expect(ledgerLoadError('rv', { ...rv, rejected: [rejectedLine('rv', 9)] })).toBeNull()
  })

  it('refuses an empty load', () => {
    expect(ledgerLoadError('rv', EMPTY_LEDGER)).toBe('rv was empty — try file upload instead.')
  })

  it('refuses a load whose every line is rejected, naming the first', () => {
    const parsed = parseCaseLedger('{not json\n{"type": "CaseLedgerEntry"}', 'bad.jsonl')
    const message = ledgerLoadError('bad.jsonl', parsed)
    expect(message).toMatch(/^bad\.jsonl has no well-formed ledger lines: 2 rejected, first at bad\.jsonl line 1: not JSON: /)
  })
})

describe('laneVfdState', () => {
  const state = buildTimelineFromCaseLedger(normalizeLedger(rv.entries))
  const snapshots = state.stepSnapshots ?? []
  const last = snapshots[snapshots.length - 1]
  // The lanes are keyed on actor ids (utils/replayLanes.ts).
  const VENDOR = 'http://actor1:7999/api/v2/actors/actor1'
  const REPORTER = 'http://actor0:7999/api/v2/actors/actor0'
  const CASE_MANAGER = 'http://case-actor:7999/api/v2/actors/case-actor'

  it('shows a Vendor its VFD state at the current step', () => {
    expect(laneVfdState(state, VENDOR, last)).toBe('VFd')
  })

  it('reads a lane not yet seeded at this step as the initial state', () => {
    expect(laneVfdState(state, VENDOR, { rm: {}, vfd: {}, emState: 'NONE', pxaState: 'pxa' })).toBe('vfd')
  })

  it('gives no VFD row to a lane the ledger never gives a VFD state', () => {
    expect(laneVfdState(state, REPORTER, last)).toBeUndefined()
  })

  it('gives no VFD row to the CASE_MANAGER, even with a VFD token at the step', () => {
    // The mapper never records one for the CASE_MANAGER; the 'N/A' rule must
    // hold on its own if a step ever does.
    const withToken = { ...last, vfd: { ...last.vfd, [CASE_MANAGER]: 'vfd' } }
    const seeded = { ...state, stepSnapshots: [...snapshots, withToken] }
    expect(laneVfdState(seeded, CASE_MANAGER, withToken)).toBeUndefined()
  })
})
