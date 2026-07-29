---
title: "BT Fuzzer Nodes: RM Vulnerability ID Assignment"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Vulnerability ID Assignment
  sub-workflow (`AssignVulIdBt`): CVE ID acquisition, publication readiness,
  and ID-assignment nodes used in simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-fuzzer-nodes-report-management.md
  - notes/bt-integration.md
  - notes/bt-canonical-reference.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/report_management
---

## Vulnerability ID Assignment

These nodes belong to the `AssignVulID` fallback tree
(`vultron/bt/report_management/_behaviors/assign_vul_id.py`), which models
the process of assigning a public vulnerability identifier (e.g., a CVE ID)
to a validated report.

### `IdAssigned`

- **Node name**: `IdAssigned`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether the vulnerability has
  already been assigned an identifier (e.g., CVE ID)
- **Input dependency**: Query to internal case metadata or an external
  vulnerability registry (e.g., CVE database lookup)
- **Notes**: Fails most of the time in simulation because ID assignment is
  the main workflow; in production this is a simple metadata check
- **Automation potential**: **High** — simple query against case metadata or a vulnerability registry; fully automatable.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssigned`
- **Call-out point shape**: Retriever — synchronous on-demand query to case
  metadata or an external vulnerability registry (e.g., CVE database); returns
  SUCCESS if an identifier has already been assigned to this vulnerability,
  writing the existing ID to `output_keys = {"assigned_vul_id": str}` so the
  parent tree has a guaranteed key on any successful path. A boolean is the
  simplest structured fact (ADR-0024); the on-demand query pattern makes this a
  Retriever, not a Sentinel (see BT-18-006).
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — early-exit Retriever guard at the top of `AssignVulID`
  Fallback Selector; returns SUCCESS if an ID is already assigned,
  short-circuiting assignment work

### `InScope`

- **Node name**: `InScope`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether the vulnerability is
  within the scope of the relevant ID namespace (e.g., CVE CNA rules)
- **Input dependency**: Human analyst review against CNA scope rules, or
  automated scope-checking against a product/component registry
- **Notes**: Scope rules vary by ID space; a broad ID space may skip
  this check
- **Automation potential**: **High** — scope rules for well-defined ID spaces (e.g., CVE CNA rules) can be encoded as a policy check and automated; may require human review for ambiguous cases.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.InScope`
- **Call-out point shape**: Evaluator — evaluates whether the vulnerability falls within the applicable ID namespace by comparing vulnerability attributes against CNA scope rules or a product/component registry; returns a policy judgment (in-scope or out-of-scope), not a binary monitor.
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — Evaluator condition guard early in `_AssignIdIfInScope`
  Sequence, before the authority-check nodes

### `IsIDAssignmentAuthority`

- **Node name**: `IsIDAssignmentAuthority`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant is
  itself an ID assignment authority (e.g., a CVE CNA) able to assign
  IDs directly
- **Input dependency**: Organizational metadata / role configuration;
  fully automatable as a static capability check.  Driven by
  `CVDRole.CVE_NUMBERING_AUTHORITY` on the participant's `case_roles`
  list — if the participant holds this role, the check succeeds.
- **Notes**: In production this is a static configuration check, not a
  runtime decision.  Multiple participants in the same case may
  independently hold `CVDRole.CVE_NUMBERING_AUTHORITY` (e.g., a vendor
  CNA and a coordinator CNA); each evaluates this node independently in
  their own BT context.
- **Automation potential**: **High** — static organizational configuration; can be fully automated as a capability metadata lookup.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IsIDAssignmentAuthority`
- **Call-out point shape**: ProtocolInternal — reads a deployment-time configuration constant (`CVDRole.CVE_NUMBERING_AUTHORITY` on this participant's `case_roles`); the value is set at participant registration, not queried from an external system at runtime. There is no agent seam here: the check resolves entirely within the protocol's own DataLayer.
  (Category 2 per issue #1199 triage — reads a flag written by the protocol's own deployment-time setup.)
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — ProtocolInternal condition check in `_AssignIdIfPossible`
  Sequence; evaluates participant role metadata before `ProductInCNAScope`,
  `IsMostAppropriateCNA`, `IdAssignable`, and `AssignId`

### `IdAssignable`

- **Node name**: `IdAssignable`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant has
  authority to assign an ID to this specific vulnerability (e.g., is the
  authoritative CNA for the affected product)
- **Input dependency**: CNA rules lookup, product-to-CNA mapping, or
  human analyst determination.  Requires that the participant holds
  `CVDRole.CVE_NUMBERING_AUTHORITY` (necessary precondition, evaluated
  by `IsIDAssignmentAuthority`); this node then evaluates the CNA's
  scope rules against the specific vulnerability's affected product/
  component to determine whether assignment authority applies here.
- **Notes**: A participant may be an ID authority generally (holds
  `CVDRole.CVE_NUMBERING_AUTHORITY`) but not the authoritative CNA for
  this specific product.  The two checks are separate and sequential:
  `IsIDAssignmentAuthority` first, `IdAssignable` second.
- **Automation potential**: **High** — CNA-scope and product-to-CNA mapping checks are automatable via the CVE Services API or a local policy registry.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssignable`
- **Call-out point shape**: Evaluator — evaluates whether this CNA
  (`CVDRole.CVE_NUMBERING_AUTHORITY` participant) has assignment
  authority for this specific vulnerability by matching vulnerability
  attributes against CNA scope rules and product-to-CNA mappings;
  a scope-matching evaluation, not a binary condition monitor. In the
  full production tree (issue #1246) `IdAssignable` is a SequenceNode
  subtree of 9 child nodes (exclusion guards, positive conditions, duplicate
  check, evidence bar, and holistic judgment), not a single leaf.
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — the `IdAssignable` SequenceNode subtree is composed
  inline within `_AssignIdIfPossible`, after `IsMostAppropriateCNA`
  succeeds; factory seams are on each of its 9 child call-out points

### `RequestId`

- **Node name**: `RequestId`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Action — submit a request for an ID to the
  appropriate assignment authority (e.g., submit a CVE ID request to the
  relevant CNA)
- **Input dependency**: API call to a CVE services endpoint (e.g.,
  CVE.org API), or human analyst manual submission
- **Notes**: Could be fully automated via the CVE Services API
- **Automation potential**: **High** — can be fully automated as an API call to the CVE Services endpoint or equivalent ID-request interface.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.RequestId`
- **Call-out point shape**: Retriever — queries an external ID assignment authority (e.g., CVE Services API) with a reservation/assignment request and writes the resulting assigned ID to the case record; `output_keys = {"assigned_id": str}`; SUCCESS = ID retrieved and recorded.
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — Retriever action node in `_AssignOrRequestId` Fallback,
  used when `_AssignIdIfPossible` fails (non-CNA or out-of-scope path)

### `AssignId`

- **Node name**: `AssignId`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Action — assign an ID from the participant's own
  ID pool (when the participant is an assignment authority)
- **Input dependency**: Internal ID pool management system or CVE Services
  API (reserve/assign endpoint)
- **Notes**: Always succeeds in simulation; in production may involve
  API calls or database writes
- **Automation potential**: **High** — can be fully automated as an API call (reserve/assign) to the ID assignment authority or an internal ID pool management system.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.AssignId`
- **Call-out point shape**: Composer — generates a new vulnerability identifier from this participant's own ID pool via the ID management system or CVE Services reserve/assign endpoint; `output_keys = {"assigned_vul_id": str}`; the produced artifact is the newly assigned ID recorded in the case.
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — Composer action node at the end of `_AssignIdIfPossible`
  Sequence, used when `IdAssignable` subtree succeeds (CNA-direct path)

---

## New nodes added in issue #1246 (full CVE ID assignment tree)

The following call-out points are part of the expanded `IdAssignable` SequenceNode
subtree and the `_AssignIdIfPossible` authority-gate section introduced by
`create_assign_cve_id_tree` (issue #1246), grounded in CNA Operational Rules v4.1.0.

### `ProductInCNAScope`

- **Node name**: `ProductInCNAScope`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `_AssignIdIfPossible` (authority gate)
- **Semantic function**: Condition — evaluate whether the affected product
  is within this CNA's declared scope (§3.1, §4.2.16.1).
- **Automation potential**: **High** — scope lists are machine-readable.
- **Call-out point shape**: Evaluator — evaluates the product against the
  CNA's scope registry and returns a policy judgment with rationale.
  `output_keys = {"product_in_cna_scope": bool,
  "product_in_cna_scope_rationale": str}`.
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — Evaluator in `_AssignIdIfPossible` Sequence, after
  `IsIDAssignmentAuthority`, before `IsMostAppropriateCNA`

### `IsMostAppropriateCNA`

- **Node name**: `IsMostAppropriateCNA`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `_AssignIdIfPossible` (authority gate)
- **Semantic function**: Condition — evaluate whether this CNA has
  first-refusal authority for the affected product (§4.2.1.1, §4.2.16.6).
- **Automation potential**: **High** — first-refusal registries are machine-readable.
- **Call-out point shape**: Evaluator — evaluates the CNA first-refusal
  registry and returns a judgment with rationale.
  `output_keys = {"is_most_appropriate_cna": bool,
  "is_most_appropriate_cna_rationale": str}`.
- **Factory-fn placement**: Implemented in
  `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree`
  (issue #1246) — Evaluator in `_AssignIdIfPossible` Sequence, after
  `ProductInCNAScope`, before the `IdAssignable` subtree

### `IsNotMaliciousCode`

- **Node name**: `IsNotMaliciousCode`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.1.8)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report
  is NOT about deliberately malicious code (§4.1.8).
- **Automation potential**: **High** — report classification flags are on the blackboard.
- **Call-out point shape**: Evaluator — evaluates report metadata against
  the §4.1.8 malicious-code exclusion criterion.
  `output_keys = {"is_not_malicious_code_verdict": bool,
  "is_not_malicious_code_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — first child of
  `IdAssignable` Sequence (cheapest guard)

### `IsNotDependencyUpdate`

- **Node name**: `IsNotDependencyUpdate`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.1.12)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report
  is NOT a dependency update without a security fix (§4.1.12).
- **Automation potential**: **High** — report type flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_not_dependency_update_verdict": bool,
  "is_not_dependency_update_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — second child of
  `IdAssignable` Sequence

### `IsNotEOLStatusAlone`

- **Node name**: `IsNotEOLStatusAlone`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.1.13)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report
  is NOT solely about end-of-life status (§4.1.13).
- **Automation potential**: **High** — report classification flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_not_eol_status_alone_verdict": bool,
  "is_not_eol_status_alone_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — third child of
  `IdAssignable` Sequence

### `IsNotDeliberatelyEducational`

- **Node name**: `IsNotDeliberatelyEducational`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.2.18)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report
  is NOT about deliberately educational content (§4.2.18).
- **Automation potential**: **High** — report metadata flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_not_deliberately_educational_verdict": bool,
  "is_not_deliberately_educational_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — fourth child of
  `IdAssignable` Sequence

### `IsOrWillBePubliclyDisclosed`

- **Node name**: `IsOrWillBePubliclyDisclosed`
- **Source file**: *(ProtocolInternal — no factory seam)*
- **Parent tree**: `AssignVulID` → `IdAssignable` (positive condition, §4.2.2.1.2)
- **Semantic function**: ProtocolInternal gate — returns SUCCESS when the
  vulnerability is already publicly disclosed (CS.P flag) or has an active
  publication intent. Reads the disclosure plan flag and CS.P status from
  the blackboard.
- **Call-out point shape**: ProtocolInternal — OR-gate reading publication-intent
  flag and CS.P blackboard status. No factory seam needed.
- **Factory-fn placement**: Implemented in issue #1246 — fifth child of
  `IdAssignable` Sequence (inline ProtocolInternal node)

### `IsPubliclyAvailableProduct`

- **Node name**: `IsPubliclyAvailableProduct`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (positive condition, §4.2.10)
- **Semantic function**: Condition — returns SUCCESS when the affected product
  is publicly available (§4.2.10).
- **Automation potential**: **High** — product metadata flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_publicly_available_product_verdict": bool,
  "is_publicly_available_product_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — sixth child of
  `IdAssignable` Sequence

### `NoDuplicateCVE`

- **Node name**: `NoDuplicateCVE`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (external duplicate check,
  §4.2.6, §4.2.15)
- **Semantic function**: Condition — returns SUCCESS when no existing CVE
  already covers this vulnerability. Makes a judgment with evidence.
- **Automation potential**: **High** — CVE corpus queries are automatable via API.
- **Call-out point shape**: Evaluator — makes a deduplication judgment with
  confidence/evidence (not a binary query). `output_keys =
  {"no_duplicate_cve_verdict": bool, "no_duplicate_cve_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — seventh child of
  `IdAssignable` Sequence

### `MeetsEvidenceBar`

- **Node name**: `MeetsEvidenceBar`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (evidence quality check,
  §4.2.2.1.1)
- **Semantic function**: Condition — returns SUCCESS when the report meets
  the structural completeness / evidence quality bar for CVE assignment.
- **Automation potential**: **High** — structural field checks are automatable.
- **Call-out point shape**: Evaluator — evaluates report structural completeness
  against a configurable evidence bar. `output_keys =
  {"meets_evidence_bar_verdict": bool, "meets_evidence_bar_rationale": str}`.
- **Factory-fn placement**: Implemented in issue #1246 — eighth child of
  `IdAssignable` Sequence

### `IsRealVulnerability`

- **Node name**: `IsRealVulnerability`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (holistic §4.1 judgment,
  most expensive — placed last)
- **Semantic function**: Holistic judgment — returns SUCCESS when the report
  describes a genuine vulnerability per §4.1/§4.4. Distinct from
  `MeetsEvidenceBar` (structural check); a structurally complete report
  may describe a non-vulnerability.
- **Automation potential**: **Medium** — well-structured reports may be
  evaluated automatically; novel or ambiguous cases may require human judgment.
- **Call-out point shape**: Evaluator — makes a holistic §4.1 judgment.
  `output_keys = {"is_real_vul": bool, "is_real_vul_rationale": str}`.
  Types are placeholder stubs marked for replacement with typed dataclasses
  before issue #1558.
- **Factory-fn placement**: Implemented in issue #1246 — ninth (last) child of
  `IdAssignable` Sequence (most expensive, placed last per cheapest-first rule)

---
