# Code Style Specifications

## Overview

Defines code formatting and import organization standards for Python code.

**Source**: .pre-commit-config.yaml, copilot-instructions.md, ADR-0006  
**Note**: Applies to all Python source files and documentation code blocks

---

## Code Formatting (MUST)

- `CS-01-001` Code MUST follow PEP 8 style guidelines
  - **Implementation**: Black formatter (or equivalent) SHOULD be used for
    consistency
  - **Settings**: Default Black settings (88 character line length, etc.)
- `CS-01-002` Formatting checks MUST be included in CI/CD pipeline
  - Builds MUST fail if code does not conform to style guidelines
- `CS-01-003` Code formatting MUST be enforced
  - **Implementation options**: Pre-commit hooks, CI pipeline checks, IDE
    integration
  - **Current implementation**: Pre-commit hooks with Black formatter

## Docstring Standards (SHOULD)

- `CS-01-004` Functions and methods SHOULD have docstrings following PEP 257
  conventions
  - Public APIs MUST have docstrings
  - Internal utilities MAY use brief one-line docstrings when purpose is clear
    from name
- `CS-01-005` Docstrings SHOULD follow Google style for structured sections
  - Include `Args`, `Returns`, `Raises` sections when informative
  - Omit empty sections for brevity
  
**Examples**:

```python
# Public API - comprehensive docstring
def validate_report(dispatchable: DispatchActivity) -> None:
    """Validate vulnerability report and create case on acceptance.
    
    Args:
        dispatchable: Activity dispatch wrapper containing report offer
        
    Raises:
        VultronApiError: If report validation fails
        DataLayerError: If case creation fails
        
    Side Effects:
        - Updates report status to VALID or INVALID
        - Creates VulnerabilityCase on validation success
        - Adds CreateCase activity to actor outbox
    """
    ...

# Simple utility - brief docstring
def extract_id_segment(url: str) -> str:
    """Extract last path segment from URL for blackboard key."""
    return url.split('/')[-1]
```

- Use type hints for function signatures and variable annotations where
  appropriate
- Use descriptive variable and function names for readability

## Import Organization (SHOULD)

- `CS-02-001` Imports SHOULD be organized in three groups: standard library, third-party libraries, local application
  - Each group separated by a single blank line
  - Within each group, imports sorted alphabetically
- `CS-02-002` Import statements SHOULD be placed at the top of the file after module comments or docstrings
- `CS-02-003` Multi-line import statements SHOULD use parentheses for readability

## Import Practices (MUST)

- `CS-03-001` Wildcard imports (e.g., `from module import *`) MUST NOT be used
- `CS-03-002` Unused imports MUST be removed
- `CS-03-003` When importing more than 10 items from a module, import the module itself instead
  - Access attributes as `module.attribute` for maintainability
  - **Rationale**: Reduces line noise and makes module boundaries clearer
- `CS-03-004` In test modules, avoid multiple imports from the module under test; consider importing the module and using attribute access for clarity.
  - Shorthand aliases are acceptable in test modules where the context is clear (e.g., `import my_module as mm` in `test_my_module.py`)

## Circular Import Prevention (MUST)

- `CS-05-001` Core modules SHALL NOT import from application layer modules
  - Core modules: `behavior_dispatcher.py`, `semantic_map.py`, `semantic_handler_map.py`, `activity_patterns.py`
  - Application layer: `api/v2/*`
- `CS-05-002` When circular dependencies cannot be resolved by reorganization,
  use lazy initialization patterns as a **last resort**
  - Prefer module-level imports; local imports are a code smell indicating a
    circular dependency that SHOULD be refactored
  - Import inside functions only when refactoring is not possible or practical
  - When encountering existing local imports, attempt to refactor them to
    module-level before accepting them as-is
  - Use caching to avoid repeated initialization overhead
- `CS-05-003` Shared types and errors SHALL be placed in neutral modules
  - Example: `types.py` for shared type definitions, `dispatcher_errors.py` for dispatcher errors
- `CS-05-004` Before adding imports between modules, trace the import chain to prevent cycles

**Verification**: Run `python -c "import vultron.MODULE_NAME"` to detect circular imports early

## Import Practices (MAY)

- `CS-04-001` Relative imports MAY be used for local application imports when appropriate
- `CS-04-002` Module imports MAY use aliases for clarity or to avoid naming conflicts
  - Aliases SHOULD be descriptive and widely recognized (e.g., `import numpy as np`)

## Module Size (SHOULD)

- `CS-06-001` Prefer modules that are < ~400 lines; split large modules by
  responsibility and avoid single-file catchalls
  - E.g., separate handlers registry, handler implementations, and handler
    utilities into distinct modules

## `as_` Field Prefix Policy (SHOULD)

- `CS-07-001` Use `as_` prefix on Pydantic fields only when the plain name
  would collide with a Python reserved word
  - Use `as_object` instead of `object` (reserved keyword)
  - Otherwise use plain field names: `actor`, not `as_actor`
