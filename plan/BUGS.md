# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

**FIXED (2026-02-19)**: `setup_clean_environment` did not clear `ACTOR_IO_STORE`
before re-initializing actor I/O for demos 2 and 3. This caused demos 2 and 3 to
fail with `KeyError: 'ActorIO for actor_id finndervul already exists'`.

Fix: call `clear_all_actor_ios()` in `setup_clean_environment` before calling
`init_actor_ios`. Added regression test `test_all_demos_succeed` in
`test/scripts/test_receive_report_demo.py`.

---
