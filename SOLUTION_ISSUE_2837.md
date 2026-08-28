# Solution for Issue #2837

## 🛠️ Proposed Solution (by Aditya Waghamare)

### Analysis
Uncontrolled vocabulary growth stems from missing explicit admission criteria, causing each extension request to be judged ad‑hoc. This leads to inconsistency and risk of bloated protocol definitions.

### Fix
1. **Create an ADR (ADR‑004X) – Vocabulary Admission Policy** that codifies:
   - **Protocol Vocabulary vs. Deployment Convention**
   - **AS2‑Expressibility‑First Rule**
   - **Enforcement Obligations & Optionality**
   - **Review Process & Trigger Conditions**
2. **Apply the policy** to the four pending items and record a verdict for each member.
3. **Create Tasks** only for items that receive an *admit* verdict, parented to epic #2567.  If TLP (#2564) is admitted, split its enforcement work into a separate task.

### Implementation
#### ADR‑004X – Vocabulary Admission Policy
```markdown
# ADR‑004X: Vocabulary Admission Policy

## Context
The Vultron protocol relies on a stable, well‑defined vocabulary. Historically, new terms have been added on a case‑by‑case basis, leading to scope creep and ambiguous enforcement responsibilities.

## Decision
We introduce a formal admission policy that must be satisfied before any term is added to the **protocol vocabulary**. The policy distinguishes between **protocol vocabulary** (terms that affect message semantics, validation, or enforcement) and **deployment conventions** (operational defaults, UI hints, or optional metadata that do not alter protocol behavior).

### 1. Protocol Vocabulary vs. Deployment Convention
| Category | Definition | Impact |
|----------|------------|--------|
| **Protocol Vocabulary** | A term that appears in the AS2‑2.0 message schema, influences validation, or creates new enforcement rules. | Must be versioned, documented, and supported by all compliant implementations. |
| **Deployment Convention** | Local or optional metadata used by a specific deployment, does not affect cross‑implementation validation. | Can be added without protocol change; documented in deployment guides only. |

### 2. AS2‑Expressibility‑First Rule
*Any proposed term must be expressible using existing AS2 constructs before a new term is introduced.*
- If the intent can be modelled with existing fields, enumerations, or extensions (e.g., using `CustomHeaders`), the proposal is rejected as a **deployment convention**.
- Only when the semantics cannot be captured by AS2 does a new protocol term become eligible.

### 3. Enforcement Obligations
When a term introduces enforcement (e.g., required handling, legal obligations, or automated actions), the following must be provided:
- **Specification of required behavior** for receivers and senders.
- **Test vectors** demonstrating correct enforcement.
- **Backward‑compatibility strategy** (e.g., optionality flag, version bump).
If these artifacts are missing, the term is **deferred** until they are supplied.

### 4. Optionality & Defaulting
New fields must be explicitly marked as **optional** or **required**:
- `optional: true` – receivers may ignore the field; no enforcement.
- `required: true` – receivers must validate and act on the field; enforcement obligations apply.
Defaults must be defined to avoid ambiguity in existing deployments.

### 5. Review Process & Triggers
| Trigger | Action |
|---------|--------|
| **Policy Violation** – proposal fails any of the above checks | **Reject** with rationale. |
| **Missing Enforcement Artifacts** – partial compliance | **Defer**; request missing documentation or test vectors. |
| **All Checks Passed** | **Admit**; create a task under the domain epic #2567. |

## Consequences
- Guarantees consistent, minimal vocabulary growth.
- Provides a clear decision path for future proposals.
- Enables automated tooling to validate new proposals against the policy.

## References
- ADR‑0049 (G01) – Error‑Reply/NACK facet (used as worked example).
- AS2‑2.0 Specification.
```

#### Verdicts per Member (based on ADR‑004X)
| Member Issue | Proposal Summary | Verdict | Rationale (policy reference) |
|--------------|-------------------|---------|------------------------------|
| **#2563** – bug bounty protocol support: scope decision and vocabulary design | Introduces a new `BountyScope` enum to AS2 messages. | **Defer** | Enforcement artifacts (validation rules, test vectors) are missing; requires explicit optional/required flag (Section 3). |
| **#2564** – TLP field support: vocabulary extension and enforcement rules | Proposes a new `TLP` field with mandatory enforcement (must block messages with disallowed TLP levels). | **Admit** (with split task) | Satisfies AS2‑Expressibility‑First (new semantic not representable), provides enforcement spec (Section 3). Enforcement work will be a separate task as required by constraints. |
| **#1955** – add a `MitigationDeployed` message type | Introduces a new message type to signal mitigation status. | **Reject** | This is a **deployment convention** – can be expressed using existing `CustomHeaders` (Section 1). No protocol‑level semantics needed. |
| **#2214** – rescind an unanswered embargo invitation via `Undo(Invite(EmbargoEvent))` | Uses existing AS2 verbs (`Undo`) and composes existing `Invite` and `EmbargoEvent`. No new term required. | **Reject** | No new vocabulary; merely a composition of existing terms (Section 2). |

#### Tasks to Create (parented to epic #2567)
- **Task 1**: Implement the `TLP` field in the AS2 schema, add validation logic, and update the spec. (Parent: #2567) – *Enforcement rules will be captured in a sub‑task `TLP‑Enforcement`.*
- **Task 2** (`TLP‑Enforcement`): Define enforcement policies, test vectors, and backward‑compatibility strategy for the `TLP` field. (Parent: Task 1)

### Testing
1. Verify ADR‑004X is merged into the `spec/adr/` directory and referenced from the main spec index.
2. Run the repository CI lint step to ensure the new ADR file follows naming conventions (`ADR-004X.md`).
3. Confirm that the four member issues now contain the verdict comments above.
4. Ensure the two new tasks are created via the GitHub UI (or via automation) with `parent` set to #2567 and linked to the ADR.
5. Validate that the `TLP` implementation passes existing message validation tests and the new enforcement test vectors.

---
*Signed‑off‑by: Aditya Waghamare <adityawaghamare7620@gmail.com>*

---
*Submitted by Aditya Waghamare*
💰 **Payout Address (Base L2 / EVM):** `0xb61dBcdBc3407F71EaCb64D4CBFAcf9FFfe2415C`