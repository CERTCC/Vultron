/**
 * The Log Replay lanes: one per participant actor, identified by its actor id
 * and labelled by the CVD roles the ledger gives it.
 *
 * Identity and label come from different facts, because they change at
 * different rates. A lane is keyed on the actor id, which never changes. Its
 * label is the CVD role the actor plays, read from the ledger itself: the
 * `caseRoles` of the `CaseParticipant` records in the entries' payloads
 * (generated type, `../data/ledgerTypes.ts`). Neither is read from a container
 * hostname or a display name, since one container plays different parts in
 * different scenarios (`actor3` is a second Vendor in `rvv` and a second
 * Coordinator in `rccv-*`).
 *
 * A role can move between participants: in the handoff scenarios CASE_OWNER
 * passes from one actor to another. So identity is never keyed on a role, and
 * the label leaves CASE_OWNER out. The label is fixed for the whole replay: it
 * is the union of the roles every record of the actor names, CASE_OWNER aside.
 *
 * A ledger with no `CaseParticipant` record for an actor (an older uploaded
 * log), or whose records name no role but CASE_OWNER, falls back to the
 * `cvdRole` of the actor's `ParticipantStatus` records.
 * When no record or status names a CASE_MANAGER, the actor of the case's
 * bootstrap entry is it. Any other actor with no roles is labelled
 * "Participant": in such a log a Reporter is not recognized, so it gets no
 * RM=ACCEPTED seed at case creation.
 */

import { getVendorColor, PARTICIPANT_COLORS } from '../constants'
import { CASE_ROLES_VALUES, type CaseRoles, type CvdRole } from '../data/ledgerTypes'
import type { CaseLedgerEntry, CaseParticipantSnapshot, ParticipantStatusSnapshot } from './caseLedgerParser'

/** A CVD role as a `CaseParticipant` record writes it (`vendor`, `case_owner`). */
export type CaseRole = CaseRoles

/**
 * What a lane does in the replay, from its roles. The CASE_MANAGER records the
 * ledger and has no report-management state of its own; a Reporter enters the
 * case already at RM ACCEPTED; a Vendor develops a fix (VFD).
 */
export type LaneKind = 'reporter' | 'vendor' | 'coordinator' | 'casemanager' | 'participant'

/** One lane of the replay. */
export interface ReplayLane {
  /** The participant's actor id: the lane's identity. */
  readonly id: string
  /** Every role the ledger gives the actor, in `CASE_ROLES_VALUES` order. */
  readonly roles: readonly CaseRole[]
  readonly kind: LaneKind
  /** The display label, e.g. "Coordinator 2". */
  readonly label: string
  /** The roles behind the label as CVD role names, e.g. "VENDOR, DEPLOYER". */
  readonly roleLabel: string
  /** The `nodeColorsFor` palette key: `reporter`, `vendor-N`, `coordinator`, … */
  readonly palette: string
  /** The lane's background color. */
  readonly color: string
  /** Top-to-bottom position. */
  readonly index: number
}

/** The lanes of one ledger, in lane order, with a lookup by actor id. */
export interface LaneDirectory {
  readonly lanes: readonly ReplayLane[]
  get(actorId: string | null | undefined): ReplayLane | undefined
}

/** The display name of each role. A role the exporter adds fails the type check here. */
const ROLE_NAMES: Record<CaseRole, string> = {
  reporter: 'Reporter',
  vendor: 'Vendor',
  deployer: 'Deployer',
  coordinator: 'Coordinator',
  observer: 'Observer',
  case_owner: 'Case Owner',
  case_manager: 'Case Manager',
  cve_numbering_authority: 'CNA',
}

/** The roles a label never shows: CASE_OWNER moves between participants. */
const MOVING_ROLES: ReadonlySet<CaseRole> = new Set(['case_owner'])

/** The case's bootstrap entry: the current verb and the pre-2026-08 one. */
const BOOTSTRAP_TYPES: ReadonlySet<string> = new Set(['create_case', 'offer_case_manager_role'])

/** Lane order, top to bottom, by kind. */
const KIND_ORDER: readonly LaneKind[] = ['reporter', 'vendor', 'coordinator', 'participant', 'casemanager']

const ROLE_SET: ReadonlySet<string> = new Set(CASE_ROLES_VALUES)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isCaseRole(value: unknown): value is CaseRole {
  return typeof value === 'string' && ROLE_SET.has(value)
}

/**
 * Every object under `value` (itself included) whose `type` is `type`, parents
 * first. `parseCaseLedger` has checked each such object against its generated
 * definition, so it is read as that model's snapshot type.
 */
function* objectsOfType<T>(value: unknown, type: string): Generator<T> {
  if (Array.isArray(value)) {
    for (const item of value) yield* objectsOfType<T>(item, type)
    return
  }
  if (!isRecord(value)) return
  if (value.type === type) yield value as T
  for (const child of Object.values(value)) yield* objectsOfType<T>(child, type)
}

/** A status's `cvdRole` names (`CASE_MANAGER`) as the roles a record writes (`case_manager`). */
function statusRoles(names: readonly CvdRole[] | undefined): CaseRole[] {
  return (names ?? []).map((name) => name.toLowerCase()).filter(isCaseRole)
}

/** The kind of a lane with `roles`. */
export function laneKind(roles: readonly CaseRole[]): LaneKind {
  if (roles.includes('case_manager')) return 'casemanager'
  if (roles.includes('reporter')) return 'reporter'
  if (roles.includes('vendor')) return 'vendor'
  if (roles.includes('coordinator')) return 'coordinator'
  return 'participant'
}

/** The roles a lane's label names, in `CASE_ROLES_VALUES` order. */
function labelRoles(roles: readonly CaseRole[]): CaseRole[] {
  if (roles.includes('case_manager')) return ['case_manager']
  return roles.filter((role) => !MOVING_ROLES.has(role))
}

/** The label of a lane with `roles` before it is numbered: "Vendor / Deployer". */
export function baseLabel(roles: readonly CaseRole[]): string {
  const shown = labelRoles(roles)
  return shown.length === 0 ? 'Participant' : shown.map((role) => ROLE_NAMES[role]).join(' / ')
}

/**
 * An actor's roles: its `CaseParticipant` records' roles when they name one a
 * label shows, else its `ParticipantStatus` records' roles. A record with no
 * roles, or only a moving one, says nothing about the part the actor plays.
 * Returns a fresh set.
 */
function resolveRoles(records: ReadonlySet<CaseRole> | undefined, statuses: ReadonlySet<CaseRole> | undefined): Set<CaseRole> {
  const fromRecords = [...(records ?? [])]
  if (fromRecords.some((role) => !MOVING_ROLES.has(role))) return new Set(fromRecords)
  return new Set([...fromRecords, ...(statuses ?? [])])
}

/**
 * Collect the lanes of `entries` (in `logIndex` order).
 *
 * A lane is every actor id the entries name as an activity's actor, as the
 * subject of its object (`attributedTo`), as a key of a case's
 * `actorParticipantIndex`, or as the actor of a `CaseParticipant` or
 * `ParticipantStatus` record anywhere in a payload. Within a kind, lanes keep
 * the order the ledger first names them in; two lanes with one label are
 * numbered from the second ("Coordinator", "Coordinator 2").
 */
export function buildLanes(entries: readonly CaseLedgerEntry[]): LaneDirectory {
  const seen: string[] = []
  const note = (url: unknown) => {
    if (typeof url === 'string' && url !== '' && !seen.includes(url)) seen.push(url)
  }
  const recordRoles = new Map<string, Set<CaseRole>>()
  const statusRoleSets = new Map<string, Set<CaseRole>>()
  const addRoles = (into: Map<string, Set<CaseRole>>, actor: string | null | undefined, roles: readonly CaseRole[]) => {
    if (!actor) return
    const set = into.get(actor) ?? new Set<CaseRole>()
    for (const role of roles) set.add(role)
    into.set(actor, set)
  }

  for (const entry of entries) {
    const snapshot = entry.payloadSnapshot
    note(snapshot?.actor)
    note(snapshot?.object?.attributedTo)
    for (const url of Object.keys(snapshot?.object?.actorParticipantIndex ?? {})) note(url)
    for (const record of objectsOfType<CaseParticipantSnapshot>(snapshot, 'CaseParticipant')) {
      note(record.attributedTo)
      addRoles(recordRoles, record.attributedTo, record.caseRoles ?? [])
    }
    for (const status of objectsOfType<ParticipantStatusSnapshot>(snapshot, 'ParticipantStatus')) {
      note(status.attributedTo)
      addRoles(statusRoleSets, status.attributedTo, statusRoles(status.cvdRole))
    }
  }

  // A ledger that names no CASE_MANAGER by role (an older log) still says who
  // it is: the actor that records the case's bootstrap entry, since only the
  // CASE_MANAGER writes the ledger (CLP-02-001).
  const resolved = new Map(seen.map((id) => [id, resolveRoles(recordRoles.get(id), statusRoleSets.get(id))]))
  const namesManager = [...resolved.values()].some((set) => set.has('case_manager'))
  const bootstrapActor = namesManager
    ? undefined
    : entries.find((entry) => BOOTSTRAP_TYPES.has(entry.semanticType))?.payloadSnapshot?.actor
  const unordered = seen.map((id) => {
    const named = resolved.get(id) ?? new Set<CaseRole>()
    if (id === bootstrapActor) named.add('case_manager')
    const roles = CASE_ROLES_VALUES.filter((role) => named.has(role))
    return { id, roles, kind: laneKind(roles) }
  })
  const ordered = KIND_ORDER.flatMap((kind) => unordered.filter((lane) => lane.kind === kind))

  const labelCounts = new Map<string, number>()
  let vendors = 0
  const lanes: ReplayLane[] = ordered.map((lane, index) => {
    const base = baseLabel(lane.roles)
    const count = (labelCounts.get(base) ?? 0) + 1
    labelCounts.set(base, count)
    const palette = lane.kind === 'vendor' ? `vendor-${++vendors}` : lane.kind
    return {
      ...lane,
      label: count === 1 ? base : `${base} ${count}`,
      roleLabel: labelRoles(lane.roles).map((role) => role.toUpperCase()).join(', '),
      palette,
      color: laneColor(lane.kind, vendors),
      index,
    }
  })

  const byId = new Map(lanes.map((lane) => [lane.id, lane]))
  return {
    lanes,
    get: (actorId) => (actorId ? byId.get(actorId) : undefined),
  }
}

/** The background color of a lane of `kind`; `vendorNumber` picks a Vendor's. */
function laneColor(kind: LaneKind, vendorNumber: number): string {
  switch (kind) {
    case 'vendor':
      return getVendorColor(vendorNumber)
    case 'casemanager':
      return PARTICIPANT_COLORS.casemanager
    case 'coordinator':
      return PARTICIPANT_COLORS.coordinator
    case 'reporter':
    case 'participant':
      return PARTICIPANT_COLORS.reporter
  }
}
