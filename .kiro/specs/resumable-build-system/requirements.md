# Requirements Document: Resumable Build System

## Introduction

The openCenter AirGap build system currently uses a monolithic Bash script (~500 lines) that lacks state management, resume capability, and parallel execution. This specification defines requirements for a hybrid Python/Bash build system that provides resumable builds, step independence verification, and improved error handling while maintaining backward compatibility.

## Glossary

- **Build_Orchestrator**: Python-based main controller that manages build state and step execution
- **Build_Step**: An atomic, idempotent unit of work in the build process
- **Build_State**: JSON-serialized checkpoint data tracking completed steps and their status
- **Completion_Marker**: File-based indicator that a step has successfully completed
- **Step_Dependency**: Relationship where one step must complete before another can execute
- **Bash_Worker**: Shell script that performs subprocess-heavy operations
- **Python_Worker**: Python module that performs text processing or orchestration
- **Idempotent_Operation**: Operation that produces the same result when executed multiple times

## Requirements

### Requirement 1: Build State Management

**User Story:** As a platform engineer, I want the build system to track which steps have completed, so that I can resume builds after failures without re-running successful steps.

#### Acceptance Criteria

1. WHEN a build step completes successfully, THE Build_Orchestrator SHALL write a completion marker to `build/.completed/{step_name}`
2. WHEN a build step completes successfully, THE Build_Orchestrator SHALL update the build state JSON file at `build/.build-state.json`
3. WHEN the build starts, THE Build_Orchestrator SHALL load the previous build state from `build/.build-state.json` if it exists
4. WHEN a step is marked complete in state, THE Build_Orchestrator SHALL skip re-execution unless explicitly requested
5. THE Build_State SHALL include step name, completion timestamp, duration, and success status for each completed step
6. WHEN the build state file is corrupted or invalid, THE Build_Orchestrator SHALL start a fresh build and log a warning

### Requirement 2: Step Dependency Resolution

**User Story:** As a platform engineer, I want steps to execute in the correct order based on dependencies, so that prerequisites are always satisfied before dependent steps run.

#### Acceptance Criteria

1. WHEN a step has dependencies, THE Build_Orchestrator SHALL verify all dependencies are complete before executing the step
2. WHEN a dependency is not satisfied, THE Build_Orchestrator SHALL execute the dependency first
3. WHEN circular dependencies are detected, THE Build_Orchestrator SHALL raise an error and halt execution
4. THE Build_Orchestrator SHALL support declaring multiple dependencies per step
5. WHEN all dependencies for multiple steps are satisfied, THE Build_Orchestrator SHALL execute those steps in parallel

### Requirement 3: Parallel Execution

**User Story:** As a platform engineer, I want independent build steps to run concurrently, so that total build time is reduced.

#### Acceptance Criteria

1. WHEN two or more steps have no dependency relationship, THE Build_Orchestrator SHALL execute them concurrently
2. WHEN executing steps in parallel, THE Build_Orchestrator SHALL limit concurrency to a configurable maximum (default: 2)
3. WHEN a parallel step fails, THE Build_Orchestrator SHALL allow other parallel steps to complete before halting
4. WHEN parallel execution is disabled via flag, THE Build_Orchestrator SHALL execute all steps sequentially
5. THE Build_Orchestrator SHALL display progress for all parallel steps simultaneously

### Requirement 4: Idempotent Step Execution

**User Story:** As a platform engineer, I want each build step to be safely re-runnable, so that partial builds can be resumed without side effects.

#### Acceptance Criteria

1. WHEN a step is executed multiple times, THE Build_Step SHALL produce the same result each time
2. WHEN a step checks for existing outputs, THE Build_Step SHALL skip redundant work if outputs are valid
3. WHEN a step creates directories, THE Build_Step SHALL succeed if directories already exist
4. WHEN a step downloads files, THE Build_Step SHALL skip download if file exists and checksum matches
5. WHEN a step is re-executed after completion, THE Build_Step SHALL complete successfully without errors

### Requirement 5: Resume Capability

**User Story:** As a platform engineer, I want to resume builds from the last successful step, so that I don't waste time re-running completed work after failures.

#### Acceptance Criteria

1. WHEN the build is invoked without flags, THE Build_Orchestrator SHALL resume from the last incomplete step
2. WHEN the `--clean` flag is provided, THE Build_Orchestrator SHALL delete all completion markers and state files
3. WHEN the `--from-step STEP_NAME` flag is provided, THE Build_Orchestrator SHALL resume from the specified step
4. WHEN the `--skip-step STEP_NAME` flag is provided, THE Build_Orchestrator SHALL mark the step as complete without executing it
5. WHEN resuming, THE Build_Orchestrator SHALL validate that all dependencies of the resume point are satisfied
6. WHEN a step is skipped, THE Build_Orchestrator SHALL log a warning and mark it as skipped in the state file

### Requirement 6: Progress Reporting

**User Story:** As a platform engineer, I want clear visual feedback on build progress, so that I can monitor long-running builds and identify bottlenecks.

#### Acceptance Criteria

1. WHEN a step starts, THE Build_Orchestrator SHALL display the step name and description
2. WHEN a step is running, THE Build_Orchestrator SHALL display a progress indicator
3. WHEN a step completes, THE Build_Orchestrator SHALL display the duration and success status
4. WHEN multiple steps run in parallel, THE Build_Orchestrator SHALL display progress for each step
5. WHEN the build completes, THE Build_Orchestrator SHALL display a summary with total duration and step count
6. THE Build_Orchestrator SHALL use the Rich library for formatted console output

### Requirement 7: Error Handling and Recovery

**User Story:** As a platform engineer, I want clear error messages when steps fail, so that I can quickly identify and fix issues.

#### Acceptance Criteria

1. WHEN a step fails, THE Build_Orchestrator SHALL log the error message and stack trace
2. WHEN a step fails, THE Build_Orchestrator SHALL halt execution and preserve the build state
3. WHEN a step fails, THE Build_Orchestrator SHALL display actionable guidance for resolution
4. WHEN a Bash worker script fails, THE Build_Orchestrator SHALL capture and display stderr output
5. WHEN a Python worker raises an exception, THE Build_Orchestrator SHALL capture and display the full traceback
6. THE Build_Orchestrator SHALL write all errors to `build/build.log` in addition to console output

### Requirement 8: Bash Worker Integration

**User Story:** As a platform engineer, I want subprocess-heavy operations to remain in Bash, so that we leverage shell's strengths for process management.

#### Acceptance Criteria

1. WHEN a step is defined as a Bash worker, THE Build_Orchestrator SHALL execute it via subprocess
2. WHEN executing a Bash worker, THE Build_Orchestrator SHALL capture stdout and stderr
3. WHEN a Bash worker exits with non-zero status, THE Build_Orchestrator SHALL treat it as a step failure
4. THE Build_Orchestrator SHALL pass environment variables to Bash workers
5. THE Build_Orchestrator SHALL set the working directory for Bash workers
6. WHEN a Bash worker times out, THE Build_Orchestrator SHALL terminate it and log a timeout error

### Requirement 9: Python Worker Implementation

**User Story:** As a platform engineer, I want text processing and validation logic in Python, so that we have better error handling and testability.

#### Acceptance Criteria

1. WHEN a step is defined as a Python worker, THE Build_Orchestrator SHALL execute it as a Python function
2. WHEN a Python worker raises an exception, THE Build_Orchestrator SHALL capture the exception and treat it as a step failure
3. THE Build_Orchestrator SHALL pass configuration parameters to Python workers as function arguments
4. WHEN a Python worker returns False, THE Build_Orchestrator SHALL treat it as a step failure
5. WHEN a Python worker returns True, THE Build_Orchestrator SHALL treat it as a step success

### Requirement 10: Documentation Updates

**User Story:** As a platform engineer, I want updated documentation reflecting the new build system, so that I can use the correct commands and understand the new features.

#### Acceptance Criteria

1. WHEN documentation references the build command, THE documentation SHALL use `python3 scripts/build/build.py`
2. WHEN documentation describes build flags, THE documentation SHALL include all new flags (--clean, --resume, --from-step, --skip-step, --force, --no-parallel, --max-parallel)
3. WHEN documentation describes resume capability, THE documentation SHALL explain state management and completion markers
4. THE documentation SHALL include examples of resuming after failures
5. THE documentation SHALL include examples of parallel execution benefits

### Requirement 11: Environment Variable Compatibility

**User Story:** As a platform engineer, I want the new build system to honor legacy environment variables, so that existing configurations continue to work.

#### Acceptance Criteria

1. THE Build_Orchestrator SHALL support GITHUB_TOKEN environment variable
2. THE Build_Orchestrator SHALL support SKIP_OPENCENTER_PRIVATE_REGISTRY environment variable
3. THE Build_Orchestrator SHALL support SKIP_KUBESPRAY_OFFLINE environment variable
4. THE Build_Orchestrator SHALL support SKIP_ZARF environment variable
5. THE Build_Orchestrator SHALL support NON_INTERACTIVE environment variable
6. WHEN the build completes successfully, THE Build_Orchestrator SHALL exit with code 0
7. WHEN the build fails, THE Build_Orchestrator SHALL exit with non-zero code

### Requirement 12: Configuration Management

**User Story:** As a platform engineer, I want build configuration centralized and type-safe, so that step definitions are maintainable and validated.

#### Acceptance Criteria

1. THE Build_Orchestrator SHALL define all steps in a Python module using dataclasses
2. WHEN a step is defined, THE definition SHALL include name, description, dependencies, worker type, and worker reference
3. WHEN the build starts, THE Build_Orchestrator SHALL validate all step definitions
4. WHEN a step references a non-existent dependency, THE Build_Orchestrator SHALL raise a validation error
5. WHEN a step references a non-existent worker, THE Build_Orchestrator SHALL raise a validation error

### Requirement 13: Logging and Observability

**User Story:** As a platform engineer, I want comprehensive logs of build execution, so that I can debug issues and audit build history.

#### Acceptance Criteria

1. THE Build_Orchestrator SHALL write all output to `build/build-{timestamp}.log`
2. WHEN a step executes, THE Build_Orchestrator SHALL log the step name, start time, and end time
3. WHEN a step fails, THE Build_Orchestrator SHALL log the error details and context
4. THE Build_Orchestrator SHALL log all subprocess commands before execution
5. THE Build_Orchestrator SHALL include log level indicators (INFO, WARN, ERROR) in all log messages
6. WHEN the build completes, THE Build_Orchestrator SHALL write a summary to the log file

### Requirement 14: Build Validation

**User Story:** As a platform engineer, I want the build system to validate outputs after each step, so that errors are caught early.

#### Acceptance Criteria

1. WHEN a step completes, THE Build_Orchestrator SHALL execute optional validation logic
2. WHEN validation fails, THE Build_Orchestrator SHALL treat it as a step failure
3. WHEN a step produces files, THE validation SHALL verify file existence
4. WHEN a step produces directories, THE validation SHALL verify directory existence and non-empty contents
5. WHEN a step has no validation logic, THE Build_Orchestrator SHALL skip validation

### Requirement 15: Performance Optimization

**User Story:** As a platform engineer, I want the build system to minimize redundant work, so that build times are reduced.

#### Acceptance Criteria

1. WHEN a step's inputs have not changed, THE Build_Orchestrator SHALL skip re-execution if outputs exist
2. WHEN checking for input changes, THE Build_Orchestrator SHALL use file modification timestamps
3. WHEN a step is skipped due to unchanged inputs, THE Build_Orchestrator SHALL log the reason
4. THE Build_Orchestrator SHALL support a `--force` flag to bypass input change detection
5. WHEN parallel execution is enabled, THE total build time SHALL be reduced by at least 20% compared to sequential execution
