# Design: Workflow Simplification

## Architecture

### Component Relationships

```
versions.env (source of truth)
    ↓
create_default_manifest()
    ↓
components.yaml (generated)
    ↓
ZarfGenerator
    ↓
zarf.yaml (generated)
```

### Workflow States

1. **Fresh Init**: No `versions.env`, no `components.yaml`
2. **Configured**: `versions.env` exists, no `components.yaml`
3. **Generated**: Both exist, `components.yaml` auto-generated
4. **Customized**: Both exist, `components.yaml` manually edited
5. **Scanned**: Repos cloned, images/charts discovered

## Implementation Design

### 1. Init Command

**Current State:**
```python
def init(template, config_file):
    create_directories()
    create_default_versions_env(config_file, template)
    display_next_steps()
```

**Changes:**
- Remove `--create-manifest` flag
- Remove manifest creation logic
- Update next steps message

**No code changes needed** - already implemented correctly.

### 2. Build Command

**Current State:**
```python
def build(config_file, ...):
    load_config(config_file)
    load_component_manifest()  # Expects manifest to exist
    generate_zarf_manifest()
    execute_build_steps()
```

**New Design:**
```python
def build(config_file, force_regenerate=False, ...):
    # 1. Validate versions.env exists
    if not config_file.exists():
        error("versions.env not found")

    # 2. Auto-generate or regenerate components.yaml
    manifest_path = Path("config/components.yaml")
    should_regenerate = (
        force_regenerate or
        not manifest_path.exists() or
        config_file.stat().st_mtime > manifest_path.stat().st_mtime
    )

    if should_regenerate:
        console.print("Generating components.yaml from versions.env...")
        manifest = create_default_manifest(versions_env=config_file)

        # Merge with existing if present
        if manifest_path.exists() and not force_regenerate:
            existing = read_manifest(manifest_path)
            manifest = merge_manifests(existing, manifest)

        write_manifest(manifest, manifest_path)

    # 3. Load manifest and continue build
    manifest = read_manifest(manifest_path)
    config = BuildConfig.from_env_file(config_file)

    # 4. Generate zarf.yaml
    generator = ZarfGenerator(config)
    generator.generate()

    # 5. Execute build steps
    orchestrator.execute()
```

**Key Functions:**

```python
def should_regenerate_manifest(
    versions_env: Path,
    manifest: Path,
    force: bool
) -> bool:
    """Determine if components.yaml should be regenerated."""
    if force:
        return True
    if not manifest.exists():
        return True
    if versions_env.stat().st_mtime > manifest.stat().st_mtime:
        return True
    return False

def merge_manifests(
    existing: ComponentManifest,
    generated: ComponentManifest
) -> ComponentManifest:
    """Merge existing manual edits with generated manifest.

    Strategy:
    - Use generated versions for all components
    - Preserve additional images/charts from existing
    - Preserve custom tools not in generated
    """
    merged = generated

    # Preserve additional images
    existing_images = set(existing.images.additional)
    generated_images = set(generated.images.additional)
    additional = existing_images - generated_images
    merged.images.additional.extend(sorted(additional))

    # Preserve additional charts
    existing_chart_names = {c.name for c in existing.charts}
    generated_chart_names = {c.name for c in generated.charts}
    for chart in existing.charts:
        if chart.name not in generated_chart_names:
            merged.charts.append(chart)

    # Preserve custom tools
    existing_tool_names = {t.name for t in existing.tools}
    generated_tool_names = {t.name for t in generated.tools}
    for tool in existing.tools:
        if tool.name not in generated_tool_names:
            merged.tools.append(tool)

    return merged
```

### 3. Scan Command Enhancement

**Current State:**
```python
def scan(repos, discover_images, ...):
    if discover_images:
        load_manifest()
        scan_repos_from_manifest()
    elif repos:
        scan_explicit_repos(repos)
```

**New Design:**
```python
def scan(
    repos: Optional[list[Path]] = None,
    clone_repos: bool = False,
    discover_images: bool = True,
    discover_charts: bool = True,
    update_manifest: bool = True,
    ...
):
    """Scan repositories for container images and Helm charts.

    Args:
        repos: Explicit repo paths to scan
        clone_repos: Clone repos from versions.env before scanning
        discover_images: Discover container images
        discover_charts: Discover Helm charts
        update_manifest: Update components.yaml with discoveries
    """

    # 1. Clone repos if requested
    if clone_repos:
        versions_env = Path("config/versions.env")
        if not versions_env.exists():
            error("versions.env not found")

        versions = parse_versions_env(versions_env)
        repos_to_clone = extract_repos_from_versions(versions)

        for repo_spec in repos_to_clone:
            clone_repository(repo_spec)

    # 2. Determine repos to scan
    repos_to_scan = repos or discover_repos_in_build()

    # 3. Scan for images
    discovered_images = set()
    if discover_images:
        scanner = RepositoryScanner(repos=repos_to_scan)
        results = scanner.scan_all()
        for images in results.values():
            discovered_images.update(images)

    # 4. Scan for charts
    discovered_charts = []
    if discover_charts:
        chart_scanner = HelmChartScanner(repos=repos_to_scan)
        discovered_charts = chart_scanner.scan_all()

    # 5. Update manifest
    if update_manifest:
        manifest_path = Path("config/components.yaml")
        if manifest_path.exists():
            manifest = read_manifest(manifest_path)
        else:
            manifest = ComponentManifest()

        # Add discovered images
        for image in discovered_images:
            if image not in manifest.images.additional:
                manifest.images.additional.append(image)

        # Add discovered charts
        for chart in discovered_charts:
            if not any(c.name == chart.name for c in manifest.charts):
                manifest.charts.append(chart)

        write_manifest(manifest, manifest_path)

    # 6. Display summary
    display_scan_summary(discovered_images, discovered_charts)
```

**New Functions:**

```python
def extract_repos_from_versions(versions: dict[str, str]) -> list[RepoSpec]:
    """Extract repository specifications from versions.env.

    Looks for patterns:
    - KUBESPRAY_VERSION + KUBESPRAY_COMMIT_SHA
    - *_REPO + *_VERSION + *_COMMIT_SHA
    """
    repos = []

    # Kubespray
    if "KUBESPRAY_VERSION" in versions:
        repos.append(RepoSpec(
            name="kubespray",
            url="https://github.com/kubernetes-sigs/kubespray.git",
            ref=versions["KUBESPRAY_VERSION"]
        ))

    # openCenter GitOps
    if "OPENCENTER_GITOPS_BASE_REPO" in versions:
        repos.append(RepoSpec(
            name="opencenter-gitops-base",
            url=versions["OPENCENTER_GITOPS_BASE_REPO"],
            ref=versions.get("OPENCENTER_GITOPS_BASE_VERSION", "main")
        ))

    return repos

def clone_repository(repo_spec: RepoSpec) -> Path:
    """Clone repository to build/ directory.

    Args:
        repo_spec: Repository specification

    Returns:
        Path to cloned repository
    """
    repo_path = Path("build") / repo_spec.name

    if repo_path.exists():
        console.print(f"Repository already exists: {repo_path}")
        return repo_path

    console.print(f"Cloning {repo_spec.url}...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", repo_spec.ref, repo_spec.url, str(repo_path)],
        check=True
    )

    return repo_path

class HelmChartScanner:
    """Scanner for discovering Helm charts in repositories."""

    def scan_all(self) -> list[ChartComponent]:
        """Scan all repositories for Helm charts.

        Looks for:
        - Chart.yaml files
        - values.yaml files
        - Extracts chart name and version
        """
        charts = []

        for repo in self.repos:
            for chart_yaml in repo.rglob("Chart.yaml"):
                chart = self._parse_chart_yaml(chart_yaml)
                if chart:
                    charts.append(chart)

        return charts

    def _parse_chart_yaml(self, path: Path) -> Optional[ChartComponent]:
        """Parse Chart.yaml and extract metadata."""
        try:
            data = yaml.safe_load(path.read_text())
            return ChartComponent(
                name=data["name"],
                version=data["version"],
                repo=str(path.parent),  # Local path
                path=str(path.parent.relative_to(self.repo_root))
            )
        except Exception:
            return None
```

### 4. Component Manifest Metadata

**Add metadata to generated manifests:**

```python
def write_manifest(manifest: ComponentManifest, path: Path) -> None:
    """Write component manifest with metadata header."""

    # Generate YAML
    data = manifest.to_dict()

    # Add metadata
    metadata = {
        "_generated": {
            "timestamp": datetime.now().isoformat(),
            "source": "config/versions.env",
            "tool": "opencenter-airgap",
            "note": "This file is auto-generated. Manual edits are preserved during regeneration."
        }
    }

    # Merge metadata
    data = {**metadata, **data}

    # Write with header comment
    path.parent.mkdir(parents=True, exist_ok=True)

    header = """# Component Manifest
# Auto-generated from config/versions.env
# Manual edits are preserved during regeneration
# To regenerate: python3 -m opencenter_build.cli build --force-regenerate

"""

    content = yaml.dump(data, default_flow_style=False, sort_keys=False)
    path.write_text(header + content)
```

## File Structure

```
config/
  versions.env          # Source of truth (user edits)
  components.yaml       # Generated (auto-created by build)

build/
  kubespray/           # Cloned by scan --repos
  opencenter-gitops-base/  # Cloned by scan --repos

dist/
  artifact-manifest.json
  zarf.yaml            # Generated by build
```

## Command Flow

### Happy Path

```bash
# 1. Init
$ opencenter-airgap init
✓ Created config/versions.env
Next: Edit config/versions.env

# 2. Edit
$ vim config/versions.env

# 3. Build
$ opencenter-airgap build
✓ Generating components.yaml from versions.env
✓ Generated zarf.yaml
✓ Build complete

# 4. Optional: Scan
$ opencenter-airgap scan --repos
✓ Cloning kubespray...
✓ Cloning opencenter-gitops-base...
✓ Discovered 247 images
✓ Discovered 12 charts
✓ Updated components.yaml
```

### With Customization

```bash
# After build, manually add custom image
$ opencenter-airgap add image custom-registry.io/app:v1.0
✓ Added image to components.yaml

# Rebuild preserves custom additions
$ opencenter-airgap build
✓ Regenerating components.yaml (versions.env updated)
✓ Preserved 1 custom image
✓ Build complete
```

## Testing Strategy

1. **Unit tests**: Test merge logic, repo extraction, chart scanning
2. **Integration tests**: Test full workflow (init → edit → build → scan)
3. **Property tests**: Test merge preserves manual edits
4. **Regression tests**: Ensure existing workflows still work

## Migration Path

For existing users with `components.yaml`:

1. Run `build` - detects existing manifest, uses it
2. Update `versions.env` - next `build` regenerates and merges
3. Or use `--force-regenerate` to start fresh

No breaking changes for existing users.
