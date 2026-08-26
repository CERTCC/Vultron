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

/**
 * The event verbs the ledger emits.
 *
 * **2026-08 vocabulary shift.** A merge from `main` changed the case-LIFECYCLE
 * verbs while leaving the per-participant / note / embargo / invite verbs intact
 * (see ui/CLAUDE.md §5–6). The mapping from the OLD vocabulary the earlier
 * fixtures used:
 *   - `offer_case_manager_role` → **`create_case`** — case bootstrap; same
 *     `actorParticipantIndex` roster + `caseStatuses[0]` EM/PXA, `actor` = the
 *     case-actor recorder. (`offer_case_manager_role` is no longer emitted.)
 *   - `submit_report` → **`add_report_to_case`** — the finder's report; `actor`
 *     is now the recorder/owner and the finder is `object.attributedTo`
 *     (`object.type = VulnerabilityReport`).
 *   - case-level EM/PXA (previously only embedded on participant statuses / the
 *     offer) now also arrives as first-class **`add_case_status_to_case`**
 *     (`emState`/`pxaState` directly on `object`, a `CaseStatus`).
 *   - **`case_fully_closed`** — the derived "all participants closed" marker
 *     (no `object`); the per-participant `close_case` nodes still show closure.
 *   - **`engage_case`** — the owner formally engages the case (no machine change;
 *     EM/PXA already seeded at create).
 *   - **`add_case_participant`** — roster bookkeeping (`object.type =
 *     CaseParticipant`); the actual join still renders via `accept_invite…`.
 *   - **`reject_invite_actor_to_case`** — an invitee declines (fcv-reject);
 *     `actor` = the rejecter, `object.object` = the invitee.
 *   - **`accept_actor_recommendation`** — a leg of the ADR-0026 suggest-actor
 *     handshake (fcvcv), folded into the "Actor Recommended" overlay.
 *
 * The ADR-0026 suggest-actor verbs (`offer_actor_to_case` /
 * `offer_case_participant` / `accept_offer_case_participant`) and
 * `accept_case_manager_role` are still emitted by some scenarios; their handlers
 * are retained. `offer_case_manager_role` / `submit_report` are kept in the union
 * for backward-compatible replay of older uploaded logs, but current fixtures no
 * longer contain them.
 */
export type LedgerEventType =
  | 'offer_case_manager_role'
  | 'create_case'
  | 'validate_report'
  | 'add_note_to_case'
  | 'add_participant_status_to_participant'
  | 'add_case_status_to_case'
  | 'remove_embargo_event_from_case'
  | 'close_case'
  | 'case_fully_closed'
  | 'engage_case'
  | 'invite_actor_to_case'
  | 'accept_invite_actor_to_case'
  | 'reject_invite_actor_to_case'
  | 'add_case_participant'
  | 'submit_report'
  | 'add_report_to_case'
  | 'accept_case_manager_role'
  | 'offer_actor_to_case'
  | 'offer_case_participant'
  | 'accept_offer_case_participant'
  | 'accept_actor_recommendation'

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

  // CaseStatus fields — when the object IS a CaseStatus (add_case_status_to_case),
  // the case-level EM/PXA sit directly on the object rather than under caseStatus.
  emState?: string
  pxaState?: string

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

/**
 * A demo lane id. `unknown` is returned for unrecognized actor URLs. Vendors are
 * `vendor-1`, `vendor-2`, … — the demo supports N vendors (a `vendor-${n}`
 * template literal type keeps the union open while still excluding arbitrary
 * strings from the caller's perspective).
 */
export type LaneId = 'finder' | `vendor-${number}` | 'coordinator' | 'caseactor' | 'unknown'

/**
 * Map an actor URL to a demo lane id.
 *
 * The container demo gives each actor service a distinct hostname: `finder:`,
 * `vendor:` (the first/primary vendor), `vendor2:`, `vendor3:`, `coordinator:`
 * (a dedicated coordinator container, 2026-07 scenarios), `actor5:` (the second
 * vendor in the coordinator scenarios — seeded as "vendor2", so it reuses the
 * vendor-N machinery as `vendor-2`), … and the Case Actor runs as a sub-actor
 * with a `case-actor-…` path segment on whichever host owns the case
 * (`//vendor:…/case-actor-<caseId>` in two-actor/fvv/fvcv-*; `//coordinator:…/
 * case-actor-<caseId>` in fcv/fccv-*).
 *
 * Order matters: the `case-actor` test MUST run FIRST — the recorder sub-actor's
 * URL is itself a `//vendor:` or `//coordinator:` URL, and it must resolve to the
 * caseactor lane, not to the host's participant lane. Lane identity is keyed on
 * the HOST, never on the participant's CVD role: a participant's role
 * (VENDOR / CASE_OWNER / COORDINATOR) is carried per-status in `cvdRole` and — in
 * the handoff scenarios — can migrate between participants, so it can't define a
 * stable lane. The `coordinator:` host is therefore its own lane distinct from the
 * caseactor recorder, even when the recorder is co-hosted with it.
 */
export function actorUrlToLaneId(url?: string | null): LaneId {
  if (!url) return 'unknown'
  if (url.includes('case-actor')) return 'caseactor'
  if (url.includes('//finder:')) return 'finder'
  if (url.includes('//coordinator:')) return 'coordinator'
  // `actor5:` hosts Vendor2 in the coordinator scenarios → reuse the vendor-2 lane.
  if (url.includes('//actor5:')) return 'vendor-2'
  // `actor6:` hosts the VendorDeployer (V2/"vendor-deployer") in the fcvcv
  // scenario → reuse the vendor-3 lane (same rationale as actor5→vendor-2: lane
  // identity is keyed on the host, and this host runs the vendor fix lifecycle).
  if (url.includes('//actor6:')) return 'vendor-3'
  // `//vendorN:` (N ≥ 2) → vendor-N; the bare `//vendor:` host → vendor-1.
  const numberedVendor = url.match(/\/\/vendor(\d+):/)
  if (numberedVendor) return `vendor-${parseInt(numberedVendor[1], 10)}`
  if (url.includes('//vendor:')) return 'vendor-1'
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
