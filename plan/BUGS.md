# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

~~The test suite takes a long time to run. It especially seems to slow down when
running `test/scripts/test_receive_report_demo.py`. Evaluate this test file
to determine if there are any optimizations that can be made to speed up the
test suite.~~ **FIXED** (see IMPLEMENTATION_NOTES.md)