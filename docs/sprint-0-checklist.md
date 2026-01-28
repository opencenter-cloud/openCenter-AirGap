# Sprint 0 Checklist: Week 1 Implementation

**Duration**: 5 days
**Engineer**: 1
**Goal**: Critical issues + quick wins

## Day 1: Quick Wins (4 hours)

### Task 1.1: Add .editorconfig (30 min)
- [ ] Create `.editorconfig` file
- [ ] Configure for Python, Bash, YAML
- [ ] Test with team editors
- [ ] Commit and push

### Task 1.2: Add CODEOWNERS (15 min)
- [ ] Create `CODEOWNERS` file
- [ ] Define ownership by directory
- [ ] Test with PR
- [ ] Commit and push

### Task 1.3: Add SECURITY.md (30 min)
- [ ] Create `SECURITY.md`
- [ ] Define security reporting process
- [ ] Add contact information
- [ ] Commit and push

### Task 1.4: Add Issue Templates (1 hour)
- [ ] Create `.github/ISSUE_TEMPLATE/` directory
- [ ] Add `bug_report.yml`
- [ ] Add `feature_request.yml`
- [ ] Test template rendering
- [ ] Commit and push

### Task 1.5: Add CONTRIBUTING.md (1.5 hours)
- [ ] Create `CONTRIBUTING.md`
- [ ] Document development setup
- [ ] Document testing process
- [ ] Document code style
- [ ] Add PR guidelines
- [ ] Commit and push

**Acceptance**: All files committed, team notified

---

## Day 2-3: Python Package Structure (12 hours)

### Task 2.1: Create pyproject.toml (2 hours)
- [ ] Create `pyproject.toml` in project root
- [ ] Define project metadata
- [ ] Add dependencies (none for now)
- [ ] Add dev dependencies (pytest, black, mypy, pylint)
- [ ] Configure black settings
- [ ] Configure mypy strict mode
- [ ] Configure pytest settings
- [ ] Test: `pip install -e .`

### Task 2.2: Create Package Structure (2 hours)
- [ ] Create `src/opencenter_build/` directory
- [ ] Create `src/opencenter_build/__init__.py`
- [ ] Create `src/opencenter_build/exceptions.py`
- [ ] Create `src/opencenter_build/logging.py`
- [ ] Create `src/opencenter_build/state.py`
- [ ] Create `src/opencenter_build/config.py`
- [ ] Create `src/opencenter_build/image_utils.py`
- [ ] Create `src/opencenter_build/version_utils.py`
- [ ] Create `src/opencenter_build/zarf_utils.py`

### Task 2.3: Implement Core Modules (4 hours)
- [ ] Implement `exceptions.py` with exception hierarchy
- [ ] Implement `logging.py` with setup_logging()
- [ ] Implement `state.py` with StateManager class
- [ ] Add type hints to all functions
- [ ] Add docstrings to all public functions

### Task 2.4: Migrate Existing Code (3 hours)
- [ ] Move image parsing logic to `image_utils.py`
- [ ] Move version validation to `version_utils.py`
- [ ] Move zarf generation to `zarf_utils.py`
- [ ] Update imports in existing scripts
- [ ] Test all scripts still work

### Task 2.5: Type Checking (1 hour)
- [ ] Run `mypy src/` and fix errors
- [ ] Run `black src/` to format
- [ ] Run `pylint src/` and address issues
- [ ] Commit changes

**Acceptance**: `pip install -e .` works, mypy passes, tests pass

---

## Day 4-5: Configuration Schema Validation (12 hours)

### Task 3.1: Create Schema Directory (1 hour)
- [ ] Create `config/schemas/` directory
- [ ] Create `config/schemas/README.md`
- [ ] Document schema format

### Task 3.2: Define Schemas (4 hours)
- [ ] Create `versions.schema.json`
  - [ ] Define required fields
  - [ ] Add version format patterns
  - [ ] Add examples
- [ ] Create `nodes.schema.json`
  - [ ] Define control_plane structure
  - [ ] Define workers structure
  - [ ] Add validation rules
- [ ] Create `openstack-config.schema.json`
  - [ ] Define required fields
  - [ ] Add validation rules
- [ ] Create `zarf-variables.schema.json`
  - [ ] Define variable structure
  - [ ] Add validation rules

### Task 3.3: Implement Validation Module (3 hours)
- [ ] Create `src/opencenter_build/validation.py`
- [ ] Implement `ConfigValidator` class
- [ ] Add `validate_versions_env()` method
- [ ] Add `validate_nodes_file()` method
- [ ] Add `validate_openstack_config()` method
- [ ] Add error reporting with context

### Task 3.4: Integrate Validation (2 hours)
- [ ] Add validation to `scripts/build/build.py`
- [ ] Add validation to `scripts/deploy/deploy.sh`
- [ ] Update error messages
- [ ] Test with invalid configs

### Task 3.5: Write Tests (2 hours)
- [ ] Create `tests/unit/test_validation.py`
- [ ] Test valid configs pass
- [ ] Test invalid configs fail
- [ ] Test error messages are clear
- [ ] Run tests: `pytest tests/unit/test_validation.py -v`

**Acceptance**: Validation catches errors, tests pass, docs updated

---

## Verification Checklist

### Code Quality
- [ ] All Python code passes `mypy --strict`
- [ ] All Python code formatted with `black`
- [ ] All Bash scripts pass `shellcheck`
- [ ] No TODO/FIXME comments without tickets

### Testing
- [ ] All unit tests pass
- [ ] Test coverage >80% for new code
- [ ] Integration tests still pass

### Documentation
- [ ] All new functions have docstrings
- [ ] README.md updated if needed
- [ ] CONTRIBUTING.md reflects new setup

### Git
- [ ] All commits have descriptive messages
- [ ] No secrets in commit history
- [ ] Branch up to date with main

---

## Rollout Plan

### Day 1 (Quick Wins)
1. Create feature branch: `feature/sprint-0-quick-wins`
2. Implement all quick wins
3. Create PR, get review
4. Merge to main
5. Announce to team

### Day 2-3 (Python Package)
1. Create feature branch: `feature/sprint-0-python-package`
2. Implement package structure
3. Migrate existing code
4. Run full test suite
5. Create PR, get review
6. Merge to main

### Day 4-5 (Config Validation)
1. Create feature branch: `feature/sprint-0-config-validation`
2. Implement schemas and validation
3. Integrate into build/deploy
4. Write tests
5. Create PR, get review
6. Merge to main

---

## Success Metrics

- [ ] 5 governance files added
- [ ] Python package installable
- [ ] Config validation active
- [ ] 0 mypy errors
- [ ] 100% of new code tested
- [ ] Team trained on new structure

---

## Blockers & Risks

### Potential Blockers
- Python version compatibility issues
- Existing code dependencies unclear
- Schema design requires domain knowledge

### Mitigation
- Test on Python 3.10, 3.11, 3.12
- Audit imports before migration
- Review schemas with domain experts

---

## Communication Plan

### Daily Standup
- Report progress on tasks
- Raise blockers immediately
- Share learnings

### End of Sprint
- Demo new capabilities
- Share documentation
- Gather feedback

---

## Next Sprint Preview

**Sprint 1 (Week 2)** will focus on:
- Language boundary documentation
- Atomic state management completion
- Team training on new standards
