---
status: accepted
status_override: >-
  Decided by the maintainer, who holds the data-handling authority for
  VINCE-derived data, while planning #5956 on 2026-11-12; the readers and
  retention rules were decided by the maintainer while planning #6349 on
  2026-11-13.
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-13
revision: 3
amended: "2026-11-13"
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# VINCE-Derived Data Stays Out of the Repository Unless It Is Synthetic or Cleared by Case Id

## Context and Problem Statement

The VINCE shadow (Epic #5954) reads one VINCE case on request, translates it, and shows an analyst where the case stands ([ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md)).
VINCE cases hold embargoed vul data and TLP-labeled content.
Nothing in the project said whether data read from VINCE may pass through the dev container, logs, test fixtures, Coding Agent sessions, the repository, or published material.
Each enforcement Task under the Epic needs a stated rule to test.

The shadow work starts with an API credential for a test VINCE instance that holds no production cases (#5957).
Later, a VINCE user runs the shadow with their own credential and reads the cases VINCE shows them.
**Which rules hold for VINCE-derived data, in development and in use?**

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

1. **Storage.** The shadow keeps no long-lived copy of VINCE-derived records. It builds a translation for the request that needs it and discards it afterwards; transient working files within a request are allowed. Its container mounts no persistent volume. Enforced by #5958.
2. **Readers.** The shadow adds no reader. The person who runs it sets the VINCE base URL and credential, and sees, on their own machine, only the cases that credential can see in VINCE. Development work, including Coding Agent sessions, should use a test VINCE instance with test credentials; test-instance data may be read in the dev container and in Coding Agent sessions. Running the shadow against production VINCE is a VINCE user's own use, governed by VINCE's terms, not by this project.
3. **Clearance.** Data read from a VINCE instance enters the repository, or anything published, only if it is synthetic or a maintainer has cleared its VINCE case id. A clearance names one case id; a Coding Agent may ask for one, and never grants one. A committed cleared-case list records each clearance with a link to the maintainer's comment. Enforced by #5961.
4. **Synthetic.** A file is synthetic only if the committed fixture generator (#5961) or the sanitizer (#6348) wrote it, and it carries the synthetic marker. Sanitizer output keeps a case's shape and none of its content or ids, so it needs no clearance. Enforced by #5961 and #6348.
5. **Logs.** A shadow-mode log record carries VINCE case, activity and actor ids, never case content. Enforced by #5959, which conforms to the general log-content rule once #5607 settles it.
6. **Credential.** The VINCE API credential is read at runtime only, and never appears in a config file, log record, exception message or repr. Enforced by #5960.
7. **Retention.** No retention rule. Rule 1 leaves no copy to keep after a request, so none is left when a VINCE case closes. A copy a user makes from the shadow's output falls under that user's VINCE obligations.

### Consequences

- Good, because every path from VINCE into git or a publication is either a tested sanitizer or a named maintainer decision.
- Good, because the sanitizer's leak test runs against real API shapes with no real case at risk.
- Good, because the shadow grants no access of its own: VINCE's access control decides what each user sees.
- Bad, because per-case clearance is a human step for every unsanitized example.
- Neutral, because a Coding Agent acts under its operator's GitHub account, so no check can tell a maintainer's clearance comment from an agent's. Rule 3's "never grants" holds by agent instruction and review, not by the check.
- Neutral, because the developer supplies the base URL and credential, so no check can tell a test instance from production. Rule 2's "development should use a test instance" records intent, and holds by the developer's choice.

## Validation

Each numbered rule names the Task whose tests enforce it.
`specs/vince-shadow-data.yaml` restates rules 3 to 6 as requirements, each citing this record.
`specs/case-shadow.yaml` restates rule 1 as SHD-01-003 (no copy kept after its request) and SHD-02-001 (no persistent volume).
Rules 2 and 7 add no requirement: rule 2 cannot be checked, and rule 1's requirements already cover rule 7.

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

## Amendment — 2026-11-13

Rules 2 and 7 were replaced, and the paragraph that left two rules undecided was removed.
Rule 2 read: "**Readers, test stage.** Data from the test VINCE instance may be read in the dev container and in Coding Agent sessions."
Rule 7 read: "**Retention, test stage.** No retention rule: test-instance data may be deleted at any time."
The paragraph read: "Two rules are **not decided** here: who and what may read live production data, and how long it is kept after a VINCE case closes. Both are open in #6349, which blocks the production account (#6338), so no live case is read under the test-stage rules."
The consequence "Good, because the production stage cannot start before its own rules exist." was replaced by the one on VINCE's access control.

The shadow is a tool that each VINCE user runs with their own credential, not one CERT/CC-owned deployment, so there is no shared production host or account to set rules for.
It keeps nothing past a request (rule 1), so no retention rule has anything to apply to.
Whether development uses a test instance depends on the base URL and credential the developer supplies, so rule 2 records that intent and no check enforces it.
The Context section and the Validation section were updated to match, and Validation now names both specs.

- Source: #6349

## More Information

Planned in #5956. Storage rule revised in #6336. Readers and retention rules decided in #6349.

Generated spec requirements: `vince-shadow-data.yaml` VSD-01 and VSD-02.
