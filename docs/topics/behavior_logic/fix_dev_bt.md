---
stakeholder_type: [project-contributor]
---

# Fix Development Behavior

## Requirements

{% include-markdown "./_requirements_pointer.md" %}

- [CSB-09](../../reference/vultron-spec/requirements/state-behavior.md#protocol-csb-09) — Enter CS V (Vendor Aware)
- [CSB-10](../../reference/vultron-spec/requirements/state-behavior.md#protocol-csb-10) — Enter CS F (Fix Ready)
- [CSB-15](../../reference/vultron-spec/requirements/state-behavior.md#protocol-csb-15) — Trigger-Side VFD Role Preconditions

{% include-markdown "./_conformant_implementation_note.md" %}

{% include-markdown "../../includes/notional_external_process.md" %}

{% include-markdown "./_legacy_diagram_note.md" %}

The Fix Development Behavior Tree is shown below.

```mermaid
---
title: Fix Development Behavior Tree
---
flowchart LR
    fb["?"]
    role_not_vendor(["role is not vendor?"])
    fb -->|A| role_not_vendor
    cs_in_VF(["CS in VF...?"])
    fb -->|B| cs_in_VF
    seq["&rarr;"]
    fb -->|C| seq
    rm_in_a(["RM in A?"])
    seq --> rm_in_a
    create_fix["create fix"]
    seq --> create_fix
    fix_ready(["fix ready?"])
    seq --> fix_ready
    cs_to_VF["CS &rarr; VFd...<br/>(emit CF)"]
    seq --> cs_to_VF
```

(A) Fix development is relegated to the Vendor role, so Non-Vendors return *Success* since they have nothing further to do.

(B) For Vendors, if a fix is ready (i.e., the case is in $q^{cs} \in VF\cdot\cdot\cdot\cdot$), the tree returns *Success*.

(C) Otherwise, engaged Vendors ($q^{rm} \in A$) can

- create fixes
- set $q^{cs} \in Vfd\cdot\cdot\cdot \xrightarrow{\mathbf{F}} VFd\cdot\cdot\cdot$
- emit $CF$ upon completion
