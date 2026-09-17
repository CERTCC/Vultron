---
source: NOTES-message-type-reference--page-architecture
timestamp: '2026-09-17T17:25:25.274049+00:00'
title: Page architecture
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) pages realized; #2998 ratchet landed
**Superseded by:** docs/reference/messages/

---

## Page architecture

Reference pages live in `docs/reference/messages/`. Formal-model pages are keyed
on the **shorthand**; the remainder are keyed on the **wire activity**, because
no shorthand exists to key them on.

| Page | Keyed on | Covers |
|---|---|---|
| `index.md` | — | Bidirectional mapping overview; how to read collapse/expansion |
| `rm.md` | Shorthand | `RS RI RV RD RA RC RK RE` |
| `em.md` | Shorthand | `EP ER EA EV EJ EC ET EK EE` |
| `cs.md` | Shorthand | `CV CF CD CP CX CA CK CE` |
| `general.md` | Shorthand | `GI GK GE` |
| `faults_and_acknowledgements.md` | Mechanism family | The fault trichotomy; the acknowledgement evolution |
| `case_management.md` | Wire activity | Lifecycle, roster, invitations, role delegation, ownership transfer |
| `case_proposal.md` | Wire activity | Pre-case bootstrap (ADR-0023) |
| `ledger_replication.md` | Wire activity | SYNC substrate |

Each page carries, per message type: protocol role and triggering transition,
the wire activity that conveys it, the discriminating payload field where the
mapping is a collapse, a rendered example, and links to the how-to guide and the
formal transition table.

Every mapping row carries a **status**: `implemented`, `collapsed-into-X`,
`expanded-into-X`, or `evolved-to-X` (for the fault and acknowledgement cases
above). Reference material states what is true, including divergence from the
normative set — see DF-05-003 and DF-05-004.

### One primary page per entry, not one page per entry

MSM-06-002 designates a **primary** page per `SEMANTIC_REGISTRY` entry rather
than requiring each entry to appear on exactly one page, because the collapse
inventory above makes the stricter rule unsatisfiable. The entries that
legitimately need a second home:

| Entry | Primary page | Also appears on | Why |
|---|---|---|---|
| `add_participant_status_to_participant` | `cs.md` | `rm.md` | `vf_state`/`d_state` carry CV/CF/CD; `rm_state` carries the RM ladder |
| `close_report` | `rm.md` | `faults_and_acknowledgements.md` | `RC` on the RM page; an ordinary `as:Reject` on the faults page (MSM-05-003) |
| `reject_case_ledger_entry` | `ledger_replication.md` | `faults_and_acknowledgements.md` | The ledger NAK is both the SYNC mechanism and the acknowledgement story (MSM-05-002) |

Build the #2998 ratchet against the primary designation. Reading MSM-06-002 as
"one page, full stop" will make it look unimplementable.

### Mapping tables are rendered, never hand-written

Render the tables at build time from the MSM spec registry joined against
`SEMANTIC_REGISTRY`, following the `docs/reference/specs/*.md` →
`vultron/metadata/specs/docs_render.py` pattern. Hand-written tables rot: the
orphaned JSONs under `docs/reference/examples/` and the failing `markdown_exec`
example blocks tracked by #2904 are what that rot looks like after a couple of
years.

MSM-06-002 requires a ratchet test asserting every `SEMANTIC_REGISTRY` entry
reaches its designated primary reference page, so a new registry entry cannot be
added without being documented or explicitly exempted. **That ratchet is
implemented in `test/architecture/test_msm_coverage_ratchet.py`**, landed in
PR 2998.
