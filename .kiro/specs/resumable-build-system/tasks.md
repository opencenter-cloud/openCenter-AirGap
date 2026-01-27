# Implementation Plan: Resumable Build System

## Overview

This plan implements a hybrid Python/Bash build system with state management, resume capability, parallel execution, and improved error handling. The implementation replaces the monolithic `build.sh` with a modular Python orchestrator that calls existing Bash scripts as workers.

## Tasks

- [x] 1. Implement core state management module
  - [x] 1.1 Create build_state.py with BuildState and StepResult dataclasses
    - Define StepStatus enum (NOT_STARTED, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
    - Implement BuildState with to_json() and from_json() methods
    - Implement step status tracking methods (mark_step_started, mark_step_completed, etc.)
    - _Requirements: 1.1, 1.2, 1.5_
  
  - [x] 1.2 Write property test for state persistence round trip
    - **Property 1: State Persistence Round Trip**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.5**
  
  - [x] 1.3 Write unit tests for state management
    - Test state creation, serialization, deserialization
    - Test step status transitions
    - Test corrupted JSON handling
    - _Requirements: 1.6_

- [x] 2. Implement step definitions and dependency resolution
  - [x] 2.1 Create build_steps.py with step definitions
    - Define WorkerType enum (BASH, PYTHON)
    - Define StepDefinition dataclass
    - Define all 15 build steps with dependencies
    - _Requirements: 11.2_
  
  - [x] 2.2 Implement dependency resolution in build_executor.py
    - Implement topological sort with layer detection
    - Implement circular dependency detection
    - Return execution layers for parallel execution
    - _Requirements: 2.1, 2.2, 2.4_
  
  - [x] 2.3 Write property test for dependency resolution
    - **Property 4: Dependency Order Enforcement**
    - **Property 5: Circular Dependency Detection**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
  
  - [x] 2.4 Write unit tests for step definitions
    - Test step validation
    - Test dependency graph construction
    - _Requirements: 11.3, 11.4, 11.5_

- [x] 3. Implement build executor with parallel execution
  - [x] 3.1 Create build_executor.py with BuildExecutor class
    - Implement execute_build() method
    - Implement execute_step() for single step execution
    - Implement execute_layer() for parallel execution
    - Implement execute_bash_worker() and execute_python_worker()
    - _Requirements: 3.1, 3.2, 8.1, 9.1_
  
  - [x] 3.2 Add progress tracking with Rich library
    - Display step progress indicators
    - Display parallel step progress
    - Display build summary
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [x] 3.3 Write property tests for parallel execution
    - **Property 6: Parallel Execution of Independent Steps**
    - **Property 7: Parallel Failure Isolation**
    - **Property 8: Sequential Mode Enforcement**
    - **Validates: Requirements 2.5, 3.1, 3.2, 3.3, 3.4**
  
  - [x] 3.4 Write unit tests for executor
    - Test sequential execution
    - Test parallel execution with max_parallel limit
    - Test error handling and state preservation
    - _Requirements: 7.2_

- [x] 4. Checkpoint - Ensure core modules work together
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Python worker functions
  - [x] 5.1 Create workers/prerequisites.py
    - Implement check_prerequisites_worker()
    - Check Python 3.12+, container runtime, git, jq, zarf, disk space
    - _Requirements: 9.1, 9.2_
  
  - [x] 5.2 Create workers/python_env.py
    - Implement setup_python_env_worker()
    - Implement validate_python_env()
    - Create venv, install dependencies (PyYAML, Jinja2, requests, hypothesis, pytest, rich)
    - _Requirements: 9.1, 9.2, 13.1_
  
  - [x] 5.3 Create workers/github_token.py
    - Implement check_github_token_worker()
    - Validate GITHUB_TOKEN environment variable
    - _Requirements: 9.1, 11.1_
  
  - [x] 5.4 Create workers/validation.py
    - Implement validate_versions_worker()
    - Implement validate_zarf_yaml_worker()
    - Implement validate_build_outputs_worker()
    - _Requirements: 9.1, 13.1_
  
  - [x] 5.5 Create workers/checksums.py
    - Implement generate_checksums_worker()
    - Generate SHA256 and MD5 checksums for Zarf package
    - _Requirements: 9.1_
  
  - [x] 5.6 Write property tests for Python workers
    - **Property 20: Python Worker Execution**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
  
  - [x] 5.7 Write unit tests for worker functions
    - Test each worker function with valid and invalid inputs
    - Test validation functions
    - _Requirements: 9.1, 9.2_

- [x] 6. Convert merge_images.sh to Python
  - [x] 6.1 Create merge_images.py
    - Implement merge_opencenter_images() function
    - Copy openCenter images to kubespray-offline/imagelists/additional_images.txt
    - Backup existing file with timestamp
    - Count and categorize images
    - _Requirements: 9.1_
  
  - [x] 6.2 Write unit tests for merge_images
    - Test image file merging
    - Test backup creation
    - Test image counting and categorization
    - _Requirements: 9.1_

- [x] 7. Implement main orchestrator
  - [x] 7.1 Create build.py with main() entry point
    - Implement parse_args() for CLI argument parsing
    - Implement setup_logging() for file and console logging
    - Implement load_state() and save_state()
    - Implement run_build() to coordinate execution
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 11.6, 11.7_
  
  - [x] 7.2 Add error handling and recovery
    - Capture and log all errors with actionable messages
    - Preserve state on failure
    - Display resume instructions
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [x] 7.3 Add completion marker management
    - Create build/.completed/ directory
    - Write marker files after step completion
    - Check markers for idempotency
    - _Requirements: 1.1, 4.1_
  
  - [x] 7.4 Write property tests for resume capability
    - **Property 11: Default Resume Behavior**
    - **Property 12: Clean Flag Behavior**
    - **Property 13: Explicit Resume Point**
    - **Property 14: Step Skipping**
    - **Property 15: Resume Dependency Validation**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6**
  
  - [x] 7.5 Write unit tests for main orchestrator
    - Test CLI argument parsing
    - Test state loading/saving
    - Test clean flag behavior
    - Test from-step and skip-step flags
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 8. Checkpoint - Ensure orchestrator integrates with workers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Create Bash worker wrappers
  - [x] 9.1 Update collect_opencenter_assets.sh
    - Add completion marker creation at end
    - Ensure idempotency (skip if already collected)
    - _Requirements: 4.1, 8.1_
  
  - [x] 9.2 Create collect_kubespray_offline.sh wrapper
    - Clone/update kubespray-offline repo
    - Run download-all.sh
    - Add completion marker creation
    - _Requirements: 4.1, 8.1_
  
  - [x] 9.3 Update organize_assets_for_zarf.sh
    - Add completion marker creation at end
    - Ensure idempotency (skip if already organized)
    - _Requirements: 4.1, 8.1_
  
  - [x] 9.4 Write property tests for Bash worker integration
    - **Property 18: Bash Worker Execution**
    - **Property 19: Bash Worker Timeout**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

- [x] 10. Implement idempotency and optimization
  - [x] 10.1 Add input change detection to build_executor.py
    - Check file modification timestamps
    - Skip steps with unchanged inputs and existing outputs
    - Log skip reason
    - _Requirements: 14.1, 14.2, 14.3_
  
  - [x] 10.2 Add --force flag support
    - Bypass input change detection
    - Force re-execution of all steps
    - _Requirements: 14.4_
  
  - [x] 10.3 Write property tests for idempotency
    - **Property 9: Step Idempotency**
    - **Property 10: Output-Based Skip Optimization**
    - **Property 30: Input Change Detection**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 14.1, 14.2, 14.3, 14.4**

- [x] 11. Add comprehensive logging
  - [x] 11.1 Implement structured logging in build.py
    - Create timestamped log files in build/
    - Log all step executions with start/end times
    - Log subprocess commands before execution
    - Include log level indicators (INFO, WARN, ERROR)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [x] 11.2 Add build summary logging
    - Write summary at build completion
    - Include total duration and step count
    - _Requirements: 12.6_
  
  - [x] 11.3 Write property tests for logging
    - **Property 26: Log File Creation**
    - **Property 27: Comprehensive Logging**
    - **Property 28: Build Summary Logging**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6**

- [x] 12. Checkpoint - Ensure full build works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Delete legacy build.sh and update documentation
  - [x] 13.1 Delete scripts/build/build.sh
    - Remove legacy Bash implementation
    - _Requirements: 10.1_
  
  - [x] 13.2 Update build documentation
    - Update docs/how-to/build/build-air-gap-package.md
    - Replace all build.sh references with python3 scripts/build/build.py
    - Document all CLI flags (--clean, --resume, --from-step, --skip-step, --force, --no-parallel, --max-parallel)
    - Add examples of resuming after failures
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [x] 13.3 Update README.md
    - Update build instructions
    - Update quick start guide
    - _Requirements: 10.1_
  
  - [x] 13.4 Update CI/CD configurations
    - Update any pipeline scripts that call build.sh
    - _Requirements: 10.1_

- [x] 14. Integration testing
  - [x] 14.1 Write integration test for full build
    - Test complete build from start to finish
    - Verify all steps execute in correct order
    - Verify final outputs exist
    - _Requirements: All_
  
  - [x] 14.2 Write integration test for resume scenarios
    - Test resume after failure at various steps
    - Test --clean flag
    - Test --from-step flag
    - Test --skip-step flag
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [x] 14.3 Write integration test for parallel execution
    - Test parallel execution of independent steps
    - Verify time savings compared to sequential
    - Test --no-parallel flag
    - _Requirements: 3.1, 3.2, 3.4, 14.5_

- [ ] 15. Final checkpoint - Complete validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- Bash scripts remain for subprocess-heavy operations (git, skopeo, tar)
- Python handles orchestration, state management, and text processing
- Direct Python invocation replaces build.sh wrapper
