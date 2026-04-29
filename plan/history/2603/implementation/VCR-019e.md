---
title: "VCR-019e \u2014 Convert non-StrEnum Enums to StrEnum (2026-03-19)"
type: implementation
date: '2026-03-19'
source: VCR-019e
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2299
legacy_heading: "VCR-019e \u2014 Convert non-StrEnum Enums to StrEnum (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## VCR-019e — Convert non-StrEnum Enums to StrEnum (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2299`
**Canonical date**: 2026-03-19 (git blame)
**Legacy heading**

```text
VCR-019e — Convert non-StrEnum Enums to StrEnum (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

**Task**: Convert older non-StrEnum Enums to `StrEnum` where semantically
appropriate, per VCR-019c study results.

**What was done**:

1. Converted 6 `IntEnum` component classes in `vultron/core/states/cs.py`
   to `StrEnum`:
   - `VendorAwareness`: values "v" / "V"
   - `FixReadiness`: values "f" / "F"
   - `FixDeployment`: values "d" / "D"
   - `PublicAwareness`: values "p" / "P"
   - `ExploitPublication`: values "x" / "X"
   - `AttackObservation`: values "a" / "A"
   The lowercase/uppercase letters directly correspond to the state-string
   notation already used throughout the codebase (e.g., "vfdpxa").
   Updated `state_string_to_enum2` return type annotation from
   `Tuple[IntEnum, ...]` to `Tuple[StrEnum, ...]`.

2. Converted `MessageTypes` in `vultron/bt/messaging/states.py` from
   plain `Enum` to `StrEnum`. Removed the `VULTRON_MESSAGE_EMBARGO_REVISION_*`
   primary entries (these were already Python aliases for the non-REVISION
   variants since they shared the same string values). The short aliases
   `EV`, `EJ`, `EC` are retained as explicit aliases for `EP`, `ER`, `EA`
   respectively to avoid breaking callsites. Removed the `EmbargoRevisionProposal`,
   `EmbargoRevisionRejected`, `EmbargoRevisionAccepted` long-name aliases.
   Removed the `__str__` override (StrEnum provides str() = value by default).
   Cleaned up `EM_MESSAGE_TYPES` to remove the duplicate EV/EJ/EC entries.

3. Updated `test/bt/test_case_states/test_states.py`:
   `test_state_string_to_enum2` now checks string values (`str(result[i]) == c`)
   instead of integer values (`== 0` / `== 1`).

4. Updated `test/bt/test_behaviortree/test_messaging/test_messaging_states.py`:
   Replaced assertions that EV/EJ/EC are aliases for the now-removed
   `EmbargoRevisionProposal/Rejected/Accepted` with assertions that EV/EJ/EC
   are aliases for EP/ER/EA.

**Result**: 982 tests pass. The string values of `VendorAwareness`, etc. now
match the state-string notation directly, making the codebase more self-
documenting and removing the historical IntEnum artifact.
