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

"""Secret settings: which they are, and refusing a file that names one.

A configuration setting typed :class:`pydantic.SecretStr` (or
``SecretStr | None``) is a secret.  A secret is read only from the environment
the node runs in, never from a configuration file, because configuration files
live in the repository and a secret written there has a path into a commit
(VSD-01-004, SHD-02-003).  The type is the one declaration:
:func:`secret_setting_paths` finds every secret by it, the YAML source refuses
a file that names one, and the configuration reference page leaves secrets out
of its example file.

The finder fails closed.  A ``SecretStr`` anywhere else in a field's type,
inside a list, a dict, or an optional section, has no single key path to
refuse, so it is refused as a declaration instead of being missed.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, get_args

from pydantic import BaseModel, SecretStr

from vultron.config.env_names import env_var_name
from vultron.config.model_walk import (
    annotation_members,
    iter_leaf_fields,
    section_model,
)
from vultron.errors import VultronConfigError, VultronSecretInConfigFileError


def _is_secret_type(member: Any) -> bool:
    return isinstance(member, type) and issubclass(member, SecretStr)


def is_secret_annotation(annotation: Any) -> bool:
    """Return whether a field typed *annotation* holds a secret directly.

    ``SecretStr`` and ``SecretStr | None`` do; a ``SecretStr`` nested in a
    container does not count here, and :func:`secret_setting_paths` refuses
    it.
    """
    return any(_is_secret_type(m) for m in annotation_members(annotation))


def _contains_secret(annotation: Any, seen: set[type[BaseModel]]) -> bool:
    """Return whether *annotation* holds a ``SecretStr`` at any depth."""
    if _is_secret_type(annotation):
        return True
    model = section_model(annotation)
    if model is not None:
        if model in seen:
            return False
        seen.add(model)
        return any(
            _contains_secret(f.annotation, seen)
            for f in model.model_fields.values()
        )
    return any(
        _contains_secret(arg, seen)
        for arg in (*annotation_members(annotation), *get_args(annotation))
        if arg is not annotation
    )


def secret_setting_paths(
    model: type[BaseModel],
) -> tuple[tuple[str, ...], ...]:
    """Return the key path of every secret setting under *model*.

    A field whose type is itself a model is a section, searched in turn, so
    ``("vince", "api_token")`` names ``AppConfig.vince.api_token``.

    Raises:
        VultronConfigError: A field holds a ``SecretStr`` in a shape with no
            single key path, such as ``list[SecretStr]`` or an optional
            section that contains a secret; the file refusal could not see
            it, so the declaration is refused rather than missed.
    """
    paths: list[tuple[str, ...]] = []
    for path, _owner, _name, field in iter_leaf_fields(model):
        if is_secret_annotation(field.annotation):
            secret_free = [
                m
                for m in annotation_members(field.annotation)
                if not _is_secret_type(m) and m is not type(None)
            ]
            if not secret_free:
                paths.append(path)
                continue
        if _contains_secret(field.annotation, set()):
            raise VultronConfigError(
                f"setting {'.'.join(path)} holds a SecretStr in a shape the"
                " secret-setting rule cannot refuse in a file; declare the"
                " secret as SecretStr or SecretStr | None in a required"
                " section"
            )
    return tuple(paths)


def _matching_values(node: Mapping[Any, Any], key: str) -> list[object]:
    """Return the value of every key of *node* that names *key*, in any case.

    YAML keys are matched case-sensitively when the file is loaded, so a key
    spelled ``API_TOKEN`` is not read.  The refusal still matches every
    spelling, and every section so spelled, because a secret written under
    any of them is a secret in a committed file.
    """
    return [
        value
        for candidate, value in node.items()
        if isinstance(candidate, str) and candidate.lower() == key.lower()
    ]


def _names_path(node: object, path: tuple[str, ...]) -> bool:
    """Return whether file *node* holds a key at every step of *path*."""
    if not path:
        return True
    if not isinstance(node, Mapping):
        return False
    head, rest = path[0], path[1:]
    return any(_names_path(v, rest) for v in _matching_values(node, head))


def refuse_secrets_in_file(
    data: object, model: type[BaseModel], source: Path
) -> None:
    """Refuse configuration file *data* when it names any secret setting.

    The file is refused whatever value the key holds, ``null`` included, so a
    placeholder never becomes the place a real value is pasted.  The message
    names the file, the key and the variable to use instead, never the value
    (VSD-01-005).

    Raises:
        VultronSecretInConfigFileError: *data* names a secret setting of
            *model*; the message lists every one it names.
    """
    found = [
        path for path in secret_setting_paths(model) if _names_path(data, path)
    ]
    if found:
        keys = ", ".join(
            f"{'.'.join(path)} (set {env_var_name(path)} instead)"
            for path in found
        )
        raise VultronSecretInConfigFileError(
            f"configuration file {source} names a secret setting, which is"
            f" read only from the environment: {keys}; remove the key from"
            " the file"
        )
