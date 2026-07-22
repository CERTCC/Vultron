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
- **Call-out point shape**: Retriever — synchronous on-demand query to case metadata or an external vulnerability registry (e.g., CVE database); returns SUCCESS if an identifier has already been assigned to this vulnerability, FAILURE otherwise. A boolean is the simplest structured fact (ADR-0024); the on-demand query pattern makes this a Retriever, not a Sentinel (see BT-18-006).
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  early-exit Retriever guard at the top of `AssignVulID` Fallback Selector;
  returns SUCCESS if an ID is already assigned, short-circuiting assignment work

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
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.assign_vul_id_tree.create_assign_vul_id_tree`
  (`in_scope_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Evaluator condition guard early in `AssignVulID` Sequence, before the
  authority-check nodes

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
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  ProtocolInternal condition check in `AssignVulID` Sequence; evaluates
  participant role metadata before `IdAssignable` and `AssignId`

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
  a scope-matching evaluation, not a binary condition monitor.
- **Factory-fn placement**: Phase 1 stub now exists as of PR #1357 —
  `vultron.core.behaviors.report.assign_vul_id_tree.create_assign_vul_id_tree`
  (`id_assignable_factory` param). FUTURE full placement:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Evaluator condition guard in the assign-direct path Sequence, after
  `IsIDAssignmentAuthority` succeeds

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
- **Call-out point shape**: Retriever — queries an external ID assignment authority (e.g., CVE Services API) with a reservation/assignment request and writes the resulting assigned ID to the case record; SUCCESS = ID retrieved and recorded.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Retriever action node in the request-external-id Sequence, used when
  `IsIDAssignmentAuthority` fails (non-CNA path)

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
- **Call-out point shape**: Composer — generates a new vulnerability identifier from this participant's own ID pool via the ID management system or CVE Services reserve/assign endpoint; the produced artifact is the newly assigned ID recorded in the case.
- **Factory-fn placement**: FUTURE:
  `vultron.core.behaviors.report.create_assign_vul_id_tree` (issue #1246) —
  Composer action node in the direct-assign Sequence, used when
  `IdAssignable` succeeds (CNA-direct path)

---
