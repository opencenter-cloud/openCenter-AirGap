# Implementation Tasks: Workflow Simplification

## Overview

Implement simplified workflow where `versions.env` is the single source of truth, with automatic component manifest generation during build and enhanced scanning capabilities.

## Tasks

- [x] 1. Build command auto-generation
  - [x] 1.1 Implement `should_regenerate_manifest()` function
    - Check if `components.yaml` exists
    - Compare mtimes of `versions.env` and `components.yaml`
    - Handle `--force-regenerate` flag
    - _Requirements: 2.2, 2.3, 6.2_

  - [x] 1.2 Implement `merge_manifests()` function
    - Preserve additional images from existing manifest
    - Preserve additional charts from existing manifest
    - Preserve custom tools from existing manifest
    - Use generated versions for all standard components
    - _Requirements: 2.5, 4.3_

  - [x] 1.3 Update `build` command to auto-generate manifest
    - Validate `versions.env` exists before proceeding
    - Call `should_regenerate_manifest()` to determine action
    - Generate manifest from `versions.env` if needed
    - Merge with existing manifest if present
    - Display message when regenerating
    - _Requirements: 2.1, 2.2, 2.4_

  - [x] 1.4 Add `--force-regenerate` flag to build command
    - Override existing `components.yaml`
    - Display warning about losing manual edits
    - _Requirements: 6.4_

  - [x] 1.5 Write unit tests for manifest regeneration logic
    - Test `should_regenerate_manifest()` with various scenarios
    - Test `merge_manifests()` preserves manual edits
    - Test mtime comparison logic
    - _Requirements: 2.2, 2.3, 2.5_

- [x] 2. Component manifest metadata
  - [x] 2.1 Add metadata to `write_manifest()` function
    - Add generation timestamp
    - Add source file reference
    - Add tool version
    - Add header comment explaining auto-generation
    - _Requirements: 2.6, 4.5_

  - [x] 2.2 Update `ComponentManifest.to_dict()` to include metadata
    - Add `_generated` section with metadata
    - Preserve metadata on round-trip
    - _Requirements: 4.5_

- [x] 3. Repository extraction from versions.env
  - [x] 3.1 Implement `extract_repos_from_versions()` function
    - Parse `KUBESPRAY_VERSION` and create repo spec
    - Parse `OPENCENTER_GITOPS_BASE_REPO` and create repo spec
    - Handle missing fields gracefully
    - Return list of `RepoSpec` objects
    - _Requirements: 5.2, 3.2_

  - [x] 3.2 Create `RepoSpec` dataclass
    - Fields: name, url, ref
    - Validation for required fields
    - _Requirements: 3.2_

  - [x] 3.3 Write unit tests for repo extraction
    - Test with complete versions.env
    - Test with missing fields
    - Test with multiple repos
    - _Requirements: 5.2_

- [x] 4. Repository cloning functionality
  - [x] 4.1 Implement `clone_repository()` function
    - Check if repo already exists in `build/`
    - Clone with `git clone --depth 1 --branch <ref>`
    - Handle clone errors gracefully
    - Display progress messages
    - _Requirements: 3.2, 3.8_

  - [x] 4.2 Write unit tests for repository cloning
    - Test successful clone
    - Test skip if exists
    - Test error handling
    - _Requirements: 3.2, 3.8_

- [x] 5. Helm chart scanning
  - [x] 5.1 Implement `HelmChartScanner` class
    - Scan repositories for `Chart.yaml` files
    - Parse chart metadata (name, version)
    - Return list of `ChartComponent` objects
    - Handle parse errors gracefully
    - _Requirements: 3.4_

  - [x] 5.2 Implement `_parse_chart_yaml()` method
    - Load YAML from `Chart.yaml`
    - Extract name and version
    - Create `ChartComponent` with local path
    - _Requirements: 3.4_

  - [x] 5.3 Write unit tests for chart scanning
    - Test with valid Chart.yaml files
    - Test with invalid YAML
    - Test with missing fields
    - Test multiple charts in repo
    - _Requirements: 3.4_

- [x] 6. Enhanced scan command
  - [x] 6.1 Add `--repos` flag to scan command
    - Boolean flag to enable repo cloning
    - Defaults to False
    - _Requirements: 3.1_

  - [x] 6.2 Update scan command to clone repos
    - Load `versions.env`
    - Extract repo specs
    - Clone each repo to `build/`
    - Display progress
    - _Requirements: 3.1, 3.2_

  - [x] 6.3 Update scan command to discover charts
    - Create `HelmChartScanner` instance
    - Scan cloned repos
    - Collect discovered charts
    - _Requirements: 3.4_

  - [x] 6.4 Update scan command to update manifest
    - Load existing `components.yaml` or create new
    - Add discovered images to `images.additional`
    - Add discovered charts to `charts`
    - Avoid duplicates
    - Write updated manifest
    - _Requirements: 3.5, 3.6_

  - [x] 6.5 Add scan summary display
    - Show count of discovered images
    - Show count of discovered charts
    - Show count of cloned repos
    - _Requirements: 3.7_

  - [x] 6.6 Write unit tests for enhanced scan command
    - Test `--repos` flag behavior
    - Test manifest update logic
    - Test duplicate detection
    - _Requirements: 3.1, 3.5, 3.6_

- [x] 7. Backward compatibility
  - [x] 7.1 Test existing `components.yaml` files work
    - Load existing manifest without versions.env
    - Build with existing manifest
    - Verify no regeneration if manifest is newer
    - _Requirements: 6.1, 6.2_

  - [x] 7.2 Add warning for stale manifests
    - Detect when `versions.env` is newer than `components.yaml`
    - Display warning message
    - Suggest regeneration
    - _Requirements: 6.3_

  - [x] 7.3 Write integration tests for backward compatibility
    - Test with pre-existing `components.yaml`
    - Test with stale `components.yaml`
    - Test with manual edits
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Documentation updates
  - [x] 8.1 Update README.md with new workflow
    - Replace old workflow with new 3-step process
    - Update quick start guide
    - Update CLI commands section
    - _Requirements: 7.1_

  - [x] 8.2 Update CLI command reference
    - Document `build --force-regenerate` flag
    - Document `scan --repos` flag
    - Update command examples
    - _Requirements: 7.2_

  - [x] 8.3 Create migration guide
    - Document changes for existing users
    - Explain backward compatibility
    - Provide migration examples
    - _Requirements: 7.3_

- [x] 9. Integration testing
  - [x] 9.1 Write end-to-end workflow test
    - Test: init → edit → build → scan
    - Verify manifest generation
    - Verify repo cloning
    - Verify chart discovery
    - _Requirements: All_

  - [x] 9.2 Write customization workflow test
    - Test: build → add custom component → rebuild
    - Verify custom components preserved
    - Verify versions updated from versions.env
    - _Requirements: 2.5, 4.3_

  - [x] 9.3 Write force regeneration test
    - Test: build → manual edit → build --force-regenerate
    - Verify manual edits lost
    - Verify clean regeneration
    - _Requirements: 6.4_

## Notes

- Each task references specific requirements for traceability
- Unit tests should be written alongside implementation
- Integration tests validate end-to-end workflows
- Maintain backward compatibility throughout implementation
- Focus on clean, testable code with single responsibility
