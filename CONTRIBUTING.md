# Contributing to openCenter AirGap

**doc_type**: how-to
**audience**: Platform Engineers, Developers
**scope**: Development environment setup, testing, and contribution workflow

This guide covers setting up your development environment, running tests, and submitting changes to openCenter AirGap.

## Prerequisites

**Operating System**: Ubuntu 24.04 LTS (or compatible Linux distribution)

**Required Tools**:
- Python 3.10 or later
- Git 2.30+
- Podman or Docker
- 100GB+ free disk space

**Optional Tools** (for full development):
- Zarf CLI (for package testing)
- Terraform 1.6.6+ (for OpenStack testing)
- shellcheck (for Bash linting)

## Development Environment Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd opencenter-airgap
```

### 2. Install Python Package in Development Mode

```bash
# Install package with development dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import opencenter_build; print(opencenter_build.__version__)"
```

This installs:
- `pytest` - Test framework
- `pytest-timeout` - Test timeout enforcement
- `pytest-cov` - Coverage reporting
- `hypothesis` - Property-based testing
- `black` - Code formatter
- `mypy` - Type checker
- `pylint` - Linter

### 3. Install Pre-commit Hooks

```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

Pre-commit hooks enforce:
- Code formatting (black)
- Type checking (mypy)
- Linting (pylint)
- Shell script validation (shellcheck)
- Secret detection
- Trailing whitespace removal

### 4. Verify Development Environment

```bash
# Run quick verification
make install-dev
make lint
make test-unit
```

If `make` is not available, run commands directly:

```bash
pip install -e ".[dev]"
black --check src/ tests/
mypy src/
pylint src/
pytest tests/unit/ -v
```

## Project Structure

```
opencenter-airgap/
├── src/opencenter_build/      # Python package (reusable modules)
│   ├── exceptions.py          # Exception hierarchy
│   ├── logging.py             # Centralized logging
│   ├── state.py               # Atomic state management
│   ├── config.py              # Configuration loading
│   ├── validation.py          # Schema validation
│   ├── secrets.py             # Secrets management
│   ├── transaction.py         # Rollback support
│   ├── metrics.py             # Build metrics
│   ├── image_utils.py         # Image operations
│   ├── version_utils.py       # Version validation
│   └── zarf_utils.py          # Zarf generation
├── scripts/
│   ├── build/                 # Build orchestration scripts
│   └── deploy/                # Deployment scripts
├── config/
│   ├── versions.env           # Version pinning
│   └── schemas/               # JSON schemas for validation
├── tests/
│   ├── unit/                  # Unit tests
│   ├── property/              # Property-based tests
│   └── integration/           # End-to-end tests
├── pyproject.toml             # Python package definition
└── Makefile                   # Developer commands
```

## Code Style Guidelines

### Python

**Style Guide**: Follow [PEP 8](https://pep8.org/) and [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

**Formatting**:
- Line length: 100 characters
- Use `black` for automatic formatting
- 4 spaces for indentation (no tabs)

**Type Hints**:
- All functions must have type hints
- Use `mypy --strict` for type checking
- Avoid `Any` unless absolutely necessary

**Docstrings**:
- All public functions require docstrings
- Use Google-style docstring format
- Include Args, Returns, Raises sections

Example:
```python
def validate_config(config: dict[str, str]) -> None:
    """Validate configuration against schema.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValidationError: If configuration is invalid
    """
    if "KUBERNETES_VERSION" not in config:
        raise ValidationError("Missing required field: KUBERNETES_VERSION")
```

**Error Handling**:
- Use specific exceptions from `opencenter_build.exceptions`
- Never use bare `except:` blocks
- Always include error context and chain exceptions

**Logging**:
- Use `logging` module (never `print()` in production code)
- Import logger: `logger = logging.getLogger(__name__)`
- Log levels: DEBUG (verbose), INFO (progress), WARNING (recoverable), ERROR (failures)

### Bash

**Style Guide**: Follow [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)

**Error Handling**:
- Always use `set -euo pipefail` at script start
- Check command exit codes explicitly when needed
- Use `|| true` only when failure is acceptable

**Logging**:
- Source `scripts/lib/logging.sh` for consistent logging
- Use `log_info`, `log_warn`, `log_error` functions
- Include timestamps in log messages

**Validation**:
- Run `shellcheck` on all Bash scripts
- Fix all warnings before committing

### Language Selection

When choosing between Python and Bash, follow the decision matrix in [docs/reference/coding-standards.md](docs/reference/coding-standards.md).

**Quick reference**:
- **Python**: JSON/YAML parsing, validation logic, state management, HTTP APIs, data transformation
- **Bash**: File operations, tool orchestration, text processing, deployment workflows

See the full [Coding Standards](docs/reference/coding-standards.md) for:
- Complete language decision matrix
- Error handling patterns for both languages
- Logging conventions
- Testing requirements
- Code examples and anti-patterns
- Migration plan for mixed-responsibility scripts

## Testing Requirements

### Running Tests

```bash
# All tests
make test

# Unit tests only (fast)
make test-unit

# Integration tests (slow, requires build artifacts)
make test-integration

# Property-based tests
pytest tests/property/ -v

# Specific test file
pytest tests/unit/test_validation.py -v

# With coverage report
make coverage
```

### Writing Tests

**Unit Tests**:
- Test individual functions in isolation
- Use descriptive test names: `test_validate_config_missing_required_field`
- Test both success and failure cases
- Keep tests fast (< 1 second each)

Example:
```python
def test_validate_versions_env_missing_kubernetes_version():
    """Test validation fails when KUBERNETES_VERSION is missing."""
    validator = ConfigValidator(Path("config/schemas"))
    config = {"TERRAFORM_VERSION": "1.6.6"}

    with pytest.raises(ValidationError, match="KUBERNETES_VERSION"):
        validator.validate_versions_env(config)
```

**Property-Based Tests**:
- Use `hypothesis` for property-based testing
- Test invariants that should hold for all inputs
- Generate realistic test data

Example:
```python
from hypothesis import given, strategies as st

@given(st.dictionaries(st.text(), st.text()))
def test_state_manager_roundtrip(state_data):
    """Test state can be written and read back unchanged."""
    state_mgr = StateManager(Path("test-state.json"))
    state_mgr.write(state_data)
    assert state_mgr.read() == state_data
```

**Integration Tests**:
- Test end-to-end workflows
- Use temporary directories for test artifacts
- Clean up after tests
- Set reasonable timeouts (use `pytest-timeout`)

### Test Coverage

**Coverage Requirements**:
- Minimum 80% code coverage required for all PRs
- Coverage is enforced in CI pipeline
- New code must maintain or improve coverage

**Check Coverage**:
```bash
# Run tests with coverage report
pytest --cov=src --cov-report=term-missing --cov-report=html

# View detailed HTML report
open htmlcov/index.html
```

**Coverage Configuration**:
- Configured in `pyproject.toml` under `[tool.coverage]`
- Threshold: `fail_under = 80.0`
- Branch coverage enabled
- Excludes test files and generated code

**Improving Coverage**:
1. Identify uncovered lines: `pytest --cov=src --cov-report=term-missing`
2. Add tests for uncovered code paths
3. Focus on critical business logic first
4. Use property-based tests for edge cases

### Testing Checklist

Before submitting a PR:
- [ ] All tests pass: `make test`
- [ ] Coverage meets threshold: `make coverage`
- [ ] Type checking passes: `mypy src/`
- [ ] Linting passes: `pylint src/`
- [ ] Formatting applied: `black src/ tests/`
- [ ] Shell scripts validated: `shellcheck scripts/**/*.sh`

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or fixes

### 2. Make Changes

- Write code following style guidelines
- Add tests for new functionality
- Update documentation if needed
- Keep commits focused and atomic

### 3. Test Changes

```bash
# Run tests
make test

# Check formatting
black --check src/ tests/

# Type checking
mypy src/

# Linting
pylint src/

# Shell validation
shellcheck scripts/**/*.sh
```

### 4. Commit Changes

```bash
# Stage changes
git add <files>

# Commit with descriptive message
git commit -m "Add config validation for versions.env

- Implement ConfigValidator class
- Add JSON schema for versions.env
- Add unit tests for validation
- Update documentation"
```

Commit message format:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed description with bullet points
- Reference issue numbers if applicable

### 5. Push and Create Pull Request

```bash
# Push branch
git push origin feature/your-feature-name

# Create PR on GitHub
# Fill out PR template with:
# - Description of changes
# - Testing performed
# - Related issues
```

### 6. Address Review Feedback

```bash
# Make requested changes
git add <files>
git commit -m "Address review feedback"
git push origin feature/your-feature-name
```

## Common Development Tasks

### Add New Python Module

```bash
# Create module file
touch src/opencenter_build/new_module.py

# Add type hints and docstrings
# Create corresponding test file
touch tests/unit/test_new_module.py

# Run tests
pytest tests/unit/test_new_module.py -v
```

### Add Configuration Schema

```bash
# Create schema file
touch config/schemas/new-config.schema.json

# Add validation method to ConfigValidator
# Add tests
pytest tests/unit/test_validation.py -v
```

### Update Dependencies

```bash
# Edit pyproject.toml
# Add dependency to [project.dependencies] or [project.optional-dependencies]

# Reinstall package
pip install -e ".[dev]"

# Test changes
make test
```

### Debug Build Issues

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run build with verbose output
python scripts/build/build.py --verbose

# Check build logs
tail -f build/build-*.log

# Inspect build state
cat build/.build-state.json | python -m json.tool
```

### Test Zarf Package Locally

```bash
# Build package
python scripts/build/build.py

# Inspect package
zarf package inspect dist/zarf-package-*.tar.zst

# Test deployment in VM or container
# (See docs/how-to/test/test-package-locally.md)
```

## Secrets Management

**Never commit secrets to the repository.**

### Using Secrets in Development

```bash
# Create secrets directory
mkdir -p .secrets
chmod 700 .secrets

# Add secret file
echo "ghp_xxxxxxxxxxxx" > .secrets/github-token
chmod 600 .secrets/github-token

# Use in code
from opencenter_build.secrets import SecretsManager

secrets = SecretsManager(Path(".secrets"))
token = secrets.get_secret("github-token")
```

The `.secrets/` directory is in `.gitignore` and will never be committed.

### Pre-commit Secret Detection

Pre-commit hooks scan for common secret patterns:
- API keys
- Tokens
- Passwords
- Private keys

If secrets are detected, the commit will be blocked.

## Troubleshooting Development Issues

### Import Errors

```bash
# Verify package installed
pip list | grep opencenter-build

# Reinstall in development mode
pip install -e ".[dev]"
```

### Type Checking Errors

```bash
# Run mypy with verbose output
mypy --show-error-codes src/

# Ignore specific error (use sparingly)
# Add comment: # type: ignore[error-code]
```

### Test Failures

```bash
# Run single test with verbose output
pytest tests/unit/test_validation.py::test_specific_test -vv

# Run with debugging
pytest --pdb tests/unit/test_validation.py

# Check test logs
pytest --log-cli-level=DEBUG tests/unit/test_validation.py
```

### Pre-commit Hook Failures

```bash
# Run specific hook
pre-commit run black --all-files

# Run all hooks manually
pre-commit run --all-files

# Skip hooks temporarily (emergency only)
git commit --no-verify -m "Emergency fix"

# Update hooks
pre-commit autoupdate
```

**Emergency Hook Bypass**:

Use `--no-verify` only in genuine emergencies:
- Critical production hotfix
- Broken CI pipeline blocking urgent fix
- Pre-commit infrastructure issue

After bypassing hooks:
1. Create follow-up issue to fix violations
2. Run hooks manually: `pre-commit run --all-files`
3. Commit fixes in separate PR

**Never bypass hooks for**:
- Convenience
- Avoiding code cleanup
- Skipping tests
- Committing secrets

## Getting Help

- **Documentation**: Check [docs/](docs/) directory
- **Issues**: Search existing issues on GitHub
- **Questions**: Open a discussion on GitHub
- **Security**: See [SECURITY.md](SECURITY.md) for security reporting

## Code Review Guidelines

When reviewing PRs:
- Check code follows style guidelines
- Verify tests cover new functionality
- Ensure documentation is updated
- Test changes locally if possible
- Provide constructive feedback
- Approve when satisfied

When your PR is reviewed:
- Respond to all comments
- Make requested changes promptly
- Ask questions if feedback is unclear
- Thank reviewers for their time

## Release Process

Releases are managed by maintainers. Contributors should:
- Keep changes focused and well-tested
- Update CHANGELOG.md with notable changes
- Follow semantic versioning for breaking changes

## License

By contributing, you agree that your contributions will be licensed under the same license as the project. See [LICENSE](LICENSE) for details.
