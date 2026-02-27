# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

### Linkchecker reports errors

Status: Fixed (2026-02-27) — updated demo link in docs/reference/code/demo/index.md to point to docs/tutorials/receive_report_demo.md.


When running linkchecker on the documentation, there are some errors that 
need to be fixed. All documentation links must use paths relative to the 
site root (where site root = `docs/`), and they must point to files that 
actually exist.

Tech hint: `mkdocs build` will build the site, and the `linkchecker` utility 
can be used to check for broken links. Command to run: `mkdocs site && linkchecker site`
This should become part of any checks run when files in the `docs/` directory 
are modified. It is not necessary to run when modifying files outside of 
`docs/`.


```shell

URL        `../../../howto/activitypub/tutorial_receive_report.md'
Name       `Demo Tutorial'
Parent URL file:///home/runner/work/Vultron/Vultron/site/reference/code/demo/index.html, line 3501, col 5
Real URL   file:///home/runner/work/Vultron/Vultron/site/howto/activitypub/tutorial_receive_report.md
Check time 0.000 seconds
Result     Error: URLError: <urlopen error [Errno 2] No such file or directory: '/home/runner/work/Vultron/Vultron/site/howto/activitypub/tutorial_receive_report.md'>
WARNING bs4.dammit 2026-02-26 22:19:29,515 CheckThread-file:///home/runner/work/Vultron/Vultron/site/sitemap.xml.gz Some characters could not be decoded, and were replaced with REPLACEMENT CHARACTER.
 7 threads active,     0 links queued, 1426 links in 1433 URLs checked, runtime 16 seconds

Statistics:
Downloaded: 20.9MB.
Content types: 12 image, 410 text, 0 video, 0 audio, 428 application, 2 mail and 581 other.
URL lengths: min=16, max=967, avg=85.

That's it. 1433 links in 1433 URLs checked. 0 warnings found. 1 error found.
Stopped checking at 2026-02-26 22:19:31+000 (17 seconds)
```

---

### Logging errors when running pytest

When running the test suite with pytest, there are a lot of errors like the 
following examples. They are not causing tests to fail, but they are very noisy
and make it difficult to see the actual test results.

```shell
--- Logging error ---
Traceback (most recent call last):
  File "/Users/adh/.local/share/uv/python/cpython-3.13.7-macos-x86_64-none/lib/python3.13/logging/__init__.py", line 1154, in emit
    stream.write(msg + self.terminator)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I/O operation on closed file.
Call stack:
  File "/Users/adh/Applications/PyCharm.app/Contents/plugins/python-ce/helpers/pycharm/_jb_pytest_runner.py", line 84, in <module>
    sys.exit(pytest.main(args, plugins_to_load + [Plugin]))
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 199, in main
    ret: ExitCode | int = config.hook.pytest_cmdline_main(config=config)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 318, in wrap_session
    session.exitstatus = doit(config, session) or 0
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 372, in _main
    config.hook.pytest_runtestloop(session=session)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 396, in pytest_runtestloop
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 118, in pytest_runtest_protocol
    runtestprotocol(item, nextitem=nextitem)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 137, in runtestprotocol
    reports.append(call_and_report(item, "call", log))
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 244, in call_and_report
    call = CallInfo.from_call(
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 353, in from_call
    result: TResult | None = func()
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 245, in <lambda>
    lambda: runtest_hook(item=item, **kwds),
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 179, in pytest_runtest_call
    item.runtest()
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/python.py", line 1720, in runtest
    self.ihook.pytest_pyfunc_call(pyfuncitem=self)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/python.py", line 166, in pytest_pyfunc_call
    result = testfunction(**testargs)
  File "/Users/adh/Documents/git/vultron_pub/test/test_behavior_dispatcher.py", line 71, in test_local_dispatcher_dispatch_logs_payload
    dispatcher.dispatch(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/behavior_dispatcher.py", line 64, in dispatch
    self._handle(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/behavior_dispatcher.py", line 73, in _handle
    handler(dispatchable=dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/api/v2/backend/handlers.py", line 43, in wrapper
    return func(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/api/v2/backend/handlers.py", line 77, in create_report
    logger.info(
Message: "Actor '%s' creates VulnerabilityReport '%s' (ID: %s)"
Arguments: ('https://example.org/users/tester', 'TEST-REPORT-001', '4bb5b86a-ddee-4497-ba20-2a919e4c7691')
--- Logging error ---
Traceback (most recent call last):
  File "/Users/adh/.local/share/uv/python/cpython-3.13.7-macos-x86_64-none/lib/python3.13/logging/__init__.py", line 1154, in emit
    stream.write(msg + self.terminator)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I/O operation on closed file.
Call stack:
  File "/Users/adh/Applications/PyCharm.app/Contents/plugins/python-ce/helpers/pycharm/_jb_pytest_runner.py", line 84, in <module>
    sys.exit(pytest.main(args, plugins_to_load + [Plugin]))
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 199, in main
    ret: ExitCode | int = config.hook.pytest_cmdline_main(config=config)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 318, in wrap_session
    session.exitstatus = doit(config, session) or 0
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 372, in _main
    config.hook.pytest_runtestloop(session=session)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 396, in pytest_runtestloop
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 118, in pytest_runtest_protocol
    runtestprotocol(item, nextitem=nextitem)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 137, in runtestprotocol
    reports.append(call_and_report(item, "call", log))
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 244, in call_and_report
    call = CallInfo.from_call(
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 353, in from_call
    result: TResult | None = func()
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 245, in <lambda>
    lambda: runtest_hook(item=item, **kwds),
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 179, in pytest_runtest_call
    item.runtest()
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/python.py", line 1720, in runtest
    self.ihook.pytest_pyfunc_call(pyfuncitem=self)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/python.py", line 166, in pytest_pyfunc_call
    result = testfunction(**testargs)
  File "/Users/adh/Documents/git/vultron_pub/test/test_behavior_dispatcher.py", line 71, in test_local_dispatcher_dispatch_logs_payload
    dispatcher.dispatch(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/behavior_dispatcher.py", line 64, in dispatch
    self._handle(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/behavior_dispatcher.py", line 73, in _handle
    handler(dispatchable=dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/api/v2/backend/handlers.py", line 43, in wrapper
    return func(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/api/v2/backend/handlers.py", line 90, in create_report
    logger.info(
Message: 'Stored VulnerabilityReport with ID: %s'
Arguments: ('4bb5b86a-ddee-4497-ba20-2a919e4c7691',)
--- Logging error ---
Traceback (most recent call last):
  File "/Users/adh/.local/share/uv/python/cpython-3.13.7-macos-x86_64-none/lib/python3.13/logging/__init__.py", line 1154, in emit
    stream.write(msg + self.terminator)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I/O operation on closed file.
Call stack:
  File "/Users/adh/Applications/PyCharm.app/Contents/plugins/python-ce/helpers/pycharm/_jb_pytest_runner.py", line 84, in <module>
    sys.exit(pytest.main(args, plugins_to_load + [Plugin]))
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/config/__init__.py", line 199, in main
    ret: ExitCode | int = config.hook.pytest_cmdline_main(config=config)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 365, in pytest_cmdline_main
    return wrap_session(config, _main)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 318, in wrap_session
    session.exitstatus = doit(config, session) or 0
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 372, in _main
    config.hook.pytest_runtestloop(session=session)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/main.py", line 396, in pytest_runtestloop
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 118, in pytest_runtest_protocol
    runtestprotocol(item, nextitem=nextitem)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 137, in runtestprotocol
    reports.append(call_and_report(item, "call", log))
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 244, in call_and_report
    call = CallInfo.from_call(
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 353, in from_call
    result: TResult | None = func()
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 245, in <lambda>
    lambda: runtest_hook(item=item, **kwds),
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/runner.py", line 179, in pytest_runtest_call
    item.runtest()
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/python.py", line 1720, in runtest
    self.ihook.pytest_pyfunc_call(pyfuncitem=self)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/_pytest/python.py", line 166, in pytest_pyfunc_call
    result = testfunction(**testargs)
  File "/Users/adh/Documents/git/vultron_pub/test/test_behavior_dispatcher.py", line 71, in test_local_dispatcher_dispatch_logs_payload
    dispatcher.dispatch(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/behavior_dispatcher.py", line 64, in dispatch
    self._handle(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/behavior_dispatcher.py", line 73, in _handle
    handler(dispatchable=dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/api/v2/backend/handlers.py", line 43, in wrapper
    return func(dispatchable)
  File "/Users/adh/Documents/git/vultron_pub/vultron/api/v2/backend/handlers.py", line 101, in create_report
    logger.info("Stored CreateReport activity with ID: %s", activity.as_id)
Message: 'Stored CreateReport activity with ID: %s'
Arguments: ('act-xyz',)
```


### Older tests have spurious print statements

When running the test suite, there are some tests that print output either 
to stdout or stderr. This is not ideal, as it clutters the test output and 
makes it harder to see the actual test results. These print statements 
should be removed or replaced with proper debug logging that could be 
enabled when desired.

