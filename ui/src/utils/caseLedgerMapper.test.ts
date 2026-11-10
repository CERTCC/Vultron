/**
 * Unit tests of the Log Replay mapper's lanes over a committed recording.
 *
 * `rv` is the smallest registered scenario: a Reporter, one Vendor and the
 * CASE_MANAGER. The recording is loaded with a `?raw` import, as
 * `App-logreplay.tsx` loads it, so a regenerated recording needs no edit here.
 */

import { describe, expect, it } from 'vitest'

import rvLedgerRaw from '../recordings/rv/case-actor.jsonl?raw'
import { PARTICIPANT_ROLES } from '../constants'
import { buildTimelineFromCaseLedger } from './caseLedgerMapper'
import { normalizeLedger, parseCaseLedger } from './caseLedgerParser'

const entries = normalizeLedger(parseCaseLedger(rvLedgerRaw))
const state = buildTimelineFromCaseLedger(entries)

describe('buildTimelineFromCaseLedger on the rv recording', () => {
  it('reads a non-empty recording', () => {
    expect(entries.length).toBeGreaterThan(0)
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
