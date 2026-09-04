---
title: "Provisional ADRs can assert an unimplemented enforcement contract as present-tense fact"
type: learning
timestamp: "2026-09-03T00:00:00Z"
source: ISSUE-2860
signal: theme-candidate
---

ADR-0075 (`status: accepted-provisional`) stated as settled fact that
`ParticipantStatus` construction "validates role-dimension invariants at
object-creation time, raising `VultronValidationError` on violation" via a
`model_validator(mode='after')`. That raise was never built — the real
`model_validator` (`mode='before'`) only *auto-seeds* the applicable dimension
and deliberately does not reject a stray one. `notes/case-state-model.md` then
copied the claim ("raises `VultronValidationError` immediately — it is never
silently corrected"), so a false invariant propagated from a provisional ADR
into an active design note. Issue #2860 was filed on the belief that the
invariant was unenforced *anywhere*; in fact it is enforced at the guard layer
(trigger fail-closed + receive partial-accept), and a construction raise is
positively wrong because it would fire inside the wire→core extractor on
untrusted self-reported roles and break the emit/receive Postel asymmetry.

**Pattern**: an `accepted-provisional` ADR describes an *intended* contract but
is written in the present/definite tense of a shipped one. Downstream notes
quote it verbatim as fact. When the implementation later diverges (or was never
written), the drift is silent — nothing ties the ADR sentence to a test.

**Recognizable trigger**: reading a provisional ADR (or a note that cites one)
that asserts a validation/enforcement behavior in present tense. Before relying
on it, grep for the named validator/guard and confirm it actually raises/refuses
— the claim may be aspirational.

**Suggested routing for `/learn`**: consider auditing other
`accepted-provisional` ADRs for present-tense claims of enforcement that no test
pins, and/or a convention that provisional ADRs phrase unbuilt contracts in the
future/conditional tense ("will raise") until a linked regression test exists.

---

**Promoted**: 2026-09-03 — general convention captured in `notes/specs-vs-adrs.md` (§ "A Provisional ADR Must Phrase an Unbuilt Contract in the Future Tense"). The specific defects this entry named were already corrected on `main` while resolving #2860 (now CLOSED): ADR-0075 § "Validation" and `notes/case-state-model.md` § "Role-Specific VFD Access" both now describe guard-layer enforcement and the non-raising `mode="before"` auto-seed. Docs PR: <https://github.com/CERTCC/Vultron/pull/3147>.
