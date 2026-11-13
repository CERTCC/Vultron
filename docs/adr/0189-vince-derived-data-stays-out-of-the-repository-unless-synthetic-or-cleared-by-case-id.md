---
status: accepted
status_override: >-
  Decided by the maintainer, who holds the data-handling authority for
  VINCE-derived data, while planning #5956 on 2026-11-12.
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-12
revision: 2
amended: "2026-11-12"
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# VINCE-Derived Data Stays Out of the Repository Unless It Is Synthetic or Cleared by Case Id

## Context and Problem Statement

The VINCE shadow (Epic #5954) reads VINCE cases, keeps a local copy as CERT/CC's Case Manager, and prompts a human.
VINCE cases hold embargoed vul data and TLP-labeled content.
Nothing in the project said whether data read from VINCE may pass through the dev container, logs, test fixtures, Coding Agent sessions, the repository, or published material.
Each enforcement Task under the Epic needs a stated rule to test.

The shadow work starts with an API credential for a test VINCE instance that holds no production cases (#5957).
Live production cases come later, through a CERT/CC-owned account and host (#6338).
**Which rules hold for VINCE-derived data, and which of them must wait for live data?**

## Decision Drivers

- Git history is permanent: one committed VINCE response needs a history rewrite to remove.
- Logs are copied into issues, CI artifacts and Coding Agent sessions, so a log line is a publication path.
- The build work needs real API shapes, which only the test instance gives.
- Sanitization must be tried somewhere a leak costs nothing, yet still be tested as if the data were sensitive.
- Each rule must be a checkable statement with a Task that enforces it.

## Considered Options

- Treat test-instance data as freely usable, because it holds no production cases.
- Treat test-instance data as sensitive everywhere, so neither the dev container nor a Coding Agent may read it.
- Let test-instance data be read where the work happens, and let it out only as synthetic data or by per-case clearance.

## Decision Outcome

Chosen option: "Let test-instance data be read where the work happens, and let it out only as synthetic data or by per-case clearance", because it gives the build work real API shapes while every route into the repository or a publication passes through either a sanitizer or a maintainer.

The rules:

1. **Storage.** The shadow keeps no long-lived copy of VINCE-derived records. It builds a translation for the request that needs it and discards it afterwards; transient working files within a request are allowed. Its container mounts no persistent volume. Enforced by #5958. *(Amended 2026-11-12.)*
2. **Readers, test stage.** Data from the test VINCE instance may be read in the dev container and in Coding Agent sessions.
3. **Clearance.** Data read from a VINCE instance enters the repository, or anything published, only if it is synthetic or a maintainer has cleared its VINCE case id. A clearance names one case id; a Coding Agent may ask for one, and never grants one. A committed cleared-case list records each clearance with a link to the maintainer's comment. Enforced by #5961.
4. **Synthetic.** A file is synthetic only if the committed fixture generator (#5961) or the sanitizer (#6348) wrote it, and it carries the synthetic marker. Sanitizer output keeps a case's shape and none of its content or ids, so it needs no clearance. Enforced by #5961 and #6348.
5. **Logs.** A shadow-mode log record carries VINCE case, activity and actor ids, never case content. Enforced by #5959, which conforms to the general log-content rule once #5607 settles it.
6. **Credential.** The VINCE API credential is read at runtime only, and never appears in a config file, log record, exception message or repr. Enforced by #5960.
7. **Retention, test stage.** No retention rule: test-instance data may be deleted at any time.

Two rules are **not decided** here: who and what may read live production data, and how long it is kept after a VINCE case closes.
Both are open in #6349, which blocks the production account (#6338), so no live case is read under the test-stage rules.

### Consequences

- Good, because every path from VINCE into git or a publication is either a tested sanitizer or a named maintainer decision.
- Good, because the sanitizer's leak test runs against real API shapes with no real case at risk.
- Good, because the production stage cannot start before its own rules exist.
- Bad, because per-case clearance is a human step for every unsanitized example.
- Neutral, because a Coding Agent acts under its operator's GitHub account, so no check can tell a maintainer's clearance comment from an agent's. Rule 3's "never grants" holds by agent instruction and review, not by the check.

## Validation

Each numbered rule names the Task whose tests enforce it.
`specs/vince-shadow-data.yaml` restates rules 1 and 3 to 6 as requirements, each citing this record.

## Pros and Cons of the Options

### Treat test-instance data as freely usable

- Good, because it adds no process.
- Bad, because test-instance cases are still written by people, and nothing would catch a real detail in one.
- Bad, because the habits and checks it builds would not hold once live data arrives.

### Treat test-instance data as sensitive everywhere

- Good, because the test stage would rehearse the strictest live rule.
- Bad, because the connector, mapping and sanitizer could not be built against real API shapes.

### Read where the work happens; let out only synthetic or cleared data

- Good, because work proceeds on real shapes, and the exits are guarded.
- Bad, because a clearance list must be kept.

## Amendment — 2026-11-12

Rule 1 (Storage) was replaced.
It read: "In shadow mode, VINCE-derived records live only in the store `database.db_url` names, and that store resolves outside the repository checkout. Enforced by #5958."
It now reads: "The shadow keeps no long-lived copy of VINCE-derived records. It builds a translation for the request that needs it and discards it afterwards; transient working files within a request are allowed. Its container mounts no persistent volume. Enforced by #5958."

The shadow is now a standalone tool that hosts no actor and has no store of its own ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md)), so there is no `database.db_url` for the rule to point at.
The rule's purpose holds and is stronger: no VINCE-derived record outlives the request, inside the repository or out of it.
VSD-01-001 and VSD-01-002 are retired; SHD-01-003 (no copy kept after its request) and SHD-02-001 (no persistent volume) replace them.
So `specs/vince-shadow-data.yaml` now restates rules 3 to 6, and rule 1 is restated in `specs/case-shadow.yaml`; the Validation section's "rules 1 and 3 to 6" predates this amendment.

- Source: #6336

## More Information

Planned in #5956. Live-data readers and retention: #6349.

Generated spec requirements: `vince-shadow-data.yaml` VSD-01 and VSD-02.
