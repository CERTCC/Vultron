---
source: NOTES-embargo-default-semantics--protocol-source
timestamp: '2026-10-12T19:33:15.376066+00:00'
title: Protocol Source
type: note
---

**Archived:** 2026-10-12
**Reason:** duplicate of the default-path table in the same note
**Superseded by:** docs/topics/process_models/em/defaults.md

---

## Protocol Source

The rules specified in EP-04 derive directly from
`docs/topics/process_models/em/defaults.md`:

| Protocol scenario | em_state outcome |
|---|---|
| Receiver has default; sender proposes nothing | `EM.ACTIVE` (EP-04-001) |
| Sender shorter, receiver longer | `EM.ACTIVE` at sender's duration; `EM.REVISE` for receiver's longer (EP-04-003) |
| Sender longer, receiver shorter | `EM.ACTIVE` at receiver's default; `EM.REVISE` for sender's longer (EP-04-003) |
