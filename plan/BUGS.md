# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYYYMMDDXX` for bug IDs, where `YYYYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,  
the first bug identified on March 26, 2026 would be `BUG-2026032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-2026041001 Tests are slow

The test suite has slowed down significantly, which is affecting development
velocity. Run the suite to investigate which tests are taking the longest
and identify bottlenecks. Consider whether any of the slowest tests can be
optimized, isolated, or refactored to improve overall test suite performance
without sacrificing coverage or reliability.
