/**
 * Golden tests of Log Replay over every committed recording (#4729 AC-4).
 *
 * Each scenario in `../data/scenario_tree.json` names its recordings; each is
 * replayed through `buildTimelineFromCaseLedger`, and the replay is written as a
 * plain-text golden file, `replay-golden/<scenario>.txt`: its lanes, each
 * participant's state path and final state, and the event sequence, one step per
 * entry. A new scenario is covered with no edit here: its first local run writes
 * its golden file, which the PR commits. In CI a missing golden file fails.
 *
 * The golden files are for review: a change to the mapper, the registry phrases
 * or a recording shows up as a readable diff of the replay. To regenerate them
 * after an intended change, run `npm test -- -u` in `ui/` and read the diff
 * before committing it.
 *
 * Beside the golden files, the properties every recording must have are
 * asserted directly: no node is unrecognized, flagged or inferred, and each lane
 * is labelled by the roles its ledger records give it.
 */

import { describe, expect, it } from 'vitest'

import scenarioTree from '../data/scenario_tree.json'
import semanticRegistry from '../data/semantic_registry.json'
import type { DemoState, TimelineEvent } from '../types'
import { buildTimelineFromCaseLedger } from './caseLedgerMapper'
import { normalizeLedger, parseCaseLedger, type CaseLedgerEntry } from './caseLedgerParser'
import { buildLanes } from './replayLanes'
import { statePath } from './testing/ledgerEntries'

const RECORDINGS = import.meta.glob<string>('../recordings/*/case-actor.jsonl', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const GOLDEN_FILES = import.meta.glob<string>('./replay-golden/*.txt', {
  query: '?raw',
  import: 'default',
  eager: true,
})

interface Replay {
  scenario: string
  /** The golden file's name: the scenario, with the case id when it has several recordings. */
  golden: string
  path: string
  entries: CaseLedgerEntry[]
  state: DemoState
}

/** Every recording each scenario of the tree names, replayed. */
function replays(): Replay[] {
  const out: Replay[] = []
  for (const [scenario, info] of Object.entries(scenarioTree.scenarios)) {
    const caseActor: Record<string, string> = info.recordings['case-actor'] ?? {}
    const several = Object.keys(caseActor).length > 1
    for (const [caseId, path] of Object.entries(caseActor)) {
      const golden = several ? `${scenario}--${caseId.replace(/[^\w-]+/g, '_')}` : scenario
      const raw = RECORDINGS[`../${path}`]
      if (raw === undefined) throw new Error(`${scenario}: no committed recording at ui/src/${path}`)
      const parsed = parseCaseLedger(raw, path)
      if (parsed.rejected.length > 0) throw new Error(`${path}: ${parsed.rejected.length} rejected line(s)`)
      const entries = normalizeLedger(parsed.entries)
      out.push({ scenario, golden, path, entries, state: buildTimelineFromCaseLedger(entries) })
    }
  }
  return out
}

const REPLAYS = replays()

// ---------------------------------------------------------------------------
// The golden text
// ---------------------------------------------------------------------------

/** Lanes top to bottom, with the hidden ones (never joined) marked. */
function lanesOf(state: DemoState) {
  return [...state.participants.values()].sort((a, b) => a.laneIndex - b.laneIndex)
}

const pad = (text: string, width: number) => text.padEnd(width)

function casePath(state: DemoState, machine: 'emState' | 'pxaState'): string[] {
  const path: string[] = []
  for (const snapshot of state.stepSnapshots ?? []) {
    if (path[path.length - 1] !== snapshot[machine]) path.push(snapshot[machine])
  }
  return path
}

function flags(event: TimelineEvent): string {
  const set = [
    event.violation ? 'violation' : '',
    event.inferred ? 'inferred' : '',
    event.unrecognized ? 'unrecognized' : '',
  ].filter(Boolean)
  return set.length > 0 ? `  [${set.join(', ')}]` : ''
}

/** The replay as reviewable text. */
function goldenText(replay: Replay): string {
  const { state } = replay
  const lanes = lanesOf(state)
  const nameById = new Map(lanes.map((p) => [p.id, p.name]))
  const width = Math.max(4, ...lanes.map((p) => p.name.length)) + 2
  const lines: string[] = [
    `# Log Replay golden: ${replay.scenario} (ui/src/${replay.path})`,
    '# Written by ui/src/utils/replayGolden.test.ts. After an intended change,',
    '# regenerate with `npm test -- -u` in ui/ and review the diff.',
    '',
    '## Lanes, top to bottom: label, roles, actor id',
  ]
  for (const p of lanes) {
    const hidden = p.visible ? '' : '  (never joins)'
    lines.push(`${pad(p.name, width)}${pad(p.role || '—', 22)}${p.id}${hidden}`)
  }

  lines.push('', '## States: each lane\'s distinct states in step order, then the case')
  for (const p of lanes) {
    if (p.laneKind === 'casemanager') {
      lines.push(`${pad(p.name, width)}RM N/A, VFD N/A`)
      continue
    }
    const rm = statePath(state, 'rm', p.id)
    const vfd = statePath(state, 'vfd', p.id)
    const parts = [`RM ${rm.length > 0 ? rm.join(' → ') : '—'}`]
    if (vfd.length > 0) parts.push(`VFD ${vfd.join(' → ')}`)
    lines.push(`${pad(p.name, width)}${parts.join('; ')}`)
  }
  lines.push(`${pad('Case', width)}EM ${casePath(state, 'emState').join(' → ')}; PXA ${casePath(state, 'pxaState').join(' → ')}`)

  lines.push('', '## Events: step, decision lane, label [flags], then details and the lanes it reaches')
  const decisions = state.timelineEvents.filter((e) => e.type === 'decision')
  decisions.forEach((event, step) => {
    const reached = state.timelineEvents
      .filter((e) => e.causedBy === event.id)
      .map((e) => nameById.get(e.participantId ?? '') ?? e.actor)
    lines.push(`${String(step + 1).padStart(2, '0')}  ${pad(event.actor, width)}${event.label}${flags(event)}`)
    if (event.consequences.length > 0) lines.push(`      ${event.consequences.join(' · ')}`)
    if (reached.length > 0) lines.push(`      → ${reached.join(', ')}`)
  })
  return `${lines.join('\n')}\n`
}

/**
 * A node that depicts the act its entry follows, not the entry itself: an
 * `add_report_to_case` entry is drawn as the Reporter's submission.
 */
const DEPICTED: ReadonlyMap<string, string> = new Map([['add_report_to_case', 'submit_report']])

const PHRASES: ReadonlyMap<string, string> = new Map(
  semanticRegistry.entries.map((entry) => [entry.semanticType, entry.phrase])
)

/**
 * The registry phrase of `semanticType` as a pattern: its words verbatim, each
 * slot any text, the first letter capitalized (`renderPhrase`).
 */
function phrasePattern(semanticType: string): RegExp {
  const phrase = PHRASES.get(semanticType)
  if (phrase === undefined) throw new Error(`${semanticType} is not in the registry`)
  const escaped = phrase
    .split(/\{\w+\}/)
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('.+')
  return new RegExp(`^${escaped.charAt(0).toUpperCase()}${escaped.slice(1)}$`)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('the recordings the golden tests replay', () => {
  it('are every scenario of the tree, each read with no rejected line', () => {
    expect(REPLAYS.length).toBeGreaterThan(0)
    expect(new Set(REPLAYS.map((r) => r.scenario))).toEqual(new Set(Object.keys(scenarioTree.scenarios)))
  })

  it('cover every committed recording', () => {
    expect(new Set(REPLAYS.map((r) => `../${r.path}`))).toEqual(new Set(Object.keys(RECORDINGS)))
  })

  it('leave no golden file without a scenario', () => {
    const goldens = new Set(REPLAYS.map((r) => r.golden))
    const stale = Object.keys(GOLDEN_FILES)
      .map((file) => file.replace(/^\.\/replay-golden\/(.*)\.txt$/, '$1'))
      .filter((name) => !goldens.has(name))
    expect(stale).toEqual([])
  })
})

describe.each(REPLAYS.map((r) => [r.golden, r] as const))('the %s replay', (_golden, replay) => {
  it('matches its golden file', async () => {
    await expect(goldenText(replay)).toMatchFileSnapshot(`./replay-golden/${replay.golden}.txt`)
  })

  it('has no unrecognized, flagged or inferred node', () => {
    const marked = replay.state.timelineEvents.filter((e) => e.unrecognized || e.violation || e.inferred)
    expect(marked.map((e) => `${e.id}: ${e.label}`)).toEqual([])
  })

  it('labels every node with the registry phrase of its entry, or of the act it depicts', () => {
    for (const event of replay.state.timelineEvents) {
      const entry = replay.entries.find((e) => event.id.startsWith(`${e.id}-`))
      expect(entry, event.id).toBeDefined()
      const depicted = DEPICTED.get(entry!.semanticType) ?? entry!.semanticType
      expect(event.label, `${entry!.semanticType} at ${entry!.logIndex}`).toMatch(phrasePattern(depicted))
    }
  })

  it('keys each lane on an actor id the ledger names and labels it by its roles', () => {
    const lanes = buildLanes(replay.entries)
    for (const lane of lanes.lanes) {
      expect(lane.id).toMatch(/^https?:\/\//)
      // Spelled out here, not taken from replayLanes: a label is the role
      // names of its lane, then a number from the second lane of that name.
      const shown = lane.roles.includes('case_manager')
        ? ['case_manager']
        : lane.roles.filter((role) => role !== 'case_owner')
      const base = shown.map((role) => EXPECTED_ROLE_NAMES[role]).join(' / ')
      expect(lane.label).toMatch(new RegExp(`^${base}( [2-9])?$`))
      expect(replay.state.participants.get(lane.id)?.name).toBe(lane.label)
    }
    const labels = lanes.lanes.map((lane) => lane.label)
    expect(new Set(labels).size).toBe(labels.length)
  })

  it('puts every node in the lane of the participant it names', () => {
    for (const event of replay.state.timelineEvents) {
      const participant = replay.state.participants.get(event.participantId ?? '')
      expect(participant?.laneIndex).toBe(event.lane)
    }
  })
})

/** The lane labels of the actors whose records name `role`, in lane order. */
function labelsWithRole(replay: Replay, role: 'coordinator' | 'vendor'): string[] {
  return buildLanes(replay.entries)
    .lanes.filter((lane) => lane.roles.includes(role) && lane.kind !== 'casemanager')
    .map((lane) => lane.label)
}

const byScenario = (name: string): Replay => {
  const replay = REPLAYS.find((r) => r.scenario === name)
  if (!replay) throw new Error(`no ${name} recording`)
  return replay
}

describe('a second Coordinator (#5585)', () => {
  it.each(['rccv-extension', 'rccv-handoff', 'rcvcv'])('is labelled a Coordinator in %s', (name) => {
    const replay = byScenario(name)
    expect(labelsWithRole(replay, 'coordinator')).toEqual(['Coordinator', 'Coordinator 2'])
    // No lane is labelled a Vendor unless its records name the Vendor role.
    for (const lane of buildLanes(replay.entries).lanes) {
      if (lane.label.startsWith('Vendor')) expect(lane.roles).toContain('vendor')
    }
    const second = replay.state.participants.get(
      buildLanes(replay.entries).lanes.find((lane) => lane.label === 'Coordinator 2')!.id
    )
    expect(second?.role).toBe('COORDINATOR')
    expect(second?.visible).toBe(true)
  })
})

/** The role names a lane label uses, as a reader of the timeline would expect them. */
const EXPECTED_ROLE_NAMES: Record<string, string> = {
  reporter: 'Reporter',
  vendor: 'Vendor',
  deployer: 'Deployer',
  coordinator: 'Coordinator',
  case_manager: 'Case Manager',
}

describe('a case-ownership handoff', () => {
  it.each([
    ['rccv-handoff', 'Coordinator', 'Coordinator 2'],
    ['rvcv-handoff', 'Vendor', 'Coordinator'],
  ])('keeps the outgoing and incoming owners in their own lanes and labels in %s', (name, outgoing, incoming) => {
    const replay = byScenario(name)
    // The records that move CASE_OWNER: the first update drops it, the second adds it.
    const updates = replay.entries.filter((e) => e.semanticType === 'update_case_participant')
    const [from, to] = updates.map((e) => e.payloadSnapshot.object!.attributedTo!)
    expect(updates.map((e) => e.payloadSnapshot.object!.caseRoles)).toEqual([
      [outgoing.toLowerCase().split(' ')[0]],
      ['coordinator', 'case_owner'],
    ])
    const lanes = buildLanes(replay.entries)
    expect([lanes.get(from)?.label, lanes.get(to)?.label]).toEqual([outgoing, incoming])
    // Every node of each owner, before and after the handoff, is in one lane.
    for (const actor of [from, to]) {
      const indices = new Set(
        replay.state.timelineEvents.filter((e) => e.participantId === actor).map((e) => e.lane)
      )
      expect([...indices]).toEqual([lanes.get(actor)!.index])
    }
    const accept = replay.entries.find((e) => e.semanticType === 'accept_case_ownership_transfer')!
    expect(replay.state.timelineEvents.find((e) => e.id === `${accept.id}-decision`)?.participantId).toBe(to)
  })
})

describe('the rcvcv Vendor that also deploys', () => {
  it('is labelled by both roles and climbs the full VFD ladder', () => {
    const replay = byScenario('rcvcv')
    const lane = buildLanes(replay.entries).lanes.find((l) => l.roles.includes('deployer'))
    expect(lane?.label).toBe('Vendor / Deployer')
    expect(statePath(replay.state, 'vfd', lane!.id)).toEqual(['vfd', 'Vfd', 'VFd', 'VFD'])
  })
})
