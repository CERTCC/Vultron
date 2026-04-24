"""Shared type aliases for the vultron.metadata tooling layer."""

from typing import Annotated

from pydantic import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
NonEmptyStrList = list[NonEmptyStr]
