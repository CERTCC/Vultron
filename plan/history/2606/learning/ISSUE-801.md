---
source: ISSUE-801
timestamp: '2026-06-11T18:36:32.475318+00:00'
title: Wire actor vocabulary overrides must preserve base-module registration
type: learning
---

## 2026-06-09 ISSUE-801 — Wire actor vocabulary overrides must preserve base-module registration

- Overriding all actor keys in `VOCABULARY` from `vultron_actor.py` can leave
  `vultron.wire.as2.vocab.base.objects.actors` with zero registered concrete
  types, tripping the registry-completeness invariant.
- Keep at least one base-actors-module registration (for now `Actor` →
  `as_Actor`) and override concrete keys (`Person`, `Organization`, etc.) with
  wire-branch Vultron actor subclasses.

**Promoted**: 2026-06-11 — captured in `notes/vocabulary-registry.md` §
"Vocabulary Override Preservation" and `AGENTS.md` pitfalls.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
