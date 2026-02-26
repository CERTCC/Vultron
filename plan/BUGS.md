# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## ✅ FIXED — Demo Commands produce no visible output

**Fixed in**: `vultron/demo/cli.py` (logging.basicConfig added to `main` group callback)

Running from a command line, `uv run vultron-demo initialize-case` produced
no output because the CLI never called `logging.basicConfig()`, so Python's
default WARNING-level root logger suppressed all INFO-level demo messages.

**Resolution**: The `main` click group now accepts `--debug` and `--log-file`
options and calls `logging.basicConfig(force=True)` with INFO level (or DEBUG
with `--debug`) before any sub-command runs. Tests added in
`test/demo/test_cli.py`.