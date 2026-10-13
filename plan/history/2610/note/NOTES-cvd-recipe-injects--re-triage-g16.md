---
source: NOTES-cvd-recipe-injects--re-triage-g16
timestamp: '2026-10-12T23:51:02.087232+00:00'
title: 'CVD recipe injects: G16 Tier B re-triage record (#2844)'
type: note
---

Archived from `notes/cvd-recipe-injects.md` by #4497 (notes sweep): the G16
re-triage (#2844, closed) is complete, and its verdicts now live in each Tier B
entry's *Gap* line and in the summary table of `notes/cvd-recipe-injects.md`.
The section was a record of how the verdicts changed, not a rule.

---

## Re-triage (G16, #2844, 2026-09-24)

The Tier B gap statements were written in July 2026 (#2051) and several had
gone stale by the time they were sorted. The re-triage checked each against the
code and specs of the day and reached a different verdict for three of the six.

| Recipe | Verdict | Why |
|---|---|---|
| x03 | Blocked — party discovery | Unchanged. Ejected from G08 (#2836) to G13 (#2841), which is deferred. |
| x05 | Blocked — pseudonymity | No pseudonym or redacted-view mechanism exists (#2562, G13, deferred). |
| x12 | Authorable, sequenced | Needs a case created already public, which EP-04-008 specifies but is not built. Task #3673. |
| x16 | Authorable now | The multi-vendor invite and suggest flows already exist. The gap statement was stale. Task #3674. |
| x17 | Blocked — admission | An outsider has no protocol act for asking to join a case (#3670). |
| x21 | Authorable now | A mid-case coordinator invite plus ownership transfer is exactly `fvcv-handoff`. The gap statement was stale. Task #3675. |

**Do not re-derive these gaps from the entries below.** The *Gap* lines record
what the re-triage found, not what the original filing said.
