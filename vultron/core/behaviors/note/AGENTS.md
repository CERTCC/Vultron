# AGENTS.md — `vultron/core/behaviors/note/`

Agent guidance for note-related BT nodes in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../AGENTS.md).

---

## AttachNoteToCase Idempotency: Check Attachment, Not Existence

(DR-08, 2026-04-20)

`AttachNoteToCaseNode.update()` MUST check whether the note is already
**attached to the case** for idempotency — NOT whether the note object exists
in the DataLayer.

```python
# WRONG — note may exist in DataLayer without being attached to the case
if dl.read(note.id_) is not None:
    return Status.SUCCESS  # false idempotency

# CORRECT — check the case's note reference list
case = dl.read(case_id)
if note.id_ in case.notes:
    return Status.SUCCESS  # truly idempotent
case.notes.append(note.id_)
dl.save(case)
return Status.SUCCESS
```

**Why this matters**: The DataLayer stores notes as top-level objects
independently of their attachment to a case. A note can be created and
persisted without ever being added to `case.notes`. Checking
`dl.read(note_id) is not None` would falsely skip re-attachment if the note
was stored by another path but never linked.

---

## `memory=False` Note Sequence: Partial-Write on FAILURE

(BTND07-913, 2026-06-15; see `specs/behavior-tree-node-design.yaml` BTND-07-001)

`add_note_to_case_trigger_bt` uses a `Sequence(memory=False)` with three
children:

1. `CreateNoteNode` — creates and writes the note to the DataLayer
2. `AttachNoteFromResultNode` — attaches the note to the case
3. `SenderSideBT` — enqueues the outbound activity

If `SenderSideBT` fails (e.g., no CASE_MANAGER recipient resolved), steps 1
and 2 have already committed. **The note IS attached to the case locally even
though the overall BT returns FAILURE.** Tests MUST assert this partial-write
behavior explicitly so future readers do not assume FAILURE → no writes occurred.

**Design implication**: When using `memory=False` sequences for partially-
reversible operations, document which steps are non-transactional and what
state is committed if a later step fails.

For the generic `memory=False` partial-write rule, see
`notes/bt-pitfalls.md` § "`memory=False` Sequence: Partial-Write Behavior on
FAILURE".
