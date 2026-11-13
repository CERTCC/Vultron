#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The VINCE API credential is read only from the environment and never shown.

Per specs/vince-shadow-data.yaml VSD-01-004, VSD-01-005 and
specs/case-shadow.yaml SHD-02-003 (#5960).  The VINCE connector (#5963) reads
its credential through :meth:`VinceConfig.require_api_token`, so these tests
pin the refusal it relies on.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel, SecretStr, ValidationError

from vultron.config import AppConfig, VinceConfig, clear_config_cache
from vultron.config.app import config_override, get_config
from vultron.config.secrets import (
    is_secret_annotation,
    refuse_secrets_in_file,
    secret_setting_paths,
)
from vultron.config.vince import VINCE_API_TOKEN_ENV_VAR
from vultron.errors import (
    VultronConfigError,
    VultronMissingCredentialError,
    VultronSecretInConfigFileError,
)

#: A marker credential: any appearance of it in output is a leak.
MARKER = "marker-vince-credential-5960"

TOKEN_VAR = VINCE_API_TOKEN_ENV_VAR


@pytest.fixture(autouse=True)
def clean_vince_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Run each test with no VINCE settings, no config file and no cache.

    A developer's shell or the devcontainer can carry real VINCE variables
    (#5957), so they are removed rather than assumed absent (CFG-06-003).
    """
    monkeypatch.chdir(tmp_path)
    for var in (
        "VULTRON_CONFIG",
        "VULTRON_VINCE",
        TOKEN_VAR,
        "VULTRON_VINCE__BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    clear_config_cache()
    yield
    clear_config_cache()


def _write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "vince-config.yaml"
    path.write_text(text)
    return path


# ---------------------------------------------------------------------------
# AC-1: the credential is read from VULTRON_VINCE__API_TOKEN, and a case read
# is refused without it (VSD-01-004, SHD-02-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("VSD-01-004")
@pytest.mark.spec("SHD-02-003")
def test_credential_is_read_from_the_environment_variable() -> None:
    with config_override(**{TOKEN_VAR: MARKER}) as cfg:
        token = cfg.vince.require_api_token()
    assert isinstance(token, SecretStr)
    assert token.get_secret_value() == MARKER


@pytest.mark.spec("VSD-01-004")
@pytest.mark.spec("SHD-02-003")
def test_case_read_is_refused_without_the_credential() -> None:
    with pytest.raises(VultronMissingCredentialError) as excinfo:
        get_config().vince.require_api_token()
    assert TOKEN_VAR in str(excinfo.value)


@pytest.mark.spec("VSD-01-004")
def test_no_credential_is_the_default() -> None:
    assert AppConfig().vince.api_token is None
    assert VinceConfig().api_token is None


@pytest.mark.spec("VSD-01-004")
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_credential_is_refused_at_load(
    monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    monkeypatch.setenv(TOKEN_VAR, blank)
    with pytest.raises(ValidationError, match=TOKEN_VAR):
        AppConfig()


@pytest.mark.spec("VSD-01-004")
@pytest.mark.parametrize(
    "source", [".env", "secrets/vince__api_token", "vince__api_token"]
)
def test_credential_is_not_read_from_a_dotenv_or_secrets_file(
    tmp_path: Path, source: str
) -> None:
    """Only the process environment is a source: no `.env`, no secrets dir."""
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"{TOKEN_VAR}={MARKER}\n" if source == ".env" else MARKER
    path.write_text(body)
    assert AppConfig().vince.api_token is None


def test_base_url_is_read_from_environment_and_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _write_config(
        tmp_path, "vince:\n  base_url: https://file.example/api\n"
    )
    monkeypatch.setenv("VULTRON_CONFIG", str(config))
    assert AppConfig().vince.base_url == "https://file.example/api"
    monkeypatch.setenv("VULTRON_VINCE__BASE_URL", "https://env.example/api")
    monkeypatch.setenv(TOKEN_VAR, MARKER)
    cfg = AppConfig()
    assert cfg.vince.base_url == "https://env.example/api"
    assert cfg.vince.require_api_token().get_secret_value() == MARKER


@pytest.mark.parametrize("url", ["ftp://vince.example", "vince.example"])
def test_base_url_without_http_scheme_is_refused(url: str) -> None:
    with pytest.raises(ValidationError, match="http:// or https://"):
        VinceConfig(base_url=url)


# ---------------------------------------------------------------------------
# AC-2: a config file carrying the credential is refused at load, and the
# error does not echo the value (VSD-01-004, VSD-01-005)
# ---------------------------------------------------------------------------


@pytest.mark.spec("VSD-01-004")
@pytest.mark.spec("VSD-01-005")
@pytest.mark.parametrize(
    "text",
    [
        f"vince:\n  api_token: {MARKER}\n",
        f"vince:\n  API_TOKEN: {MARKER}\n",
        f"Vince:\n  Api_Token: {MARKER}\n",
        f"vince:\n  base_url: https://vince.example\n  api_token: {MARKER}\n",
        "vince:\n  api_token: null\n",
        'vince:\n  api_token: ""\n',
        "vince:\n  base_url: https://vince.example\n"
        f"VINCE:\n  api_token: {MARKER}\n",
    ],
    ids=[
        "value",
        "upper-key",
        "mixed-case",
        "beside-url",
        "null",
        "empty",
        "second-section-spelling",
    ],
)
def test_config_file_naming_the_credential_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str
) -> None:
    config = _write_config(tmp_path, text)
    monkeypatch.setenv("VULTRON_CONFIG", str(config))
    with pytest.raises(VultronSecretInConfigFileError) as excinfo:
        AppConfig()
    message = str(excinfo.value)
    assert MARKER not in message
    assert "vince.api_token" in message
    assert TOKEN_VAR in message
    assert str(config) in message


@pytest.mark.spec("VSD-01-004")
def test_file_is_refused_even_when_the_environment_also_sets_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The environment outranks the file, but never excuses a secret in it."""
    config = _write_config(tmp_path, f"vince:\n  api_token: {MARKER}\n")
    monkeypatch.setenv("VULTRON_CONFIG", str(config))
    monkeypatch.setenv(TOKEN_VAR, "another-credential")
    with pytest.raises(VultronSecretInConfigFileError):
        AppConfig()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "vince: null\n",
        "vince: {}\n",
        "server:\n  api_token: x\n",
        "vince:\n  - api_token\n",
        "vince:\n  1: x\n",
    ],
    ids=[
        "empty",
        "null-section",
        "empty-section",
        "other-section",
        "list-section",
        "non-string-key",
    ],
)
def test_file_without_the_credential_key_is_not_refused_for_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str
) -> None:
    """Only the secret's own key path is refused; other shapes load or fail
    on their own terms."""
    config = _write_config(tmp_path, text)
    monkeypatch.setenv("VULTRON_CONFIG", str(config))
    try:
        AppConfig()
    except VultronSecretInConfigFileError:  # pragma: no cover - the failure
        pytest.fail(f"refused a file that names no secret: {text!r}")
    except ValidationError:
        pass  # a malformed file fails validation, which is not this rule


class _Secrets(BaseModel):
    """A model with a required and an optional secret, and a plain field."""

    required: SecretStr
    optional: SecretStr | None = None
    plain: str = "x"


def test_secret_is_found_by_type_whether_optional_or_not(
    tmp_path: Path,
) -> None:
    assert is_secret_annotation(SecretStr)
    assert is_secret_annotation(SecretStr | None)
    assert not is_secret_annotation(str | None)
    assert secret_setting_paths(_Secrets) == (("required",), ("optional",))
    with pytest.raises(VultronSecretInConfigFileError) as excinfo:
        refuse_secrets_in_file(
            {"required": MARKER, "OPTIONAL": None, "plain": "y"},
            _Secrets,
            tmp_path / "f.yaml",
        )
    message = str(excinfo.value)
    assert "required (set VULTRON_REQUIRED instead)" in message
    assert "optional (set VULTRON_OPTIONAL instead)" in message
    assert MARKER not in message


class _Section(BaseModel):
    """A section holding a secret."""

    token: SecretStr | None = None


class _ListOfSecrets(BaseModel):
    tokens: list[SecretStr] = []


class _DictOfSecrets(BaseModel):
    tokens: dict[str, SecretStr] = {}


class _SecretOrInt(BaseModel):
    token: SecretStr | int | None = None


class _OptionalSecretSection(BaseModel):
    section: _Section | None = None


@pytest.mark.spec("VSD-01-004")
@pytest.mark.parametrize(
    "model",
    [_ListOfSecrets, _DictOfSecrets, _SecretOrInt, _OptionalSecretSection],
    ids=["list", "dict", "union-with-other", "optional-section"],
)
def test_secret_in_a_shape_with_no_key_path_is_refused(
    model: type[BaseModel],
) -> None:
    """The finder fails closed: a secret it cannot refuse is a declaration
    error, never a setting silently left out of the file refusal."""
    with pytest.raises(VultronConfigError, match="SecretStr"):
        secret_setting_paths(model)


def test_the_credential_is_the_only_secret_setting() -> None:
    """The field's type is the one declaration that makes a setting secret."""
    assert secret_setting_paths(AppConfig) == (("vince", "api_token"),)
    assert TOKEN_VAR == "VULTRON_VINCE__API_TOKEN"  # noqa: S105 - a name


# ---------------------------------------------------------------------------
# AC-3: the credential appears in no log record, exception message or repr
# during a run (VSD-01-005)
# ---------------------------------------------------------------------------


def _load_failure(monkeypatch: pytest.MonkeyPatch, path: Path) -> str:
    monkeypatch.setenv("VULTRON_CONFIG", str(path))
    try:
        AppConfig()
    except (ValidationError, VultronSecretInConfigFileError) as exc:
        return f"{exc!s}\n{exc!r}"
    finally:
        monkeypatch.delenv("VULTRON_CONFIG")
    pytest.fail(f"{path} loaded, but it was written to fail")


@pytest.mark.spec("VSD-01-005")
def test_marker_credential_appears_in_no_log_error_or_repr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    rendered: list[str] = []

    # A loaded configuration, rendered every way it can be shown.
    monkeypatch.setenv(TOKEN_VAR, MARKER)
    monkeypatch.setenv("VULTRON_VINCE__BASE_URL", "https://vince.example")
    with config_override() as cfg:
        logging.getLogger("vultron.test").info("config %s", cfg)
        logging.getLogger("vultron.test").debug("vince %r", cfg.vince)
        token = cfg.vince.require_api_token()
        rendered += [
            repr(cfg),
            str(cfg),
            repr(cfg.vince),
            str(cfg.vince),
            repr(token),
            str(token),
            cfg.model_dump_json(),
            str(cfg.model_dump()),
            f"{token}",
        ]

    monkeypatch.delenv("VULTRON_VINCE__BASE_URL")
    monkeypatch.delenv(TOKEN_VAR)

    # A credential of the wrong type, whose input holds the marker: from the
    # environment through AppConfig, and given to the section on its own.
    monkeypatch.setenv(
        "VULTRON_VINCE", f'{{"api_token": {{"v": "{MARKER}"}}}}'
    )
    with pytest.raises(ValidationError) as wrong_type:
        AppConfig()
    rendered += [str(wrong_type.value), repr(wrong_type.value)]
    monkeypatch.delenv("VULTRON_VINCE")
    with pytest.raises(ValidationError) as standalone:
        VinceConfig.model_validate({"api_token": {"v": MARKER}})
    rendered += [str(standalone.value), repr(standalone.value)]

    # A file that carries the credential, as a key and as the whole section.
    rendered.append(
        _load_failure(
            monkeypatch,
            _write_config(tmp_path, f"vince:\n  api_token: {MARKER}\n"),
        )
    )
    rendered.append(
        _load_failure(
            monkeypatch, _write_config(tmp_path, f"vince: {MARKER}\n")
        )
    )

    # The refusal a case read gets with no credential.
    with pytest.raises(VultronMissingCredentialError) as missing:
        AppConfig().vince.require_api_token()
    rendered.append(str(missing.value))

    leaks = [text for text in rendered if MARKER in text]
    leaks += [
        r.getMessage() for r in caplog.records if MARKER in r.getMessage()
    ]
    assert MARKER not in caplog.text
    assert not leaks
