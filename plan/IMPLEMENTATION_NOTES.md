# Implementation Notes

This file tracks insights, issues, and learnings during implementation.

**Last Updated**: 2026-02-18

---

When we get to BT-1.4: Handler Refactoring, modifying the existing procedural
logic in `/api/v2/backend` will break
`vultron/scripts/receive_report_demo.py` script. Instead, we should create 
a new set of handlers that use the BT implementation, and then we will need to 
create a new demo script that uses those handlers. This will allow us to keep the existing
demo script working while we transition to the new BT-based implementation. 
Adding BT-based handlers while retaining the existing procedural handlers 
might have implications to the `vultron/api/v2` module structure, since we might
need to propagate things back up to routers or even the main FastAPI app. 
We should be mindful of this as we implement the new handlers, and we should aim
to keep the module structure clean and organized. Consider making the FastAPI 
invocation selective to use either the procedural or BT-based handlers based on
a configuration setting, command line flag, or environment variable, to allow
for easy switching between implementations without code changes. This can be
added into the docker configs as well so that you could run either version of the
app in a container. (So the old `receive_report_demo.py` could use a container
running the procedural version, and a new `receive_report_demo_bt.py` could use
a container running the BT-based version.)

#### Cross-References

- **Plan**: `plan/BT_INTEGRATION.md` (detailed architecture)
- **Spec**: `specs/behavior-tree-integration.md` (requirements)
- **Priority**: `plan/PRIORITIES.md` (BT integration is top priority)
- **Updated**: `plan/IMPLEMENTATION_PLAN.md` (added Phase BT-1 tasks)
