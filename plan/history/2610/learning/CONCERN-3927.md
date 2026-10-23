---
source: CONCERN-3927
timestamp: '2026-10-05T17:40:31.392547+00:00'
title: Every non-empty ratchet baseline names an open owning issue, checked in CI
  (ARCH-18)
type: learning
---

Five live architecture ratchets held debt whose only cited tracking issue was closed, or cited no issue at all. ARCH-18 required bidirectional equality and same-commit removal but said nothing about who drives a non-empty baseline to zero. MS-10-006 already imposed that rule on the spec corpus. The concern proposed an `# owner: #N` comment on every non-empty baseline and a CI check that the cited issue is open.

Decisions:

- The owner marker is a comment beside each baseline. A baseline that is permanent by design carries `# permanent: <reference>` instead, tied to the ratchet versus pinned-exemption-set split in #3933.
- Two checks: an offline unit test (marker present, permanent reference non-empty) and a scheduled online job (owner still open).
- The online job files or updates one tracking issue and never fails the build, so `main` cannot go red because an unrelated issue closed (the #3828 pin-to-live-count race).

**Resolved**: 2026-10-05 — implementation tracked in #4205, #4206.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4204>.

Spec: `specs/architecture.yaml` (ARCH-18-003, ARCH-18-004).

Notes: `notes/architecture-ratchet-corpus.md`.
