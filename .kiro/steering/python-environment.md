---
inclusion: conditional
fileMatchPattern: "**/*.py"
---

# Python Development Environment

## Virtual Environments
- **Always use `venv`** for Python projects
- Create: `python3 -m venv venv`
- Activate: `source venv/bin/activate`
- Deactivate: `deactivate`
- Include `venv/` in `.gitignore`

## Cross-Platform Scripts
- **Default to cross-platform compatibility** for Python and Bash scripts
- Do not create OS-specific script variants (Linux vs macOS) unless absolutely necessary
- Test the script first on the current platform before creating OS-specific versions
- Python's `os`, `pathlib`, and `platform` modules handle most cross-platform needs
- Bash scripts work identically on macOS and Linux in 99% of cases

## When OS-Specific Code is Required
- Only create OS-specific branches when:
  - Linux-specific syscalls or kernel features are required
  - Package managers differ (apt vs brew)
  - Binary dependencies have different names/paths
- Use runtime detection (`platform.system()` in Python, `uname` in Bash) rather than separate files
- Document why the OS distinction is necessary

## Dependencies
- Pin versions in `requirements.txt` or `pyproject.toml`
- Use lockfiles (`requirements.lock`, `poetry.lock`, `uv.lock`)
- Never use mutable version specifiers in production (`>=`, `latest`)
