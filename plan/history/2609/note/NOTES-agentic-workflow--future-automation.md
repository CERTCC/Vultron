---
source: NOTES-agentic-workflow--future-automation
timestamp: '2026-09-17T17:13:37.021465+00:00'
title: Future Automation (agentic workflow)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) speculative; superseded by delivered skill pipeline
**Superseded by:** specs/build-workflow.yaml

---

## Future Automation

The trigger conditions in the loop are based on observable file-change
signals, making the entire pipeline amenable to a behavior tree (BT)
implementation:

```text
Selector (priority order)
├── Sequence: Open Idea-type GitHub issues? → ingest-idea
├── Sequence: BUILD_LEARNINGS.md changed? → learn
├── Sequence: specs/ or notes/ changed? → update-plan
└── Sequence: Open GitHub Issues in top-priority group? → build
```

Each condition node checks a file-system signal; each action node invokes
the corresponding skill. The BT's selector ensures the highest-priority
condition is always serviced first.
