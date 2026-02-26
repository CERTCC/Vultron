# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## ~~test_check_server_availability_logs_retry_attempts failure~~ [FIXED 2026-02-26]

**Root cause**: `TestCliLogging.teardown_method` reset root logger to
`WARNING`, and `TestCliSubCommands`/`TestCliAll` left root at `INFO` after
invoking the CLI. The function logs at `DEBUG`, so caplog captured nothing
when root was above DEBUG.

**Fix**: Added `with caplog.at_level(logging.DEBUG):` to the test;
changed `teardown_method` to use `logging.NOTSET` instead of `logging.WARNING`.

