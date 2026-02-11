"""
Type helpers for ActivityPub objects and activities.
Allow for easier type hinting in other modules by providing TypeVars
that are bound to the base as_Activity and as_Object classes to make
subclass type hints easier.
"""

from typing import TypeVar

from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.base import as_Object

AsActivityType = TypeVar("AsActivityType", bound=as_Activity)
AsObjectType = TypeVar("AsObjectType", bound=as_Object)
