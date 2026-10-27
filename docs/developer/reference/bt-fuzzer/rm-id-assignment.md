---
stakeholder_type: [project-contributor]
---

# Vulnerability ID assignment fuzzer nodes

These stub nodes belong to the `AssignVulID` fallback tree (`vultron/bt/report_management/_behaviors/assign_vul_id.py`).
This tree models how a participant assigns a public vulnerability identifier to a validated report.
A Common Vulnerabilities and Exposures (CVE) ID is one such identifier.
The production tree is `create_assign_cve_id_tree` (`vultron/core/behaviors/report/assign_cve_id_tree.py`).

See the [fuzzer node index](index.md) for the entry format, the automation-potential and call-out shape values, and the base-type probabilities.

## Simulator nodes

### `IdAssigned`

- **Node name**: `IdAssigned`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether the vulnerability already has an identifier, such as a CVE ID
- **Input dependency**: Query to internal case metadata or to an external vulnerability registry, such as a CVE database lookup
- **Notes**: Fails most of the time in simulation because ID assignment is the main workflow.
  In production, this node is a simple metadata check
- **Automation potential**: **High** — a simple query against case metadata or a vulnerability registry.
  Full automation is possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssigned`
- **Call-out point shape**: Retriever — synchronous on-demand query to case metadata or an external vulnerability registry, such as a CVE database.
  The node returns SUCCESS if the vulnerability already has an identifier.
  It writes the existing ID to `output_keys = {"assigned_vul_id": str}`, so the parent tree has a guaranteed key on any successful path.
  A boolean is the simplest structured fact (ADR-0024, BT-18-006).
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — early-exit Retriever guard at the top of the `AssignVulID` Fallback Selector.
  The guard returns SUCCESS if an ID is already assigned, and so the tree skips the assignment work

### `InScope`

- **Node name**: `InScope`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether the vulnerability is in the scope of the applicable ID namespace, such as the CVE Numbering Authority (CNA) rules
- **Input dependency**: Human analyst review against CNA scope rules, or automated scope-checking against a product/component registry
- **Notes**: Scope rules are different for each ID space.
  A broad ID space can skip this check
- **Automation potential**: **High** — a policy check can encode and automate the scope rules for well-defined ID spaces, such as the CVE CNA rules.
  Ambiguous cases can need human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.InScope`
- **Call-out point shape**: Evaluator — compares the vulnerability attributes against the CNA scope rules or a product/component registry.
  The result tells whether the vulnerability is in the applicable ID namespace.
  The node returns a policy judgment (in-scope or out-of-scope), not a binary monitor.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — Evaluator condition guard early in the `_AssignIdIfInScope` Sequence, before the authority-check nodes

### `IsIDAssignmentAuthority`

- **Node name**: `IsIDAssignmentAuthority`
- **btz type**: `OftenSucceed` (p=0.70)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant is an ID assignment authority, such as a CVE CNA, that can assign IDs directly
- **Input dependency**: Organizational metadata or role configuration.
  A static capability check can fully automate it.
  The input is `CVDRole.CVE_NUMBERING_AUTHORITY` on the `case_roles` list of the participant.
  If the participant holds this role, the check succeeds.
- **Notes**: In production, this node is a static configuration check, not a runtime decision.
  More than one participant in the same case can hold `CVDRole.CVE_NUMBERING_AUTHORITY`, for example a vendor CNA and a coordinator CNA.
  Each participant evaluates this node independently in its own behavior tree (BT) context.
- **Automation potential**: **High** — static organizational configuration.
  A capability metadata lookup can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IsIDAssignmentAuthority`
- **Call-out point shape**: ProtocolInternal — reads a deployment-time configuration constant: `CVDRole.CVE_NUMBERING_AUTHORITY` on the `case_roles` of this participant.
  Participant registration sets the value.
  The node does not query an external system at runtime.
  There is no agent seam here: the check resolves fully in the DataLayer of the protocol.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — ProtocolInternal condition check in the `_AssignIdIfPossible` Sequence.
  It evaluates participant role metadata before `ProductInCNAScope`, `IsMostAppropriateCNA`, `IdAssignable`, and `AssignId`

### `IdAssignable`

- **Node name**: `IdAssignable`
- **btz type**: `ProbablySucceed` (p=0.67)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Condition — check whether this participant has the authority to assign an ID to this specific vulnerability.
  For example, the participant is the authoritative CNA for the affected product
- **Input dependency**: CNA rules lookup, product-to-CNA mapping, or human analyst determination.
  The participant must hold `CVDRole.CVE_NUMBERING_AUTHORITY`.
  This role is a necessary precondition, and `IsIDAssignmentAuthority` evaluates it.
  This node then evaluates the CNA scope rules against the affected product/component of the specific vulnerability.
  The result tells whether assignment authority applies here.
- **Notes**: A participant can be an ID authority in general (it holds `CVDRole.CVE_NUMBERING_AUTHORITY`) but not the authoritative CNA for this specific product.
  The two checks are separate and sequential: `IsIDAssignmentAuthority` first, `IdAssignable` second.
- **Automation potential**: **High** — the CVE Services application programming interface (API) or a local policy registry can automate the CNA-scope and product-to-CNA mapping checks.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.IdAssignable`
- **Call-out point shape**: Evaluator — matches the vulnerability attributes against the CNA scope rules and product-to-CNA mappings.
  The result tells whether this CNA (the `CVDRole.CVE_NUMBERING_AUTHORITY` participant) has assignment authority for this specific vulnerability.
  The node is a scope-matching evaluation, not a binary condition monitor.
  In the production tree, `IdAssignable` is not a single leaf.
  It is a SequenceNode subtree of 9 child nodes: exclusion guards, positive conditions, duplicate check, evidence bar, and holistic judgment.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — the factory composes the `IdAssignable` SequenceNode subtree inline in `_AssignIdIfPossible`, after `IsMostAppropriateCNA` succeeds.
  Each of its 9 child call-out points has a factory seam

### `RequestId`

- **Node name**: `RequestId`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Action — send an ID request to the applicable assignment authority, for example a CVE ID request to the applicable CNA
- **Input dependency**: API call to a CVE Services endpoint, such as the CVE.org API, or a manual submission by a human analyst
- **Notes**: The CVE Services API can fully automate this node
- **Automation potential**: **High** — an API call to the CVE Services endpoint, or to an equivalent ID-request interface, can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.RequestId`
- **Call-out point shape**: Retriever — sends a reservation/assignment request to an external ID assignment authority, such as the CVE Services API.
  The node writes the assigned ID to the case record.
  `output_keys = {"assigned_id": str}`.
  SUCCESS means that the node retrieved and recorded the ID.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — Retriever action node in the `_AssignOrRequestId` Fallback.
  The tree uses it when `_AssignIdIfPossible` fails (the non-CNA or out-of-scope path)

### `AssignId`

- **Node name**: `AssignId`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID`
- **Semantic function**: Action — assign an ID from the ID pool of the participant, when the participant is an assignment authority
- **Input dependency**: Internal ID pool management system, or the reserve/assign endpoint of the CVE Services API
- **Notes**: Always succeeds in simulation.
  In production, the node can make API calls or database writes
- **Automation potential**: **High** — a reserve/assign API call to the ID assignment authority, or to an internal ID pool management system, can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.report_management.assign_vul_id.AssignId`
- **Call-out point shape**: Composer — makes a new vulnerability identifier from the ID pool of this participant.
  It uses the ID management system or the CVE Services reserve/assign endpoint.
  `output_keys = {"assigned_vul_id": str}`.
  The artifact is the newly assigned ID, recorded in the case.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — Composer action node at the end of the `_AssignIdIfPossible` Sequence.
  The tree uses it when the `IdAssignable` subtree succeeds (the CNA-direct path)

---

## CVE ID assignment tree nodes

These call-out points exist only in the production tree.
They form the `IdAssignable` SequenceNode subtree and the `_AssignIdIfPossible` authority gate of `create_assign_cve_id_tree`.
The section numbers cite the CNA Operational Rules v4.1.0.

### `ProductInCNAScope`

- **Node name**: `ProductInCNAScope`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `_AssignIdIfPossible` (authority gate)
- **Semantic function**: Condition — evaluate whether the affected product is in the declared scope of this CNA (§3.1, §4.2.16.1).
- **Automation potential**: **High** — scope lists are machine-readable.
- **Call-out point shape**: Evaluator — evaluates the product against the scope registry of the CNA and returns a policy judgment with rationale.
  `output_keys = {"product_in_cna_scope": bool, "product_in_cna_scope_rationale": str}`.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — Evaluator in `_AssignIdIfPossible` Sequence, after `IsIDAssignmentAuthority`, before `IsMostAppropriateCNA`

### `IsMostAppropriateCNA`

- **Node name**: `IsMostAppropriateCNA`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `_AssignIdIfPossible` (authority gate)
- **Semantic function**: Condition — evaluate whether this CNA has first-refusal authority for the affected product (§4.2.1.1, §4.2.16.6).
- **Automation potential**: **High** — first-refusal registries are machine-readable.
- **Call-out point shape**: Evaluator — evaluates the CNA first-refusal registry and returns a judgment with rationale.
  `output_keys = {"is_most_appropriate_cna": bool, "is_most_appropriate_cna_rationale": str}`.
- **Factory-fn placement**: `vultron.core.behaviors.report.assign_cve_id_tree.create_assign_cve_id_tree` — Evaluator in `_AssignIdIfPossible` Sequence, after `ProductInCNAScope`, before the `IdAssignable` subtree

### `IsNotMaliciousCode`

- **Node name**: `IsNotMaliciousCode`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.1.8)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report is NOT about deliberately malicious code (§4.1.8).
- **Automation potential**: **High** — report classification flags are on the blackboard.
- **Call-out point shape**: Evaluator — evaluates report metadata against the §4.1.8 malicious-code exclusion criterion.
  `output_keys = {"is_not_malicious_code_verdict": bool, "is_not_malicious_code_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — first child of `IdAssignable` Sequence (cheapest guard)

### `IsNotDependencyUpdate`

- **Node name**: `IsNotDependencyUpdate`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.1.12)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report is NOT a dependency update without a security fix (§4.1.12).
- **Automation potential**: **High** — report type flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_not_dependency_update_verdict": bool, "is_not_dependency_update_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — second child of `IdAssignable` Sequence

### `IsNotEOLStatusAlone`

- **Node name**: `IsNotEOLStatusAlone`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.1.13)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report is NOT solely about end-of-life status (§4.1.13).
- **Automation potential**: **High** — report classification flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_not_eol_status_alone_verdict": bool, "is_not_eol_status_alone_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — third child of `IdAssignable` Sequence

### `IsNotDeliberatelyEducational`

- **Node name**: `IsNotDeliberatelyEducational`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (exclusion guard, §4.2.18)
- **Semantic function**: Exclusion guard — returns SUCCESS when the report is NOT about deliberately educational content (§4.2.18).
- **Automation potential**: **High** — report metadata flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_not_deliberately_educational_verdict": bool, "is_not_deliberately_educational_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — fourth child of `IdAssignable` Sequence

### `IsOrWillBePubliclyDisclosed`

- **Node name**: `IsOrWillBePubliclyDisclosed`
- **Source file**: *(ProtocolInternal — no factory seam)*
- **Parent tree**: `AssignVulID` → `IdAssignable` (positive condition, §4.2.2.1.2)
- **Semantic function**: ProtocolInternal gate — returns SUCCESS when the vulnerability is already publicly disclosed (CS.P flag) or has an active publication intent.
  Reads the disclosure plan flag and CS.P status from the blackboard.
- **Call-out point shape**: ProtocolInternal — OR-gate that reads the publication-intent flag and the CS.P blackboard status.
  No factory seam needed.
- **Factory-fn placement**: `create_assign_cve_id_tree` — fifth child of `IdAssignable` Sequence (inline ProtocolInternal node)

### `IsPubliclyAvailableProduct`

- **Node name**: `IsPubliclyAvailableProduct`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (positive condition, §4.2.10)
- **Semantic function**: Condition — returns SUCCESS when the affected product is publicly available (§4.2.10).
- **Automation potential**: **High** — product metadata flags are on the blackboard.
- **Call-out point shape**: Evaluator.
  `output_keys = {"is_publicly_available_product_verdict": bool, "is_publicly_available_product_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — sixth child of `IdAssignable` Sequence

### `NoDuplicateCVE`

- **Node name**: `NoDuplicateCVE`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (external duplicate check, §4.2.6, §4.2.15)
- **Semantic function**: Condition — returns SUCCESS when no existing CVE already covers this vulnerability.
  Makes a judgment with evidence.
- **Automation potential**: **High** — an API can automate CVE corpus queries.
- **Call-out point shape**: Evaluator — makes a deduplication judgment with confidence and evidence, not a binary query.
  `output_keys = {"no_duplicate_cve_verdict": bool, "no_duplicate_cve_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — seventh child of `IdAssignable` Sequence

### `MeetsEvidenceBar`

- **Node name**: `MeetsEvidenceBar`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (evidence quality check, §4.2.2.1.1)
- **Semantic function**: Condition — returns SUCCESS when the report meets the structural completeness and evidence quality bar for CVE assignment.
- **Automation potential**: **High** — structural field checks are automatable.
- **Call-out point shape**: Evaluator — evaluates report structural completeness against a configurable evidence bar.
  `output_keys = {"meets_evidence_bar_verdict": bool, "meets_evidence_bar_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — eighth child of `IdAssignable` Sequence

### `IsRealVulnerability`

- **Node name**: `IsRealVulnerability`
- **Source file**: `report_management/fuzzer/assign_vul_id.py`
- **Parent tree**: `AssignVulID` → `IdAssignable` (holistic §4.1 judgment, most expensive — placed last)
- **Semantic function**: Holistic judgment — returns SUCCESS when the report describes a genuine vulnerability per §4.1/§4.4.
  This node is different from `MeetsEvidenceBar`, which is a structural check.
  A structurally complete report can describe a non-vulnerability.
- **Automation potential**: **Medium** — automation can evaluate well-structured reports.
  New or ambiguous cases can need human judgment.
- **Call-out point shape**: Evaluator — makes a holistic §4.1 judgment.
  `output_keys = {"is_real_vul": bool, "is_real_vul_rationale": str}`.
- **Factory-fn placement**: `create_assign_cve_id_tree` — ninth (last) child of `IdAssignable` Sequence (most expensive, placed last per cheapest-first rule)
