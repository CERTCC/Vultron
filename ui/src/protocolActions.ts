/**
 * Bridge between the demo's action IDs and the protocol state machines.
 *
 * The multi-vendor demo dispatches ~29 string action IDs (see the
 * `handleAction` switch in App-multivendor.tsx). This table records, for each
 * action, how it relates to the four protocol machines defined in
 * `data/json/protocol_states.json` (accessed via `./protocol`).
 *
 * Three kinds:
 *   - 'transition' — the action IS one machine step. The filter layer can gate
 *     it purely with `isLegalTransition(machine, currentState, trigger)`, and a
 *     handler can compute its destination with `requireNextState(...)`. This is
 *     the clean case the deferral effort targets.
 *   - 'composite' — the action drives more than one machine step, or a step
 *     that the demo applies implicitly (e.g. report receipt advances both RM
 *     and VFD; publication advances PXA and terminates EM). Handlers may use
 *     the listed transitions, but gating stays hand-written because no single
 *     machine state decides availability.
 *   - 'demo' — the action has no protocol-machine meaning at all (notes/Q&A,
 *     vendor invitations, publication acknowledgement). These are outside the
 *     scope of `protocol_states.json` (see ui/CLAUDE.md §6 / §9) and keep their
 *     existing demo-owned logic.
 *
 * NOTE on states absent from the artifact: the demo uses a 'DECLINED' RM
 * pseudo-state for declined invitations. It is NOT a real RM state in
 * `protocol_states.json` and is intentionally not represented here — keep any
 * 'DECLINED' handling as demo-only logic.
 */

import type { MachineName } from './protocol'

interface MachineStep {
  machine: MachineName
  trigger: string
}

export type ActionProtocolMapping =
  | { kind: 'transition'; machine: MachineName; trigger: string }
  | { kind: 'composite'; transitions: MachineStep[]; note: string }
  | { kind: 'demo'; note: string }

/**
 * Action ID → how it maps onto the protocol machines.
 *
 * Several distinct action IDs intentionally share a trigger (e.g.
 * `propose-embargo` and `*-propose-revision` are both `em.propose`); the EM
 * machine distinguishes them by source state (NONE→PROPOSED vs ACTIVE→REVISE),
 * so the same trigger applied from different `emState`s does the right thing.
 */
export const ACTION_PROTOCOL_MAP: Record<string, ActionProtocolMapping> = {
  // ---- Finder: report submission (composite, demo-gated) -----------------
  // Creates the Vendor + Case Actor lanes and advances the first vendor's RM
  // (START→RECEIVED via `receive`) and VFD (vfd→Vfd via `vendor_becomes_aware`)
  // in one step. Gated by `phase === 'start'`, not by a machine state.
  'submit-report': {
    kind: 'composite',
    transitions: [
      { machine: 'rm', trigger: 'receive' },
      { machine: 'vfd', trigger: 'vendor_becomes_aware' },
    ],
    note: 'Report receipt: advances new vendor RM (receive) and VFD (vendor_becomes_aware); also creates lanes.',
  },

  // ---- Finder: embargo (EM machine) --------------------------------------
  'finder-accept-embargo': { kind: 'transition', machine: 'em', trigger: 'accept' },
  'finder-reject-embargo': { kind: 'transition', machine: 'em', trigger: 'reject' },
  'finder-propose-revision': { kind: 'transition', machine: 'em', trigger: 'propose' },
  'finder-accept-revision': { kind: 'transition', machine: 'em', trigger: 'accept' },
  'finder-reject-revision': { kind: 'transition', machine: 'em', trigger: 'reject' },

  // ---- Finder: RM ---------------------------------------------------------
  'finder-close-case': { kind: 'transition', machine: 'rm', trigger: 'close' },

  // ---- Finder: demo-only --------------------------------------------------
  'finder-add-note': { kind: 'demo', note: 'Q&A note; no machine slot (see CLAUDE.md §6).' },
  'finder-notify-published': { kind: 'demo', note: 'Acknowledgement of publication; not a machine transition.' },
  'finder-invite-vendor': {
    kind: 'demo',
    note: 'Invites a new vendor (creates a lane); the new vendor RM/VFD advance via the same receipt logic as submit-report.',
  },

  // ---- Case Actor: embargo (EM machine) ----------------------------------
  'propose-embargo': { kind: 'transition', machine: 'em', trigger: 'propose' },
  'caseactor-propose-revision': { kind: 'transition', machine: 'em', trigger: 'propose' },
  'caseactor-accept-revision': { kind: 'transition', machine: 'em', trigger: 'accept' },
  'caseactor-reject-revision': { kind: 'transition', machine: 'em', trigger: 'reject' },

  // ---- Vendor: RM ---------------------------------------------------------
  'validate-report': { kind: 'transition', machine: 'rm', trigger: 'validate' },
  'invalidate-report': { kind: 'transition', machine: 'rm', trigger: 'invalidate' },
  'accept-report': { kind: 'transition', machine: 'rm', trigger: 'accept' },
  'defer-report': { kind: 'transition', machine: 'rm', trigger: 'defer' },
  'vendor-close-case': { kind: 'transition', machine: 'rm', trigger: 'close' },

  // ---- Vendor: embargo (EM machine) --------------------------------------
  'accept-embargo': { kind: 'transition', machine: 'em', trigger: 'accept' },
  'reject-embargo': { kind: 'transition', machine: 'em', trigger: 'reject' },
  'vendor-propose-revision': { kind: 'transition', machine: 'em', trigger: 'propose' },
  'vendor-accept-revision': { kind: 'transition', machine: 'em', trigger: 'accept' },
  'vendor-reject-revision': { kind: 'transition', machine: 'em', trigger: 'reject' },

  // ---- Vendor: VFD --------------------------------------------------------
  'notify-fix-ready': { kind: 'transition', machine: 'vfd', trigger: 'fix_is_ready' },
  'notify-fix-deployed': { kind: 'transition', machine: 'vfd', trigger: 'fix_is_deployed' },

  // ---- Vendor: publication (composite) -----------------------------------
  // Publishing makes the vuln public (PXA `public_becomes_aware`) and forces
  // any live embargo to EXITED (EM `terminate`). Gated by `vfdState === 'VFD'`
  // and "not already public", neither of which is a single transition check.
  'vendor-notify-published': {
    kind: 'composite',
    transitions: [
      { machine: 'pxa', trigger: 'public_becomes_aware' },
      { machine: 'em', trigger: 'terminate' },
    ],
    note: 'Publication: PXA public_becomes_aware + EM terminate (embargo ends). EM terminate only applies from ACTIVE/REVISE.',
  },

  // ---- Vendor: demo-only --------------------------------------------------
  'vendor-reply-note': { kind: 'demo', note: 'Reply to a Q&A note; no machine slot.' },
  'vendor-invite-next-vendor': {
    kind: 'demo',
    note: 'Invites a new vendor (creates a lane); see finder-invite-vendor.',
  },

  // ---- External actors: PXA ----------------------------------------------
  // Real-world events outside any participant's control (CLAUDE.md §3 / filters).
  'trigger-exploit': { kind: 'transition', machine: 'pxa', trigger: 'exploit_made_public' },
  'trigger-attacks': { kind: 'transition', machine: 'pxa', trigger: 'attacks_are_observed' },
}

/** Look up an action's protocol mapping, or `undefined` if unmapped. */
export function getActionMapping(actionId: string): ActionProtocolMapping | undefined {
  return ACTION_PROTOCOL_MAP[actionId]
}
