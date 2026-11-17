"""Tests for the per-app config scope in ``vultron/config/app.py`` (ADR-0206).

Inside an app's scope ``get_config()`` and ``load_actor_config()`` return the
app's own config; an app with none reads the process-wide cache; and while an
app holding its own config runs, a read in no app scope raises
``VultronWiringError`` instead of falling back to the process-wide config.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import contextvars
import threading
from collections.abc import Callable

import pytest

from test.support.app_configs import (
    held_app_configs,
    own_app_config,
    release_leaked_app_config_holds,
)
from vultron.config import (
    AppConfig,
    app as app_config_module,
    app_config_scope,
    config_override,
    get_config,
    holding_app_config,
    load_actor_config,
    reload_config,
)
from vultron.config.actor import ActorConfig
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError


def _own_config(retries: int) -> AppConfig:
    return own_app_config(
        max_inbox_retry_attempts=retries,
        actor=ActorConfig(default_case_roles=[CVDRole.VENDOR]),
    )


def test_scope_returns_the_apps_own_config() -> None:
    own = _own_config(7)
    with app_config_scope(own):
        assert get_config() is own
        assert load_actor_config() is own.actor


def test_scope_without_config_reads_the_process_wide_config() -> None:
    process_wide = get_config()
    with app_config_scope(None):
        assert get_config() is process_wide


def test_no_scope_reads_the_process_wide_cache_as_before() -> None:
    assert get_config() is get_config()
    assert load_actor_config() is get_config().actor


def test_nested_scopes_restore_the_outer_scope_on_exit() -> None:
    outer, inner = _own_config(3), _own_config(4)
    with app_config_scope(outer):
        with app_config_scope(inner):
            assert get_config() is inner
        assert get_config() is outer


def test_scope_is_restored_when_the_body_raises() -> None:
    process_wide = get_config()
    with pytest.raises(RuntimeError):
        with app_config_scope(_own_config(3)):
            raise RuntimeError("boom")
    assert get_config() is process_wide


def _in_no_scope[T](read: Callable[[], T]) -> T:
    """Call *read* in a fresh context, where no app scope is entered."""
    return contextvars.Context().run(read)


def test_read_in_no_scope_while_an_app_holds_its_config_raises() -> None:
    """AC-3: a path that lost its app's config never gets the process one."""
    with holding_app_config(_own_config(5)):
        with pytest.raises(VultronWiringError, match="ADR-0206"):
            _in_no_scope(get_config)
        with pytest.raises(VultronWiringError):
            _in_no_scope(load_actor_config)


def test_thread_started_without_the_scope_raises_while_held() -> None:
    """A thread does not inherit the scope; it raises rather than fall back."""
    seen: list[BaseException | AppConfig] = []

    def _read() -> None:
        try:
            seen.append(get_config())
        except VultronWiringError as exc:
            seen.append(exc)

    with holding_app_config(_own_config(5)):
        worker = threading.Thread(target=_read)
        worker.start()
        worker.join()

    assert len(seen) == 1
    assert isinstance(seen[0], VultronWiringError)


def test_thread_run_in_a_copied_context_reads_the_apps_config() -> None:
    """The propagation a later path uses: copy the context into the thread."""
    own = _own_config(5)
    seen: list[AppConfig] = []

    with holding_app_config(own):
        context = contextvars.copy_context()
        worker = threading.Thread(
            target=context.run, args=(lambda: seen.append(get_config()),)
        )
        worker.start()
        worker.join()

    assert seen == [own]


def test_app_without_config_still_reads_process_wide_while_another_holds() -> (
    None
):
    own = _own_config(5)
    process_wide = reload_config()
    with holding_app_config(own):
        with app_config_scope(None):
            assert get_config() is process_wide


def test_release_ends_the_refusal_even_when_the_body_raises() -> None:
    with pytest.raises(RuntimeError):
        with holding_app_config(_own_config(5)):
            raise RuntimeError("boom")
    # No app holds its config now, so a read in no scope is the cache again.
    assert get_config() is get_config()


def test_refusal_lasts_while_any_held_app_runs() -> None:
    with holding_app_config(_own_config(5)):
        with holding_app_config(_own_config(6)):
            pass
        with pytest.raises(VultronWiringError):
            _in_no_scope(get_config)
    assert isinstance(get_config(), AppConfig)


def test_process_wide_reload_and_override_work_while_an_app_holds() -> None:
    """``reload_config`` / ``config_override`` are process-wide on purpose."""
    with holding_app_config(_own_config(5)):
        assert isinstance(reload_config(), AppConfig)
        with config_override(VULTRON_MAX_INBOX_RETRY_ATTEMPTS="9") as cfg:
            assert cfg.max_inbox_retry_attempts == 9
        # The app's own config is untouched by the process-wide override.
        assert get_config().max_inbox_retry_attempts == 5


def test_leak_guard_puts_back_a_hold_the_test_left_running() -> None:
    """The autouse guard's helper undoes a hold a test never released."""
    before = held_app_configs()
    # The hold a TestClient left open leaves: recorded, never released.
    app_config_module._HELD_APP_CONFIGS.hold()
    with pytest.raises(VultronWiringError):
        _in_no_scope(get_config)

    assert release_leaked_app_config_holds(before) == 1
    assert held_app_configs() == before
    assert _in_no_scope(get_config) is get_config()


def test_leak_guard_reports_none_when_every_hold_was_released() -> None:
    before = held_app_configs()
    with holding_app_config(_own_config(5)):
        pass
    assert release_leaked_app_config_holds(before) == 0


def test_a_released_hold_that_later_exits_leaves_no_refusal() -> None:
    """The guard's release, then the app's own exit, releases it once.

    A holder the guard reports and releases (a module-scoped app first
    started by ``getfixturevalue``, or a leaked client closed later) still
    exits its lifespan afterwards.  That exit must not take off a second
    hold, or the refusal would stay on with no app running.
    """
    before = held_app_configs()
    with holding_app_config(_own_config(5)):
        assert release_leaked_app_config_holds(before) == 1
    assert held_app_configs() == before
    assert release_leaked_app_config_holds(before) == 0
    assert _in_no_scope(get_config) is get_config()
