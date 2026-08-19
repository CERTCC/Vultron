---
title: pydantic model_fields not populated during __init_subclass__
type: learning
timestamp: 2026-08-19T00:00:00Z
source: ISSUE-1992
signal: design-question
---

When a Pydantic v2 model class is being defined, `__init_subclass__` fires
during Python's class-creation machinery — before Pydantic's metaclass
`__new__` has finished processing the new class. As a result,
`cls.model_fields` at that moment still reflects the *parent* class's fields,
not the child's.

**What this means in practice:** any `__init_subclass__` hook that tries to
read `cls.model_fields.get("type_").default` to extract a Literal default will
silently get the parent's value (usually `None`), not the child's.

**Fix applied in #1992:** extract the Literal value directly from the type
annotation using `typing.get_args(annotation)` instead of relying on
`model_fields`. The annotation IS available in `__init_subclass__` via
`typing.get_type_hints(cls)`.

```python
literal_args = _typing.get_args(annotation)
if literal_args and len(literal_args) == 1 and isinstance(literal_args[0], str):
    CORE_TYPE_MAP[literal_args[0]] = cls
```
