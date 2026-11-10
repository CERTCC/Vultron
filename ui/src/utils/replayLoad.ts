/**
 * The Log Replay view's load and panel rules, kept out of `App-logreplay.tsx`
 * so they can be unit-tested (the view itself has no component tests).
 */

import { initialState } from '../protocol'
import type { DemoState, StepSnapshot } from '../types'
import type { ParsedLedger } from './caseLedgerParser'

/** What the view holds before anything is loaded, and after Start Over. */
export const EMPTY_LEDGER: ParsedLedger = { entries: [], rejected: [] }

/**
 * Join parsed ledgers in order: the entries of all, and every rejected line of
 * all, so a later upload never hides an earlier upload's rejected lines.
 *
 * A rejected line whose text an earlier part already rejected is listed once,
 * at its first source: uploading every replica's folder, or the same file
 * again, repeats each line, as `normalizeLedger` dedups the entries by hash.
 */
export function mergeLedgers(parts: readonly ParsedLedger[]): ParsedLedger {
  const seen = new Set<string>()
  const rejected = parts
    .flatMap((part) => part.rejected)
    .filter((line) => {
      if (seen.has(line.text)) return false
      seen.add(line.text)
      return true
    })
  return { entries: parts.flatMap((part) => part.entries), rejected }
}

/**
 * Why a load cannot be replayed, or null when it can. A load with no
 * well-formed line is refused, naming its first rejected line, so a file of
 * malformed lines never shows as an empty timeline.
 */
export function ledgerLoadError(label: string, parsed: ParsedLedger): string | null {
  if (parsed.entries.length > 0) return null
  const [first] = parsed.rejected
  if (first === undefined) return `${label} was empty — try file upload instead.`
  return (
    `${label} has no well-formed ledger lines: ${parsed.rejected.length} rejected, ` +
    `first at ${first.source} line ${first.lineNumber}: ${first.problems[0]}`
  )
}

/**
 * The VFD state a lane's panel shows at `current`, or undefined for no VFD row.
 *
 * A lane has a VFD row only if the ledger gives it a VFD state at some step:
 * statuses carry `vfState` for a VENDOR alone (ADR-0075), so a Reporter's or
 * Coordinator's lane has none, and the CASE_MANAGER ('N/A') has none. Before its
 * first VFD step a lane reads as the machine's initial state, as RM does.
 */
export function laneVfdState(
  demoState: DemoState,
  laneId: string,
  current: StepSnapshot | undefined
): string | undefined {
  if (demoState.participants.get(laneId)?.vfd === 'N/A') return undefined
  const snapshots = demoState.stepSnapshots ?? []
  if (!snapshots.some((snapshot) => snapshot.vfd[laneId] !== undefined)) return undefined
  return current?.vfd[laneId] ?? initialState('vfd')
}
