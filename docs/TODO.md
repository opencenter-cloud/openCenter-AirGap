# TODO: Future Improvements

## Image List Generation

### Long-term Enhancements

#### 1. Scan Result Caching
**Priority:** Medium
**Effort:** 2-3 days

Cache scan results with repository commit SHA to avoid re-scanning unchanged repos.

**Implementation:**
- Store scan results in `build/repository-scans/.cache/`
- Key format: `{repo_name}-{commit_sha}.json`
- Check git HEAD SHA before scanning
- Invalidate cache on SHA mismatch

**Benefits:**
- Faster incremental builds (skip unchanged repos)
- Reduced CI/CD pipeline time
- Lower disk I/O during development

**Risks:**
- Cache invalidation complexity
- Disk space growth (need cleanup strategy)

---

#### 2. Dry-Run Mode
**Priority:** High
**Effort:** 1 day

Add `--dry-run` flag to preview changes without modifying files.

**Implementation:**
```bash
./scripts/build/generate_image_lists.sh --dry-run
```

**Output:**
- Show which files would be created/updated
- Display diff of changes
- Report new/removed images
- No filesystem modifications

**Use cases:**
- Pre-commit validation
- CI/CD preview in PRs
- Safe testing of configuration changes

---

#### 3. Incremental Scanning
**Priority:** Low
**Effort:** 3-5 days

Scan only changed files since last run using git diff.

**Implementation:**
- Track last scan timestamp per repo
- Use `git diff --name-only` to find changed files
- Merge new results with cached results
- Full scan fallback if cache missing

**Benefits:**
- Sub-second scans for small changes
- Real-time feedback during development
- Reduced resource usage

**Challenges:**
- Handling deleted files
- Merge conflicts in results
- Initial implementation complexity

---

#### 4. Parallel Repository Scanning
**Priority:** Medium
**Effort:** 2 days

Scan multiple repositories concurrently using multiprocessing.

**Implementation:**
```python
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(scan_repo, repo) for repo in repos]
    results = [f.result() for f in futures]
```

**Benefits:**
- 2-4x faster on multi-core systems
- Better resource utilization
- Scales with CPU count

**Considerations:**
- Thread-safe logging
- Memory usage (multiple repos in RAM)
- Error handling across processes

---

#### 5. Image Vulnerability Pre-Check
**Priority:** Low
**Effort:** 3-4 days

Integrate Trivy scanning during image list generation to flag vulnerable images early.

**Implementation:**
- Optional `--check-vulnerabilities` flag
- Query Trivy database for each discovered image
- Report HIGH/CRITICAL CVEs
- Generate vulnerability report

**Benefits:**
- Early detection of vulnerable images
- Shift-left security
- Automated compliance checks

**Dependencies:**
- Trivy installed
- Internet access (or local Trivy DB)
- Significant performance impact

---

#### 6. Smart Deduplication
**Priority:** Low
**Effort:** 2 days

Detect and consolidate equivalent image references.

**Examples:**
```
docker.io/nginx:1.21 == nginx:1.21
quay.io/repo/image:latest == quay.io/repo/image:v1.2.3 (if latest points to v1.2.3)
```

**Implementation:**
- Normalize all images to full registry format
- Query registry APIs for tag resolution
- Create equivalence map
- Deduplicate based on digest

**Challenges:**
- Requires registry access
- API rate limiting
- Mutable tags (latest, stable)

---

#### 7. Configuration-Driven Scanning
**Priority:** Medium
**Effort:** 2-3 days

Move repository configuration to YAML for easier customization.

**Example config:**
```yaml
repositories:
  - name: kubespray
    path: assets/kubespray/kubespray-master
    enabled: true
    scan_patterns:
      - "**/*.yaml"
      - "**/*.yml"
    exclude_patterns:
      - "**/tests/**"
      - "**/.git/**"

  - name: opencenter-gitops-base
    path: assets/opencenter-gitops-base
    enabled: true
    custom_patterns:
      - 'image:\s*(?P<image>[\w\-\.:/]+)'
```

**Benefits:**
- User customization without code changes
- Per-repo scan configuration
- Easy addition of new repos
- Pattern overrides for special cases

---

#### 8. Continuous Monitoring
**Priority:** Low
**Effort:** 5-7 days

Watch repositories for changes and auto-regenerate lists.

**Implementation:**
- File system watcher (inotify/fswatch)
- Debounce changes (wait 5s after last change)
- Auto-run scan on detected changes
- Desktop notifications on completion

**Use cases:**
- Development workflow
- Real-time GitOps sync
- Automated CI triggers

**Considerations:**
- Resource usage (always running)
- False positives from IDE/editor
- Platform-specific implementations

---

## General Build System

### 9. Build Artifact Signing
**Priority:** High
**Effort:** 3-4 days

Sign all generated image lists with GPG/Cosign for supply chain security.

**Implementation:**
- Generate detached signatures for each list
- Store public keys in repository
- Verify signatures before use
- Integrate with existing Zarf signing

---

### 10. SBOM Generation for Image Lists
**Priority:** Medium
**Effort:** 2-3 days

Generate SBOM (SPDX/CycloneDX) for discovered images.

**Output:**
```json
{
  "bomFormat": "CycloneDX",
  "components": [
    {
      "type": "container",
      "name": "nginx",
      "version": "1.21.0",
      "purl": "pkg:docker/nginx@1.21.0"
    }
  ]
}
```

---

## Documentation

### 11. Video Walkthrough
**Priority:** Low
**Effort:** 1 day

Create screencast demonstrating:
- Initial setup
- Running scans
- Interpreting results
- Troubleshooting common issues

---

### 12. Architecture Decision Records (ADRs)
**Priority:** Medium
**Effort:** Ongoing

Document key decisions:
- Why regex-based scanning vs AST parsing
- Repository structure choices
- Performance vs accuracy trade-offs

---

## Testing

### 13. Property-Based Testing
**Priority:** Medium
**Effort:** 3-4 days

Use Hypothesis to generate test cases:
- Random YAML structures
- Edge case image formats
- Malformed input handling

---

### 14. Performance Benchmarking
**Priority:** Low
**Effort:** 2 days

Automated benchmarks tracking:
- Scan duration over time
- Memory usage
- Disk I/O patterns
- Regression detection

---

## Notes

- Priorities: High (next sprint), Medium (next quarter), Low (backlog)
- Effort estimates assume single developer
- Dependencies and blockers noted per item
- Review quarterly and reprioritize based on user feedback
