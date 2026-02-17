# Code Style Specifications

## Overview

Defines code formatting and import organization standards for Python code.

**Source**: .pre-commit-config.yaml, copilot-instructions.md, ADR-0006  
**Note**: Applies to all Python source files and documentation code blocks

---

## Code Formatting (MUST)

- `CS-01-001` Code SHALL be formatted using Black with default settings
- `CS-01-002` Formatting checks SHALL be included in CI/CD pipeline
- `CS-01-003` Pre-commit hooks SHALL enforce code formatting standards

- Methods SHOULD have docstrings following PEP 257 conventions
  - Docstrings SHOULD follow Google style consistently (Args, Returns, Raises sections) when informative
    - Empty Google docstrings sections (Args, Returns, Raises) SHOULD be omitted for clarity
  - Small methods where the purpose is clear from the name MAY omit or use one-line docstrings for brevity
- Use type hints for function signatures and variable annotations where appropriate
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
- `CS-05-002` When unavoidable dependencies exist, use lazy initialization patterns
  - Import inside functions rather than at module level
  - Use caching to avoid repeated initialization overhead
- `CS-05-003` Shared types and errors SHALL be placed in neutral modules
  - Example: `types.py` for shared type definitions, `dispatcher_errors.py` for dispatcher errors
- `CS-05-004` Before adding imports between modules, trace the import chain to prevent cycles

**Verification**: Run `python -c "import vultron.MODULE_NAME"` to detect circular imports early

## Import Practices (MAY)

- `CS-04-001` Relative imports MAY be used for local application imports when appropriate
- `CS-04-002` Module imports MAY use aliases for clarity or to avoid naming conflicts
  - Aliases SHOULD be descriptive and widely recognized (e.g., `import numpy as np`)

