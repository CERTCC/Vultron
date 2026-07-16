/**
 * Parser for the Vultron **case-ledger** JSONL format (the refactored log format).
 *
 * This is the current log-replay pipeline. It replaced an older pipeline
 * (`jsonlParser.ts` + `logEventMapper.ts`) that parsed the pre-refactor format;
 * those files have been deleted (git history preserves them). See ui/CLAUDE.md
 * §5–6 for the format history.
 *
 * The ledger is a single shared, hash-chained log: each container-based demo run
 * writes per-folder copies (devlogs/two-actor/{finder,vendor,case-actor}/), but in
 * the current sample all three are byte-identical — one authoritative ledger, not
 * three perspectives. `normalizeLedger` dedups by `entryHash` so uploading all
 * three folders is safe.
 *
 * Each line is a `CaseLedgerEntry` carrying an explicit `eventType` verb plus an
 * ActivityStreams 2.0 `payloadSnapshot`. The mapper (`caseLedgerMapper.ts`) reads
 * these and validates them against the protocol source of truth (`../protocol`).
 */

/** The six event verbs the current ledger emits. */
export type LedgerEventType =
  | 'offer_case_manager_role'
  | 'validate_report'
  | 'add_note_to_case'
  | 'add_participant_status_to_participant'
  | 'remove_embargo_event_from_case'
  | 'close_case'

/** A case-level status snapshot (`CaseStatus`): the global EM/PXA pair. */
export interface CaseStatusSnapshot {
  emState?: string
  pxaState?: string
  /**
   * Human label like "ACTIVE Pxa". UNRELIABLE for EM — at logIndex 0 the offer's
   * CaseStatus name reads "NONE pxa" while its structured `emState` is "ACTIVE".
   * Always prefer the structured `emState`/`pxaState` fields over this string.
   */
  name?: string
}

/** A per-participant status snapshot (`ParticipantStatus`): RM + VFD + consent. */
export interface ParticipantStatusSnapshot {
  rmState?: string
  vfdState?: string
  emConsentState?: string
  attributedTo?: string | null
  /** Label like "ACCEPTED VFD ACTIVE Pxa" (RM VFD [EM] [PXA] tokens, in that order). */
  name?: string
}

/**
 * The subset of an AS2 object the mapper reads. Covers ParticipantStatus,
 * VulnerabilityCase (offer/close), Note, Offer, and EmbargoEvent shapes.
 */
export interface As2Object {
  id?: string
  type?: string
  name?: string
  content?: string
  inReplyTo?: string | null
  attributedTo?: string | null

  // ParticipantStatus fields (first-class — authoritative over `name`):
  rmState?: string
  vfdState?: string
  emConsentState?: string
  /** Case-level snapshot embedded on some participant-status entries. */
  caseStatus?: CaseStatusSnapshot | null

  // VulnerabilityCase fields (offer / close entries):
  caseStatuses?: CaseStatusSnapshot[]
  /** Maps actor URL → participant URN; the case roster lives in its keys. */
  actorParticipantIndex?: Record<string, string>
  caseParticipants?: string[]
  /** Nested per-participant statuses on the offer's target CaseParticipant. */
  participantStatuses?: ParticipantStatusSnapshot[]
}

/** An AS2 activity (the `payloadSnapshot`). */
export interface As2Activity {
  id?: string
  type?: string
  actor?: string
  object?: As2Object
  target?: As2Object
  context?: string
}

/** One line of the case ledger. */
export interface CaseLedgerEntry {
  id: string
  type: 'CaseLedgerEntry'
  published: string
  updated: string
  caseId: string
  logIndex: number
  disposition: string
  logObjectId: string
  eventType: LedgerEventType
  payloadSnapshot: As2Activity
  prevLogHash: string
  entryHash: string
  receivedAt: string
}

/** A demo lane id. `unknown` is returned for unrecognized actor URLs. */
export type LaneId = 'finder' | 'vendor-1' | 'caseactor' | 'unknown'

/**
 * Map an actor URL to a demo lane id.
 *
 * Order matters: the Case Actor's URL is itself a `//vendor:` URL with a
 * `case-actor-…` path segment (e.g.
 * `http://vendor:7999/api/v2/actors/case-actor-<caseId>`), so the `case-actor`
 * test MUST run before the `//vendor:` test.
 */
export function actorUrlToLaneId(url?: string | null): LaneId {
  if (!url) return 'unknown'
  if (url.includes('case-actor')) return 'caseactor'
  if (url.includes('//vendor:')) return 'vendor-1'
  if (url.includes('//finder:')) return 'finder'
  return 'unknown'
}

/**
 * Parse case-ledger JSONL content into entries. One entry per non-empty line;
 * unparseable lines are warned and skipped (a corrupt line shouldn't sink the run).
 */
export function parseCaseLedger(content: string): CaseLedgerEntry[] {
  const entries: CaseLedgerEntry[] = []
  for (const line of content.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    try {
      entries.push(JSON.parse(trimmed) as CaseLedgerEntry)
    } catch (error) {
      console.warn('Skipping unparseable case-ledger line:', error, trimmed)
    }
  }
  return entries
}

/**
 * Canonicalize entries gathered from one or more files:
 *   1. dedup by `entryHash` (the per-folder copies are byte-identical), and
 *   2. sort ascending by `logIndex` — the authoritative order. Do NOT sort by
 *      `receivedAt`: entries 2/3, 7/8, 9/10 in the sample share a wall-clock
 *      second and a receivedAt-sort would scramble their order.
 *
 * Warns (does not throw) if the resulting `logIndex` sequence is non-contiguous —
 * that signals a truncated / perspective-subset ledger, which the mapper still
 * handles via mid-stream seeding.
 */
export function normalizeLedger(entries: CaseLedgerEntry[]): CaseLedgerEntry[] {
  const byHash = new Map<string, CaseLedgerEntry>()
  for (const entry of entries) {
    // Fall back to logObjectId+logIndex if an entry somehow lacks a hash.
    const key = entry.entryHash || `${entry.logObjectId}:${entry.logIndex}`
    if (!byHash.has(key)) byHash.set(key, entry)
  }

  const ordered = Array.from(byHash.values()).sort((a, b) => a.logIndex - b.logIndex)

  for (let i = 1; i < ordered.length; i++) {
    if (ordered[i].logIndex !== ordered[i - 1].logIndex + 1) {
      console.warn(
        `Case ledger has a non-contiguous logIndex gap between ${ordered[i - 1].logIndex} ` +
          `and ${ordered[i].logIndex} — treating as a truncated/subset ledger (mid-stream seeding applies).`
      )
      break
    }
  }

  return ordered
}
