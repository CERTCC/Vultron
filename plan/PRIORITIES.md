# Priorities

Getting `scripts/receive_report_demo.py` working again is the top priority.
The script was originally implemented using a previous version of the codebase,
see for example `vultron/api/v2/backend/_old_handlers/*.py` to find some of the
original logic. What has changed since then is that we moved to the TinyDB 
based backing store in `vultron/api/v2/datalayer/tinydb_backend.py`, and we have
completely revamped the `vultron/api/v2/backend/inbox_handler.py` to use the
dispatcher-based architecture in `vultron/behavior_dispatcher.py` along with
`vultron/api/v2/backend/handlers.py`. These things are not currently wired together
properly, so `receive_report_demo.py` is not working.
There are tests in `test/scripts/test_receive_report_demo.py` that can help guide
the implementation, but they are failing because of the changes described above
so they will also need to be reworked to match the new architecture.


Features that primarily serve to improve production-readiness are lower priority
than any of the above.