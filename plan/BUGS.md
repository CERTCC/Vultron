# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

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

### ~~mkdocs serve error~~ FIXED (2026-02-26)

**Fixed**: Removed `griffe>=2.0.0` and `griffecli>=2.0.0` from
`pyproject.toml`. The stub `griffe` 2.0.0 package conflicted with
`griffelib` 2.0.0 (the real library), causing `griffe/__init__.py` to be
absent from the venv after `uv sync`. Keeping only `griffelib>=2.0.0` (which
`mkdocstrings-python` also requires directly) eliminates the conflict.

### ~~mkdocs serve error (original report)~~

When attempting to run `uv run mkdocs serve` to serve the documentation 
locally, the following error occurred. 

```shell
INFO    -  Building documentation...
INFO    -  Loading data from bib files: ['/Users/adh/Documents/git/vultron_pub/references.bib']
Traceback (most recent call last):
  File "/Users/adh/Documents/git/vultron_pub/.venv/bin/mkdocs", line 10, in <module>
    sys.exit(cli())
             ~~~^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/click/core.py", line 1485, in __call__
    return self.main(*args, **kwargs)
           ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/click/core.py", line 1406, in main
    rv = self.invoke(ctx)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/click/core.py", line 1873, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/click/core.py", line 1269, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/click/core.py", line 824, in invoke
    return callback(*args, **kwargs)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocs/__main__.py", line 272, in serve_command
    serve.serve(**kwargs)
    ~~~~~~~~~~~^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocs/commands/serve.py", line 85, in serve
    builder(config)
    ~~~~~~~^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocs/commands/serve.py", line 67, in builder
    build(config, serve_url=None if is_clean else serve_url, dirty=is_dirty)
    ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocs/commands/build.py", line 265, in build
    config = config.plugins.on_config(config)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocs/plugins.py", line 587, in on_config
    return self.run_event('config', config)
           ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocs/plugins.py", line 566, in run_event
    result = method(item, **kwargs)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocstrings/_internal/plugin.py", line 153, in on_config
    handlers._download_inventories()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocstrings/_internal/handlers/base.py", line 602, in _download_inventories
    handler = self.get_handler(handler_name)
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocstrings/_internal/handlers/base.py", line 581, in get_handler
    module = importlib.import_module(f"mkdocstrings_handlers.{name}")
  File "/Users/adh/.local/share/uv/python/cpython-3.13.7-macos-x86_64-none/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocstrings_handlers/python/__init__.py", line 3, in <module>
    from mkdocstrings_handlers.python._internal.config import (
    ...<11 lines>...
    )
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocstrings_handlers/python/_internal/config.py", line 12, in <module>
    from mkdocstrings_handlers.python._internal.rendering import Order  # noqa: TC001
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/adh/Documents/git/vultron_pub/.venv/lib/python3.13/site-packages/mkdocstrings_handlers/python/_internal/rendering.py", line 17, in <module>
    from griffe import (
    ...<15 lines>...
    )
ImportError: cannot import name 'Alias' from 'griffe' (unknown location)
```