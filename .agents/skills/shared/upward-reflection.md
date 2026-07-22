# Upward-Reflection Checklist

Before writing learning files at the end of a `build` or `bugfix` session, run
this checklist. For each signal type, if the answer is "yes", a learning file
with the matching `signal:` tag is required (BW-07-001, BW-07-002).

| Signal type | Question to ask |
|---|---|
| `spec-gap` | Was any behaviour implemented or fixed that has no existing spec entry? |
| `spec-ambiguity` | Was any requirement unclear? What interpretation was made? |
| `spec-contradiction` | Did two requirements appear to conflict? |
| `design-question` | Was an architectural decision made beyond what the issue specified? |
| `concern` | Was any fragility, risk, or technical debt encountered that should be tracked as a GitHub Concern issue? |
| `tooling-issue` | Was any environment or tooling problem encountered? |
| `process-issue` | Was the issue body stale, the issue already implemented, or tracking otherwise broken? |

Record each triggered signal as an individual learning file in
`plan/incoming/learnings/` (filename: `YYYYMMDD-SLUG.md`; frontmatter:
`title`, `type: learning`, `timestamp`, `source`, and optionally
`signal: <type>`). Do not write completion summaries here.

A session with no learning files is valid only if this checklist was run and
every answer was "no". Skipping the checklist is not allowed.
