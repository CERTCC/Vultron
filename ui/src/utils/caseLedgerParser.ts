/**
 * Parser for the Vultron **case-ledger** JSONL format (the refactored log format).
 *
 * This is the current log-replay pipeline. It replaced an older pipeline
 * (`jsonlParser.ts` + `logEventMapper.ts`) that parsed the pre-refactor format;
 * those files have been deleted (git history preserves them). See ui/AGENTS.md
 * §5–6 for the format history.
 *
 * The ledger is a single shared, hash-chained log: each container-based demo run
 * writes one replica per actor (devlogs/rv/{reporter,vendor,case-actor}/). The
 * replicas share entries and entry hashes but differ in `receivedAt`, and a
 * replica may lag the case-actor copy by its last entries — one authoritative
 * ledger, not several perspectives. `normalizeLedger` dedups by `entryHash` so
 * uploading every folder is safe.
 *
 * Each line is a `CaseLedgerEntry` carrying an explicit `semanticType` verb plus an
 * ActivityStreams 2.0 `payloadSnapshot`. Its fields, and those of the statuses in
 * the snapshot, are not declared here: they come from `../data/ledgerTypes.ts`,
 * generated from the Python models (`uv run export-demo-ledger-types`), and every
 * line is checked against those definitions on load (`./ledgerShape`). The mapper
 * (`caseLedgerMapper.ts`) reads the entries and validates them against the
 * protocol source of truth (`../protocol`).
 */

import {
  D_STATE_VALUES,
  type CaseLedgerEntry as CaseLedgerEntryRecord,
  type CaseParticipant,
  type CaseStatus,
  type ParticipantStatus,
} from '../data/ledgerTypes'
import { ledgerLineProblems } from './ledgerShape'

/**
 * A ledger entry's semantic type: the semantic registry's label for its payload.
 *
 * The set of types is not declared here. `../semanticRegistry` reads it from the
 * generated `src/data/semantic_registry.json` (exported from Python's
 * `SEMANTIC_REGISTRY` by `uv run export-demo-semantics`), so a type the protocol
 * adds or retires reaches the UI without a hand edit. The mapper's `handleEntry`
 * switch draws the types it depicts; every other registered type is logged in the
 * registry's phrasing.
 *
 * A few retired types are still handled so older uploaded logs replay:
 * `offer_case_manager_role` (now `create_case`), `submit_report` as a ledger verb
 * (now `add_report_to_case`), `create_note` (now `add_note_to_case`),
 * `add_case_participant` (now `create_case_participant`) and
 * `accept_case_manager_role`.
 */
export type LedgerSemanticType = string

/**
 * A case-level status (`CaseStatus`): the global EM/PXA pair.
 *
 * Partial: a payload object is read before its `type` is known, so every field
 * may be absent. An object that does carry `type: 'CaseStatus'` has been checked
 * against the generated definition by `parseCaseLedger`.
 *
 * Its `name` (like "ACTIVE Pxa") is UNRELIABLE for EM — at logIndex 0 the offer's
 * CaseStatus name reads "NONE pxa" while its structured `emState` is "ACTIVE".
 * Always prefer the structured `emState`/`pxaState` fields over the name.
 */
export type CaseStatusSnapshot = Partial<CaseStatus>

/**
 * A per-participant status (`ParticipantStatus`): RM, plus `vfState` for a
 * VENDOR and `dState` for a DEPLOYER (ADR-0075). Partial, as `CaseStatusSnapshot`.
 * Its `name` is a label like "ACCEPTED VF ACTIVE Pxa".
 */
export type ParticipantStatusSnapshot = Partial<ParticipantStatus>

/**
 * A participant record (`CaseParticipant`): its actor (`attributedTo`), the CVD
 * roles it plays (`caseRoles`, which label its replay lane, `./replayLanes`) and
 * its statuses. Partial, as `CaseStatusSnapshot`.
 */
export type CaseParticipantSnapshot = Partial<CaseParticipant>

/**
 * The combined VFD ladder token (`vfd`, `Vfd`, `VFd`, `VFD`) of a status, the
 * token the `vfd` machine of `src/data/protocol_states.json` names.
 *
 * The ladder is the export's projection of the `vf` and `d` sub-machines, so
 * the token is `vfState` then `dState`, with `d` when the participant has no D
 * dimension (it is not a DEPLOYER, so it deploys nothing). A status with no
 * `vfState` is not a VENDOR's and has no VFD token: `undefined`.
 */
export function vfdLadderToken(
  status: Pick<ParticipantStatusSnapshot, 'vfState' | 'dState'> | undefined
): string | undefined {
  if (!status?.vfState) return undefined
  return `${status.vfState}${status.dState ?? D_STATE_VALUES[0]}`
}

/**
 * The subset of an AS2 object the mapper reads. Covers ParticipantStatus,
 * CaseStatus, CaseParticipant, VulnerabilityCase (offer/close), Note, Offer, and
 * EmbargoEvent shapes. The status fields are the generated ones; the rest belong to models
 * the UI does not export.
 */
export interface As2Object
  extends Omit<ParticipantStatusSnapshot, 'type' | 'id' | 'name' | 'content' | 'inReplyTo' | 'attributedTo'>,
    Pick<CaseStatusSnapshot, 'emState' | 'pxaState'>,
    Pick<CaseParticipantSnapshot, 'caseRoles'> {
  id?: string
  type?: string
  name?: string | null
  content?: string | null
  inReplyTo?: string | null
  attributedTo?: string | null

  // VulnerabilityCase fields (offer / close entries):
  caseStatuses?: CaseStatusSnapshot[]
  /** Maps actor URL → participant URN; the case roster lives in its keys. */
  actorParticipantIndex?: Record<string, string>
  /** The case's participant records, inline or by id. */
  caseParticipants?: Array<CaseParticipantSnapshot | string>
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

/**
 * One line of the case ledger: the generated `CaseLedgerEntry`, with its
 * `payloadSnapshot` read as an AS2 activity. The snapshot is the body as
 * received (CLP-02-003), which no single exported model describes.
 */
export type CaseLedgerEntry = Omit<CaseLedgerEntryRecord, 'payloadSnapshot' | 'semanticType'> & {
  semanticType: LedgerSemanticType
  payloadSnapshot: As2Activity
}

/** A ledger line `parseCaseLedger` set aside, and why. */
export interface RejectedLedgerLine {
  /** Where the line came from: a file name, or a recording's label. */
  source: string
  /** 1-based line number within `source`. */
  lineNumber: number
  /** Every problem found, as `path: problem` (see `ledgerLineProblems`). */
  problems: string[]
  /** The line as read, trimmed. */
  text: string
}

/** What `parseCaseLedger` read: the well-formed entries and the rejected lines. */
export interface ParsedLedger {
  entries: CaseLedgerEntry[]
  rejected: RejectedLedgerLine[]
}

/**
 * Parse case-ledger JSONL content. Each non-empty line is checked against the
 * generated `CaseLedgerEntry` definition (`ledgerLineProblems`). A line that is
 * not JSON, or whose shape is wrong, is not replayed: replaying a line of the
 * wrong shape would draw a timeline from fields that are not there. It is
 * returned in `rejected` with every problem found, and the replay view shows
 * each one; a rejected line is never dropped without a trace.
 */
export function parseCaseLedger(content: string, source = 'ledger'): ParsedLedger {
  const entries: CaseLedgerEntry[] = []
  const rejected: RejectedLedgerLine[] = []
  content.split('\n').forEach((line, index) => {
    const text = line.trim()
    if (!text) return
    let value: unknown
    try {
      value = JSON.parse(text)
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      rejected.push({ source, lineNumber: index + 1, problems: [`not JSON: ${reason}`], text })
      return
    }
    const problems = ledgerLineProblems(value)
    if (problems.length > 0) {
      rejected.push({ source, lineNumber: index + 1, problems, text })
      return
    }
    entries.push(value as CaseLedgerEntry)
  })
  return { entries, rejected }
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
