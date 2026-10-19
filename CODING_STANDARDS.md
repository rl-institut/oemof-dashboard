# Coding Standards (Python)

- Use Python 3.12+
- Dependencies managed with uv (`pyproject.toml`)
- Use ruff for linting, formatting, **and import sorting** (I ruleset — no separate isort needed)
- Use pytest for tests
- Use British english in all coding files

# Python Best Practices

- Use type hints everywhere
- Prefer pathlib over os.path
- Avoid premature abstraction
- **NEVER** use mutable default arguments
- **MUST** use context managers (`with` statement) for file/resource management
- **MUST** use `is` for comparing with `None`, `True`, `False`
- **MUST** use f-strings for string formatting; **Never** use .format() or %-formatting
  - Exception: logging calls use lazy `%s` placeholders (`log.info("Ignoring %s", path)`), not f-strings
- Use list comprehensions and generator expressions
- Use `enumerate()` instead of manual counter variables

## Readability First
- Code is read more than written
- Clear variable and function names
- Self-documenting code preferred over comments
- Consistent formatting

## KISS (Keep It Simple)

- Prefer the simplest solution that actually works
- Avoid premature optimization
- Optimize for clarity over cleverness

## DRY (Don't Repeat Yourself)

- Extract repeated logic into shared functions or utilities
- Avoid copy-paste implementation drift
- Introduce abstractions when repetition is real, not speculative

## YAGNI (You Aren't Gonna Need It)

- Do not build features or abstractions before they are needed
- Avoid speculative generality
- Start simple, then refactor when the pressure is real

# Error Handling

- **NEVER** silently swallow exceptions without logging
- **MUST** never use bare `except:` clauses
- **MUST** catch specific exceptions rather than broad exception types
- **MUST** use context managers (`with` statements) for resource cleanup
- Provide meaningful error messages
- Handle errors explicitly at every level
- Log detailed error context on the server side

# Function Design

- **MUST** keep functions focused on a single responsibility
- **NEVER** use mutable objects (lists, dicts) as default argument values
- Limit function parameters to 5 or fewer
- Return early to reduce nesting

# Class Design

- **MUST** keep classes focused on a single responsibility
- **MUST** keep `__init__` simple; avoid complex logic
- Prefer Pydantic models for data containers that need validation; use plain dataclasses for simple containers without validation
- Prefer composition over inheritance
- Avoid creating additional class functions if they are not necessary
- Use `@property` for computed attributes

# Imports and Dependencies

- **MUST** avoid wildcard imports (`from module import *`)
- **MUST** document dependencies in `pyproject.toml`
- Organize imports: standard library, third-party, local imports (enforced by ruff I ruleset)

# Testing

- Always add or update tests
- Run pytest before finalizing
- Prefer focused unit tests
- **MUST** use pytest fixtures instead of setup/teardown methods; pass fixtures explicitly
- Use `@pytest.mark.parametrize` for data-driven tests to avoid duplication

Example parametrize usage:
```python
@pytest.mark.parametrize("input,expected", [(1, 2), (2, 4)])
def test_double(input, expected):
    assert double(input) == expected
```

# Code Style

- Follow PEP8 conventions
- **MUST** use meaningful, descriptive variable and function names
- Avoid single-letter variables
- Use snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- Declare constants at the top of the files directly below imports

# Documentation

- **MUST** include docstrings for all public functions, classes, and methods
- **MUST** document function parameters, return values, and exceptions raised
- Use **Google-style** docstrings (Args / Returns / Raises sections)
- Keep comments up-to-date with code changes
- Include examples in docstrings for complex functions

Example docstring:

```python
def calculate_total(items: list[dict], tax_rate: float = 0.0) -> float:
    """Calculate the total cost of items including tax.

    Args:
        items: List of item dictionaries with 'price' keys
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)

    Returns:
        Total cost including tax

    Raises:
        ValueError: If items is empty or tax_rate is negative
    """
```

# Type Hints

- **MUST** use type hints for all function signatures (parameters and return values)
- **NEVER** use `Any` type unless absolutely necessary
- **MUST** use `T | None` for nullable types — **never** `Optional[T]` (legacy pre-3.10 syntax)

# Security

- **NEVER** store secrets, API keys, or passwords in code. Only store them in `.env`.
  - Ensure `.env` is declared in `.gitignore`.
  - **NEVER** print or log URLs to console if they contain an API key.
- **MUST** use environment variables for sensitive configuration
- **NEVER** log sensitive information (passwords, tokens, PII)
