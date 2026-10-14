---
source: NOTES-case-state-model--potential-actions-per-case-state
timestamp: '2026-10-12T19:32:56.220524+00:00'
title: Potential Actions per Case State
type: note
---

**Archived:** 2026-10-12
**Reason:** reference material already published per state in docs/
**Superseded by:** docs/reference/case_states/; vultron/core/case_states/patterns/potential_actions.py

---

## Potential Actions per Case State

`vultron/core/case_states/patterns/potential_actions.py` maps 6-character state
patterns (e.g., `"...P.."`, `"VfdpX."`) to `Actions` enum values — things a
participant COULD do when the case is in a given state.

The patterns use regex-like matching where `.` matches either letter of a
dimension. For example:

- `"...P.."` → public is aware → recommend terminating embargo, publishing vul
- `"....X."` → exploit is public → publish detection, monitor refinement
- `".....A"` → attacks observed → publish detection, monitor additional attacks

**Important**: These are menus of **possible** actions, not required actions.
Actual decisions are left to participant policy. This makes the pattern table
useful for:

- Future UI design (show actionable suggestions given current state)
- Future agent design (understand what actions are available)
- Protocol documentation (explain why transitions matter)

The corresponding documentation is in `docs/reference/case_states/*.md` — one
file per case state, each listing available actions and context.
