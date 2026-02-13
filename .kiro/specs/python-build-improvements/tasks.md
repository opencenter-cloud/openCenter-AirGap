# Implementation Plan: Python Build Improvements

## Overview

Implement hybrid Python + Zarf architecture for openCenter AirGap build system. Incremental approach maintains backward compatibility while introducing concurrent scanning, state management, modern CLI, and automatic Zarf package generation.

## Tasks

- [x] 1. Project structure and dependencies
  - Create src/opencenter_build/ package structure
  - Add pyproject.toml with dependencies: typer, rich, hypothesis, pyyaml
  - Pin all dependency versions
  - Set up pytest configuration
  - _Requirements: 11.4_

- [x] 2. Core data models
  - [x] 2.1 Implement BuildConfig dataclass
    - Load from versions.env with dotenv parsing
    - Validate required fields
    - Generate SHA256 config hash
    - _Requirements: 10.1, 10.2, 12.1_

  - [x] 2.2 Implement state management models
    - StepStatus enum (PENDING, RUNNING, COMPLETED, FAILED)
    - StepCheckpoint dataclass with timestamps
    - BuildState dataclass with step list
    - FileMetadata and ImageMetadata dataclasses
    - _Requirements: 4.1, 4.2_

  - [x] 2.3 Write property test for BuildConfig parsing
    - **Property 16: Backward Compatible Configuration Parsing**
    - **Validates: Requirements 12.1**

  - [x] 2.4 Write property test for state serialization
    - **Property 3: State Persistence Round Trip**
    - **Validates: Requirements 4.1, 4.5**

- [x] 3. Repository scanner with concurrency
  - [x] 3.1 Implement RepositoryScanner class
    - ProcessPoolExecutor with configurable workers
    - Cached regex pattern compilation with lru_cache
    - Memory-mapped file reading for files >1MB
    - Graceful encoding error handling
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3_

  - [x] 3.2 Write property test for image discovery
    - **Property 1: Image Discovery Completeness**
    - **Validates: Requirements 1.4**

  - [x] 3.3 Write property test for encoding resilience
    - **Property 2: Encoding Error Resilience**
    - **Validates: Requirements 2.3**

  - [x] 3.4 Write unit tests for scanner edge cases
    - Empty repositories
    - Repositories with no images
    - Invalid file paths
    - _Requirements: 1.4, 2.3_

- [x] 4. State management with checkpoint/resume
  - [x] 4.1 Implement StateManager class
    - Atomic file writes (temp + rename)
    - JSON serialization/deserialization
    - Find resume point logic
    - _Requirements: 4.1, 4.5, 4.6, 4.7_

  - [x] 4.2 Implement BuildOrchestrator class
    - Step execution with try/catch/finally
    - Checkpoint persistence after each step
    - Resume from last incomplete step
    - Rollback on failure
    - _Requirements: 4.3, 4.4_

  - [x] 4.3 Write property test for failure state capture
    - **Property 4: Failure State Capture**
    - **Validates: Requirements 4.2**

  - [x] 4.4 Write property test for resume behavior
    - **Property 5: Resume Skips Completed Steps**
    - **Property 6: Resume Starts at First Incomplete**
    - **Validates: Requirements 4.3, 4.4**

  - [x] 4.5 Write unit tests for state manager
    - State file creation
    - Concurrent access handling
    - Corrupted state recovery
    - _Requirements: 4.1, 4.5_

- [x] 5. Checkpoint - Verify core functionality
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Zarf package generation
  - [x] 6.1 Implement ZarfGenerator class
    - Parse versions.env for component versions
    - Generate images component from discovered images
    - Generate charts component from config
    - Generate repos component from config
    - Generate files component for binaries/packages
    - Generate actions component for bastion services
    - Write zarf.yaml with proper schema
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 6.2 Write property test for Zarf generation
    - **Property 7: Zarf Configuration Generation**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

  - [x] 6.3 Write unit tests for Zarf components
    - Images component structure
    - Charts component structure
    - Repos component structure
    - Files component structure
    - Actions component structure
    - _Requirements: 5.2, 5.3, 5.4, 5.5_

- [x] 7. Artifact manifest generation
  - [x] 7.1 Implement ArtifactManifest dataclass
    - Fields for all artifact types
    - Total count and size calculations
    - Size formatting helper
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [x] 7.2 Implement ManifestGenerator class
    - Scan build directory for artifacts
    - Calculate sizes and checksums
    - Export JSON format
    - Export Markdown format with tables
    - _Requirements: 6.10, 6.11_

  - [x] 7.3 Write property test for manifest completeness
    - **Property 8: Manifest Completeness**
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8**

  - [x] 7.4 Write property test for manifest consistency
    - **Property 9: Manifest Total Consistency**
    - **Validates: Requirements 6.9**

  - [x] 7.5 Write property test for manifest serialization
    - **Property 10: Manifest Serialization Round Trip**
    - **Validates: Requirements 6.10**

  - [x] 7.6 Write property test for Markdown export
    - **Property 11: Markdown Export Completeness**
    - **Validates: Requirements 6.11**

- [x] 8. Structured logging and metrics
  - [x] 8.1 Implement structured logging
    - JSON formatter with timestamp, level, message, trace_id
    - Context variable for trace_id propagation
    - Log level configuration (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 8.2 Implement metrics exporter
    - BuildMetrics dataclass
    - Prometheus format export
    - Record build duration, status, per-step durations, artifact counts
    - Write to dist/build-metrics.prom
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 8.3 Write property test for JSON log structure
    - **Property 12: JSON Log Structure**
    - **Validates: Requirements 7.2**

  - [x] 8.4 Write property test for metrics completeness
    - **Property 13: Metrics Completeness**
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5**

- [x] 17. CLI implementation with Typer and Rich
  - [x] 17.1 Implement init command
    - Create component manifest from template
    - Validate config file
    - Initialize directory structure
    - _Requirements: 3.6, 10.1, 13.7_

  - [x] 17.2 Implement add command
    - Add tool to component manifest
    - Add repository to component manifest
    - Add image to component manifest
    - Add chart to component manifest
    - _Requirements: 3.6, 13.7_

  - [x] 17.3 Implement scan command
    - Invoke RepositoryScanner
    - Discover images from repositories
    - Display progress bar with Rich
    - Write results to config/all-images.txt
    - _Requirements: 3.2, 3.5, 3.6_

  - [x] 17.4 Implement generate-manifest command
    - Invoke ManifestGenerator
    - Display progress with Rich
    - Validate generated zarf.yaml
    - _Requirements: 3.6, 14.1_

  - [x] 17.5 Implement build command
    - Invoke BuildOrchestrator
    - Display step progress with Rich
    - Handle --clean and --resume flags
    - Display success/error indicators
    - _Requirements: 3.3, 3.4, 3.6, 4.6, 4.7_

  - [x] 17.6 Implement validate command
    - Check config/versions.env exists
    - Validate component manifest
    - Validate required variables
    - Validate repository paths
    - Check Zarf installation
    - Display validation results
    - Handle --strict and --check-upstream flags
    - _Requirements: 3.6, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 13.8_

  - [x] 17.7 Implement verify command
    - Invoke PackageVerifier
    - Display verification results with Rich
    - Handle --manifest flag
    - _Requirements: 3.6, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [x] 17.8 Implement status command
    - Read build state
    - Display step statuses with Rich table
    - Show progress percentage
    - _Requirements: 3.6_

  - [x] 17.9 Implement clean command
    - Remove build artifacts
    - Remove state file
    - Confirm before deletion
    - _Requirements: 3.6_

  - [x] 17.10 Implement version command
    - Display tool version
    - Display Python version
    - Display dependency versions
    - _Requirements: 3.6_

  - [x] 17.11 Write unit tests for CLI commands
    - Test command invocation
    - Test flag handling
    - Test error messages
    - _Requirements: 3.5, 3.6, 4.6, 4.7, 7.4, 7.5, 10.3_

- [ ] 18. Checkpoint - Verify CLI and core features
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Deployment and service management
  - [x] 19.1 Implement serve command
    - Execute zarf package deploy
    - Start nginx container with volume mounts
    - Verify service health (HTTP 200 checks)
    - Display service URLs
    - Cleanup on failure
    - _Requirements: 3.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 19.2 Write property test for service cleanup
    - **Property 14: Service Cleanup on Failure**
    - **Validates: Requirements 9.5**

  - [x] 19.3 Write integration test for deployment
    - Deploy to test environment
    - Verify all services running
    - Verify artifact serving
    - _Requirements: 9.3, 9.4_

- [x] 20. Configuration validation
  - [x] 20.1 Implement ConfigValidator class
    - Validate versions.env format
    - Check required variables
    - Validate repository paths
    - Check external dependencies (Zarf, Docker)
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

  - [x] 20.2 Write property test for validation
    - **Property 15: Configuration Validation Completeness**
    - **Validates: Requirements 10.2, 10.4**

- [x] 21. Binary packaging with PyInstaller
  - [x] 21.1 Create PyInstaller spec file
    - Configure entry point
    - Include data files
    - Set binary name to opencenter-airgap
    - Target Ubuntu 24.04 AMD64
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 21.2 Build and test binary
    - Build with PyInstaller
    - Verify binary size <25MB
    - Test on clean Ubuntu 24.04 system
    - Verify all dependencies included
    - _Requirements: 11.4, 11.5_

  - [x] 21.3 Write unit tests for binary
    - Test binary execution
    - Test command availability
    - Test version output
    - _Requirements: 11.2, 11.3, 11.4_

- [x] 22. Integration and end-to-end testing
  - [x] 22.1 Write integration test for full build with component manifest
    - Initialize component manifest
    - Add components
    - Scan repositories
    - Generate Zarf manifest
    - Execute full build
    - Verify package creation
    - Verify artifact manifest generation
    - _Requirements: 5.7, 6.1, 13.7, 14.1_

  - [x] 22.2 Write integration test for resume
    - Start build
    - Simulate failure mid-build
    - Resume build
    - Verify skipped steps
    - Verify completion
    - _Requirements: 4.3, 4.4_

  - [x] 22.3 Write integration test for deployment
    - Deploy package
    - Verify registry serving images
    - Verify git server serving repos
    - Verify nginx serving files
    - _Requirements: 9.3, 9.4, 9.6_

  - [x] 22.4 Write integration test for package verification
    - Build package
    - Verify with artifact manifest
    - Tamper with package
    - Verify detection of tampering
    - _Requirements: 15.3, 15.4, 15.5_

- [x] 23. Documentation and examples
  - Create README.md with usage examples
  - Document CLI commands and flags
  - Document component manifest schema
  - Add troubleshooting guide
  - Create example components.yaml
  - Document migration from bash scripts
  - Document manifest taxonomy (Component, Zarf, Artifact)
  - Delete stale and outdated documents

- [x] 24. Final checkpoint - Complete verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- Maintain backward compatibility throughout implementation
- New features: Component manifest management, manifest generation, package verification
