/**
 * Unit tests of `protocol.ts` against the committed protocol-state artifact.
 *
 * The expectations are derived from `data/protocol_states.json` itself, not
 * restated by hand: every transition the artifact lists must be legal, and every
 * (state, trigger) pair it does not list must be illegal. So these tests follow
 * a regenerated artifact (`uv run export-demo-states`) without an edit, and fail
 * only if `protocol.ts` misreads it.
 */

import { describe, expect, it } from 'vitest'

import protocolStates from './data/protocol_states.json'
import {
  initialState,
  isLegalTransition,
  legalTriggers,
  machineStates,
  nextStates,
  requireNextState,
  type MachineName,
  type RawMachine,
} from './protocol'

const MACHINE_NAMES: readonly MachineName[] = ['rm', 'em', 'vfd', 'pxa']

const artifact = protocolStates as unknown as Record<MachineName, RawMachine>

/** Every dest the artifact lists for (source, trigger), in artifact order. */
function artifactDests(machine: MachineName, source: string, trigger: string): string[] {
  return artifact[machine].transitions
    .filter((t) => t.source === source && t.trigger === trigger)
    .map((t) => t.dest)
}

/** Every trigger the machine uses anywhere, deduped. */
function allTriggers(machine: MachineName): string[] {
  return [...new Set(artifact[machine].transitions.map((t) => t.trigger))]
}

/** Every (source, trigger) pair the artifact does NOT list for the machine. */
function illegalPairs(machine: MachineName): Array<[string, string]> {
  const pairs: Array<[string, string]> = []
  for (const source of artifact[machine].states) {
    for (const trigger of allTriggers(machine)) {
      if (artifactDests(machine, source, trigger).length === 0) pairs.push([source, trigger])
    }
  }
  return pairs
}

describe('the artifact under test', () => {
  // Guards the tests below against passing vacuously on an empty artifact.
  it.each(MACHINE_NAMES)('%s declares states and transitions', (machine) => {
    expect(artifact[machine].states.length).toBeGreaterThan(0)
    expect(artifact[machine].transitions.length).toBeGreaterThan(0)
    expect(illegalPairs(machine).length).toBeGreaterThan(0)
  })
})

describe.each(MACHINE_NAMES)('%s machine', (machine) => {
  it('reads the initial state and the state list from the artifact', () => {
    expect(initialState(machine)).toBe(artifact[machine].initial)
    expect(machineStates(machine)).toEqual(artifact[machine].states)
  })

  describe('isLegalTransition', () => {
    it.each(artifact[machine].transitions.map((t) => [t.source, t.trigger] as const))(
      'allows the listed transition %s --%s-->',
      (source, trigger) => {
        expect(isLegalTransition(machine, source, trigger)).toBe(true)
      },
    )

    it.each(illegalPairs(machine))('refuses the unlisted pair %s --%s-->', (source, trigger) => {
      expect(isLegalTransition(machine, source, trigger)).toBe(false)
    })

    it('refuses a state or trigger the machine does not declare', () => {
      const [first] = artifact[machine].transitions
      expect(isLegalTransition(machine, 'NO_SUCH_STATE', first.trigger)).toBe(false)
      expect(isLegalTransition(machine, first.source, 'no_such_trigger')).toBe(false)
    })
  })

  describe('requireNextState', () => {
    it.each(artifact[machine].transitions.map((t) => [t.source, t.trigger] as const))(
      'returns a listed dest for %s --%s-->',
      (source, trigger) => {
        expect(artifactDests(machine, source, trigger)).toContain(
          requireNextState(machine, source, trigger),
        )
      },
    )

    it.each(illegalPairs(machine))('throws on the unlisted pair %s --%s-->', (source, trigger) => {
      expect(() => requireNextState(machine, source, trigger)).toThrow(
        `Illegal ${machine} transition: no "${trigger}" from "${source}"`,
      )
    })
  })

  it('lists every dest of each pair in nextStates, and every legal trigger', () => {
    for (const source of artifact[machine].states) {
      const listed = allTriggers(machine).filter(
        (trigger) => artifactDests(machine, source, trigger).length > 0,
      )
      expect([...legalTriggers(machine, source)].sort()).toEqual([...listed].sort())
      for (const trigger of listed) {
        expect(nextStates(machine, source, trigger)).toEqual([
          ...new Set(artifactDests(machine, source, trigger)),
        ])
      }
    }
  })
})

describe('requireNextState on a pair with several dests', () => {
  // EM's accept/reject from PROPOSED/REVISE may leave negotiation or stay in it
  // (ADR-0130). The Multi-Vendor overlay takes the dest outside PROPOSED/REVISE.
  const NEGOTIATING = new Set(['PROPOSED', 'REVISE'])
  const ambiguous = artifact.em.transitions
    .map((t) => [t.source, t.trigger] as const)
    .filter(([source, trigger]) => new Set(artifactDests('em', source, trigger)).size > 1)

  it('exists in the artifact', () => {
    expect(ambiguous.length).toBeGreaterThan(0)
  })

  it.each(ambiguous)('takes the dest that leaves negotiation for em %s --%s-->', (source, trigger) => {
    const dest = requireNextState('em', source, trigger)
    expect(NEGOTIATING.has(dest)).toBe(false)
    expect(artifactDests('em', source, trigger)).toContain(dest)
  })
})
