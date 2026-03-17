# Design Document: Python Build Improvements

## Overview

The Python build improvements introduce a hybrid architecture combining Python orchestration with Zarf native capabilities. The design replaces sequential bash scripts with concurrent Python execution, reduces build time by 4x, and provides checkpoint/resume capability for build resilience.

Core improvements:
- Concurrent repository scanning (8.5min → 2.1min)
- Modern CLI with Typer and Rich
- State persistence with checkpoint/resume
- Automatic Zarf package generation
- Comprehensive artifact manifests
- Structured logging and metrics

The system maintains backward compatibility by preserving existing file formats and directory structures while gradually replacing bash scripts with Python and Zarf components.

## Architecture

### Component Diagram

```
            ┌─────────────────────────────────────────────────────────────┐
            │                     CLI Layer (Typer)                       │
            │  Commands: init, scan, build, serve, validate, status       │
            └────────────────────┬────────────────────────────────────────┘
                                 │
            ┌────────────────────▼───────────────────────────────────────┐
            │                Build Orchestrator                          │
            │  - Step execution with checkpoints                         │
            │  - State management                                        │
            │  - Error handling and rollback                             │
            └─┬──────────┬──────────┬──────────┬──────────┬──────────────┘
              │          │          │          │          │
              ▼          ▼          ▼          ▼          ▼
            ┌───────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌──────────┐
            │Scanner│ │Asset │ │Zarf    │ │Manifest│ │Metrics   │
            │       │ │Coll. │ │Gen.    │ │Gen.    │ │Exporter  │
            └───────┘ └──────┘ └────────┘ └────────┘ └──────────┘
                │         │         │          │          │
                ▼         ▼         ▼          ▼          ▼
            ┌─────────────────────────────────────────────────────┐
            │              File System / State Store              │
            │  - config/versions.env                              │
            │  - build/state.json                                 │
            │  - dist/zarf-package-*.tar.zst                      │
            │  - dist/artifact-manifest.{json,md}                 │
            └─────────────────────────────────────────────────────┘
```

### Build Pipeline

```
Phase 1: Initialization
  ├─ Load config/versions.env
  ├─ Validate configuration
  └─ Initialize state manager

Phase 2: Asset Discovery
  ├─ Scan repositories (concurrent)
  ├─ Discover container images
  └─ Write config/all-images.txt

Phase 3: Asset Collection
  ├─ Execute kubespray-offline (bash)
  ├─ Collect OS packages → build/kubespray-offline/outputs/debs/
  ├─ Collect PyPI mirror → build/kubespray-offline/outputs/pypi/
  └─ Collect K8s binaries → build/kubespray-offline/outputs/files/

Phase 4: Asset Organization
  ├─ Copy to assets/ directory
  ├─ Organize by type (images, files, debs, pypi)
  └─ Generate checksums

Phase 5: Zarf Package Creation
  ├─ Generate zarf.yaml from versions.env
  ├─ Execute zarf package create
  └─ Output to dist/

Phase 6: Manifest Generation
  ├─ Inventory all artifacts
  ├─ Calculate sizes and checksums
  ├─ Export JSON manifest
  └─ Export Markdown summary
```

### Deployment Flow

```
Zone C (Air-Gapped):
  1. Transfer package → bastion:/opt/
  2. Execute: opencenter-airgap serve <package>
     ├─ zarf package deploy
     ├─ Start registry (Zarf init, port 31999)
     ├─ Start git server (Zarf init, port 3000)
     └─ Start nginx (Docker, port 80)
  3. Verify services
     ├─ curl http://localhost/files/
     ├─ curl http://localhost/debs/
     ├─ curl http://localhost/pypi/
     ├─ curl http://localhost:31999/v2/_catalog
     └─ curl http://localhost:3000/api/v1/repos/search
```

## Manifest Taxonomy

The build system uses three distinct manifests at different lifecycle stages:

### 1. Component Manifest (Input)

**File**: `config/components.yaml`
**Phase**: Pre-build (Zone A)
**Purpose**: Declarative specification of what to collect
**Owner**: Platform engineer (manually edited)

```yaml
# Core Kubernetes components
kubernetes:
  version: "1.34.3"
  binaries:
    - name: kubectl
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubectl"
    - name: kubelet
      url: "https://dl.k8s.io/v{{version}}/bin/linux/amd64/kubelet"

# Additional CLI tools
tools:
  - name: k9s
    version: "0.32.4"
    url: "https://github.com/derailed/k9s/releases/download/v{{version}}/k9s_Linux_amd64.tar.gz"
    extract: true
    binary: k9s

  - name: helm
    version: "3.14.0"
    url: "https://get.helm.sh/helm-v{{version}}-linux-amd64.tar.gz"
    extract: true
    binary: linux-amd64/helm

# Git repositories
repositories:
  - name: opencenter-gitops-base
    url: "https://github.com/opencenter-cloud/opencenter-gitops-base.git"
    ref: "v1.0.0"

  - name: kubespray
    url: "https://github.com/kubernetes-sigs/kubespray.git"
    ref: "master"

# Container images (discovered from repos + explicit additions)
images:
  auto_discover:
    - source: repositories.kubespray
      patterns:
        - "roles/*/defaults/main.yml"
        - "inventory/*/group_vars/*.yml"

  additional:
    - "docker.io/grafana/grafana:10.2.0"
    - "quay.io/prometheus/prometheus:v2.48.0"

# Helm charts
charts:
  - name: cert-manager
    repo: "https://charts.jetstack.io"
    version: "v1.13.0"

  - name: ingress-nginx
    repo: "https://kubernetes.github.io/ingress-nginx"
    version: "4.8.3"
```

**Characteristics**:
- Templates with `{{version}}` placeholders
- Auto-discovery directives
- No checksums (URLs not yet fetched)
- Human-readable, version-controlled

### 2. Zarf Manifest (Build Instructions)

**File**: `zarf.yaml`
**Phase**: Build (Zone A)
**Purpose**: Zarf package definition - how to collect and bundle
**Owner**: Generated by `opencenter-airgap generate-manifest`

Generated from components.yaml with:
- Templates resolved
- Auto-discovery expanded
- Full image list (115 images)
- Zarf-native format

### 3. Artifact Manifest (Output Inventory)

**File**: `dist/artifact-manifest.json` + `dist/artifact-manifest.md`
**Phase**: Post-build (Zone A) / Pre-deploy (Zone B/C)
**Purpose**: Cryptographic inventory of what was actually collected
**Owner**: Generated by `opencenter-airgap build`

Contains:
- SHA256 checksums for every artifact
- Actual sizes (bytes collected)
- Resolved Git commit SHAs
- Image digests (immutable content-addressable IDs)
- Collection timestamps

### Manifest Comparison

| Aspect | Component Manifest | Zarf Manifest | Artifact Manifest |
|--------|-------------------|---------------|-------------------|
| **File** | `config/components.yaml` | `zarf.yaml` | `dist/artifact-manifest.json` |
| **Format** | YAML (custom schema) | YAML (Zarf schema) | JSON |
| **Purpose** | Declare what to collect | Instruct Zarf how to build | Inventory what was collected |
| **Audience** | Platform engineer | Zarf CLI | Security officer, auditor |
| **Lifecycle** | Pre-build (input) | Build (instructions) | Post-build (output) |
| **Mutability** | Version-controlled, edited | Generated, ephemeral | Immutable, signed |
| **Hashes** | None | None | SHA256 for every artifact |
| **Git refs** | Branch names (`master`) | Branch names | Commit SHAs (`a1b2c3d4...`) |
| **Images** | Discovery directives | Full list (115 images) | Full list + digests |

## Components and Interfaces

### ComponentManifest

Manages declarative component specifications.

```python
@dataclass
class ToolSpec:
    """CLI tool specification."""
    name: str
    version: str
    url: str
    extract: bool = False
    binary: str | None = None
    checksum_url: str | None = None

@dataclass
class RepositorySpec:
    """Git repository specification."""
    name: str
    url: str
    ref: str
    type: str = "git"

@dataclass
class ImageDiscoverySpec:
    """Image auto-discovery specification."""
    source: str  # e.g., "repositories.kubespray"
    patterns: list[str]

@dataclass
class ComponentManifest:
    """Complete component manifest."""
    kubernetes: dict  # version, binaries
    tools: list[ToolSpec]
    repositories: list[RepositorySpec]
    images: dict  # auto_discover, additional
    charts: list[dict]
    os_packages: dict
    python_packages: dict
    terraform_providers: list[dict]

    @classmethod
    def from_yaml(cls, path: Path) -> "ComponentManifest":
        """Load from config/components.yaml."""
        pass

    def add_tool(self, tool: ToolSpec) -> None:
        """Add tool to manifest."""
        pass

    def add_repository(self, repo: RepositorySpec) -> None:
        """Add repository to manifest."""
        pass

    def add_image(self, image: str) -> None:
        """Add explicit image to manifest."""
        pass

    def save(self, path: Path) -> None:
        """Save manifest to YAML."""
        pass

class ComponentManifestManager:
    """Manages component manifest operations."""

    def __init__(self, manifest_path: Path = Path("config/components.yaml")):
        self.manifest_path = manifest_path

    def init(self, template: str | None = None) -> ComponentManifest:
        """Initialize new component manifest from template."""
        pass

    def validate(self, check_upstream: bool = False) -> list[str]:
        """
        Validate component manifest.

        Args:
            check_upstream: Verify URLs are reachable

        Returns:
            List of validation errors (empty if valid)
        """
        pass

    def discover_images(self, manifest: ComponentManifest) -> list[str]:
        """
        Discover images from repositories.

        Returns:
            List of discovered image references
        """
        pass
```

**Interface:**
- Input: YAML file with component specifications
- Output: Structured component manifest
- Operations: add, validate, discover

### ManifestGenerator

Generates Zarf manifest from component manifest.

```python
class ManifestGenerator:
    """Generates Zarf manifest from component manifest."""

    def __init__(self, component_manifest: ComponentManifest):
        self.component_manifest = component_manifest

    def generate(self, output: Path = Path("zarf.yaml")) -> None:
        """
        Generate zarf.yaml from component manifest.

        Process:
        1. Resolve version templates ({{version}})
        2. Expand auto-discovery directives
        3. Create Zarf components
        4. Write zarf.yaml
        """
        pass

    def _resolve_templates(self, url: str, context: dict) -> str:
        """Resolve {{variable}} templates in URLs."""
        pass

    def _expand_discovery(self, spec: ImageDiscoverySpec) -> list[str]:
        """Expand image discovery directive to concrete image list."""
        pass
```

**Interface:**
- Input: ComponentManifest
- Output: zarf.yaml file
- Process: Template resolution → Discovery expansion → Zarf component generation

### PackageVerifier

Verifies package integrity and signatures.

```python
class PackageVerifier:
    """Verifies Zarf package integrity."""

    def verify(
        self,
        package_path: Path,
        manifest_path: Path | None = None
    ) -> VerificationResult:
        """
        Verify package integrity.

        Checks:
        1. Cosign signature validation
        2. Checksum verification
        3. Artifact manifest comparison (if provided)

        Returns:
            VerificationResult with success status and details
        """
        pass

    def _verify_signature(self, package_path: Path) -> bool:
        """Verify Cosign signature."""
        pass

    def _verify_checksums(self, package_path: Path) -> bool:
        """Verify internal checksums."""
        pass

    def _compare_manifest(
        self,
        package_path: Path,
        manifest: ArtifactManifest
    ) -> list[str]:
        """
        Compare artifact manifest against package contents.

        Returns:
            List of discrepancies (empty if match)
        """
        pass

@dataclass
class VerificationResult:
    """Package verification result."""
    success: bool
    signature_valid: bool
    checksums_valid: bool
    manifest_matches: bool
    errors: list[str]
    artifact_count: int
```

**Interface:**
- Input: Package path, optional manifest path
- Output: VerificationResult
- Checks: Signature, checksums, manifest comparison

### RepositoryScanner

Discovers container images in Git repositories using concurrent processing.

```python
class RepositoryScanner:
    """Concurrent repository scanner for container image discovery."""

    def __init__(
        self,
        repos: list[Path],
        max_workers: int | None = None,
        patterns: list[str] | None = None
    ):
        """
        Initialize scanner.

        Args:
            repos: List of repository paths to scan
            max_workers: Number of worker processes (default: cpu_count)
            patterns: Custom regex patterns for image detection
        """
        self.repos = repos
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.patterns = self._compile_patterns(patterns)

    def scan_all(self) -> dict[str, set[str]]:
        """
        Scan all repositories concurrently.

        Returns:
            Dictionary mapping repo paths to discovered images
        """
        pass

    def _scan_repo(self, repo: Path) -> dict[str, set[str]]:
        """Scan single repository (executed in worker process)."""
        pass

    @staticmethod
    @lru_cache(maxsize=None)
    def _compile_patterns(patterns: tuple[str, ...] | None) -> list[re.Pattern]:
        """Compile and cache regex patterns."""
        pass
```

**Interface:**
- Input: List of repository paths, optional worker count
- Output: Dictionary of discovered images by repository
- Performance: 4x faster than sequential (8.5min → 2.1min)

### StateManager

Persists build progress and enables checkpoint/resume.

```python
@dataclass
class StepCheckpoint:
    """Checkpoint for a single build step."""
    name: str
    status: StepStatus  # PENDING, RUNNING, COMPLETED, FAILED
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    artifacts: dict[str, str] | None = None

@dataclass
class BuildState:
    """Complete build state."""
    build_id: str
    start_time: datetime
    steps: list[StepCheckpoint]
    config_hash: str  # SHA256 of versions.env

class StateManager:
    """Manages build state persistence."""

    def __init__(self, state_file: Path = Path("build/state.json")):
        self.state_file = state_file

    def read(self) -> BuildState | None:
        """Read existing state from disk."""
        pass

    def write(self, state: BuildState) -> None:
        """Write state to disk atomically."""
        pass

    def update_step(self, step_name: str, checkpoint: StepCheckpoint) -> None:
        """Update single step checkpoint."""
        pass

    def find_resume_point(self, state: BuildState) -> int:
        """Find first incomplete step index."""
        pass
```

**Interface:**
- Input: State file path
- Output: BuildState object with step checkpoints
- Persistence: Atomic writes using temp file + rename

### BuildOrchestrator

Coordinates build pipeline execution with checkpoint/resume.

```python
class BuildOrchestrator:
    """Orchestrates build pipeline with state management."""

    def __init__(
        self,
        config: BuildConfig,
        state_mgr: StateManager,
        clean: bool = False
    ):
        self.config = config
        self.state_mgr = state_mgr
        self.clean = clean
        self.steps = [
            "scan_repositories",
            "collect_kubespray_offline",
            "mirror_terraform_providers",
            "organize_assets",
            "create_zarf_package",
            "generate_manifest"
        ]

    def execute(self, resume: bool = True) -> BuildResult:
        """
        Execute build pipeline.

        Args:
            resume: Resume from checkpoint if available

        Returns:
            BuildResult with success status and artifacts
        """
        pass

    def _execute_step(self, step_name: str) -> dict[str, str]:
        """Execute single step with checkpoint."""
        pass

    def _rollback_step(self, step_name: str) -> None:
        """Rollback failed step artifacts."""
        pass
```

**Interface:**
- Input: BuildConfig, StateManager, clean flag
- Output: BuildResult with artifact paths
- Error handling: Automatic rollback on failure

### ZarfGenerator

Generates zarf.yaml from versions.env configuration.

```python
class ZarfGenerator:
    """Generates Zarf package definition from configuration."""

    def __init__(self, config: BuildConfig):
        self.config = config

    def generate(self, output: Path = Path("zarf.yaml")) -> None:
        """
        Generate zarf.yaml from configuration.

        Args:
            output: Output path for zarf.yaml
        """
        pass

    def _create_images_component(self) -> dict:
        """Create component for container images."""
        pass

    def _create_charts_component(self) -> dict:
        """Create component for Helm charts."""
        pass

    def _create_repos_component(self) -> dict:
        """Create component for Git repositories."""
        pass

    def _create_files_component(self) -> dict:
        """Create component for binaries and packages."""
        pass

    def _create_actions_component(self) -> dict:
        """Create component for bastion service startup."""
        pass
```

**Interface:**
- Input: BuildConfig with versions and paths
- Output: zarf.yaml file
- Format: YAML with Zarf v0.32+ schema

### ManifestGenerator

Creates comprehensive artifact inventory.

```python
@dataclass
class ArtifactManifest:
    """Complete artifact inventory."""
    build_id: str
    timestamp: datetime

    # Artifact collections
    images: list[str]
    image_count: int
    image_total_size: int

    charts: list[dict]  # name, version, url
    chart_count: int

    repos: list[dict]  # url, ref, size
    repo_count: int

    binaries: list[dict]  # name, version, path, size, sha256
    binary_count: int
    binary_total_size: int

    os_packages: list[dict]  # name, version, arch
    os_package_count: int
    os_package_total_size: int

    pypi_packages: list[dict]  # name, version, type
    pypi_package_count: int
    pypi_package_total_size: int

    terraform_providers: list[dict]  # name, version, platform
    terraform_provider_count: int

    # Totals
    total_artifacts: int
    total_size: int

class ManifestGenerator:
    """Generates artifact manifests."""

    def generate(self, build_dir: Path) -> ArtifactManifest:
        """
        Generate manifest from build artifacts.

        Args:
            build_dir: Root build directory

        Returns:
            Complete artifact manifest
        """
        pass

    def export_json(self, manifest: ArtifactManifest, output: Path) -> None:
        """Export machine-readable JSON."""
        pass

    def export_markdown(self, manifest: ArtifactManifest, output: Path) -> None:
        """Export human-readable Markdown summary."""
        pass
```

**Interface:**
- Input: Build directory path
- Output: ArtifactManifest with complete inventory
- Exports: JSON (machine-readable), Markdown (human-readable)

### CLI

Modern command-line interface using Typer and Rich.

```python
app = typer.Typer(name="opencenter-airgap", help="Build tool for openCenter AirGap packages")
console = Console()

@app.command()
def init(
    create_manifest: bool = typer.Option(False, help="Create component manifest"),
    template: str = typer.Option(None, help="Template: baremetal, openstack"),
    config_file: Path = typer.Option("config/versions.env", help="Configuration file")
) -> None:
    """Initialize project configuration."""
    pass

@app.command()
def add(
    component_type: str = typer.Argument(..., help="Component type: tool, repo, image, chart"),
    name: str = typer.Argument(..., help="Component name"),
    version: str = typer.Option(None, help="Component version"),
    url: str = typer.Option(None, help="Component URL"),
    ref: str = typer.Option(None, help="Git ref (for repos)"),
    repo: str = typer.Option(None, help="Helm repo URL (for charts)")
) -> None:
    """Add component to manifest."""
    pass

@app.command()
def scan(
    repos: list[Path] = typer.Option(None, help="Repository paths to scan"),
    discover_images: bool = typer.Option(False, help="Discover images from repos"),
    concurrency: int = typer.Option(None, help="Number of worker processes"),
    verbose: bool = typer.Option(False, help="Enable verbose output")
) -> None:
    """Scan repositories for container images."""
    pass

@app.command()
def generate_manifest(
    output: Path = typer.Option("zarf.yaml", help="Output path for Zarf manifest")
) -> None:
    """Generate Zarf manifest from component manifest."""
    pass

@app.command()
def build(
    clean: bool = typer.Option(False, help="Clean build (ignore checkpoints)"),
    resume: bool = typer.Option(True, help="Resume from checkpoint"),
    verbose: bool = typer.Option(False, help="Enable verbose output")
) -> None:
    """Build air-gap package with all artifacts."""
    pass

@app.command()
def serve(
    package: Path = typer.Argument(..., help="Zarf package path"),
    verify: bool = typer.Option(True, help="Verify package signature")
) -> None:
    """Deploy package and start bastion services."""
    pass

@app.command()
def validate(
    strict: bool = typer.Option(False, help="Fail on warnings"),
    check_upstream: bool = typer.Option(False, help="Verify URLs are reachable"),
    config_file: Path = typer.Option("config/versions.env", help="Configuration file")
) -> None:
    """Validate configuration files and schemas."""
    pass

@app.command()
def verify(
    package: Path = typer.Argument(..., help="Package path to verify"),
    manifest: Path = typer.Option(None, help="Artifact manifest path for comparison")
) -> None:
    """Verify package integrity and signatures."""
    pass

@app.command()
def status() -> None:
    """Show current build status and progress."""
    pass

@app.command()
def clean() -> None:
    """Clean build artifacts and state."""
    pass
```

**Interface:**
- Framework: Typer for CLI, Rich for output
- Progress: Rich progress bars for long operations
- Output: Colored success/error indicators
- Logging: Structured JSON with --json flag

**New Commands:**
- `add`: Add components to manifest (tools, repos, images, charts)
- `generate-manifest`: Generate zarf.yaml from components.yaml
- `verify`: Verify package integrity and signatures

## Data Models

### BuildConfig

```python
@dataclass
class BuildConfig:
    """Build configuration loaded from versions.env."""

    # Kubernetes versions
    kubernetes_version: str
    containerd_version: str
    runc_version: str
    cni_version: str

    # Platform versions
    calico_version: str
    cert_manager_version: str
    ingress_nginx_version: str
    keycloak_version: str

    # Repository paths
    repos: list[Path]

    # Build settings
    max_workers: int
    output_dir: Path

    @classmethod
    def from_env_file(cls, path: Path) -> "BuildConfig":
        """Load configuration from versions.env."""
        pass

    def hash(self) -> str:
        """Generate SHA256 hash of configuration."""
        pass
```

### BuildResult

```python
@dataclass
class BuildResult:
    """Result of build execution."""
    success: bool
    build_id: str
    duration: timedelta
    package_path: Path | None
    manifest_path: Path | None
    error: str | None

    def summary(self) -> str:
        """Generate human-readable summary."""
        pass
```

### StepStatus

```python
class StepStatus(Enum):
    """Build step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

### FileMetadata

```python
@dataclass
class FileMetadata:
    """Metadata for a single file artifact."""
    path: Path
    size: int
    sha256: str
    mtime: datetime

    @classmethod
    def from_path(cls, path: Path) -> "FileMetadata":
        """Calculate metadata from file."""
        pass
```

### ImageMetadata

```python
@dataclass
class ImageMetadata:
    """Metadata for container image."""
    registry: str
    repository: str
    tag: str
    digest: str | None
    size: int | None

    @property
    def full_name(self) -> str:
        """Return full image name (registry/repo:tag)."""
        return f"{self.registry}/{self.repository}:{self.tag}"
```



## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Image Discovery Completeness

*For any* set of repositories containing container image references, scanning should discover all images that match the configured patterns.

**Validates: Requirements 1.4**

### Property 2: Encoding Error Resilience

*For any* file with invalid encoding, the file reader should handle the error gracefully without crashing and continue processing remaining files.

**Validates: Requirements 2.3**

### Property 3: State Persistence Round Trip

*For any* build step checkpoint, persisting to disk and reading back should produce an equivalent checkpoint with all fields preserved.

**Validates: Requirements 4.1, 4.5**

### Property 4: Failure State Capture

*For any* build step failure with an error message, the persisted state should contain the failure status, error message, and timestamp.

**Validates: Requirements 4.2**

### Property 5: Resume Skips Completed Steps

*For any* build state with completed steps, resuming the build should skip those steps and not re-execute them.

**Validates: Requirements 4.3**

### Property 6: Resume Starts at First Incomplete

*For any* build state with mixed step statuses (completed, failed, pending), resuming should start execution at the first non-completed step.

**Validates: Requirements 4.4**

### Property 7: Zarf Configuration Generation

*For any* valid BuildConfig, generating zarf.yaml should produce a valid Zarf package definition that includes all configured components.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

### Property 8: Manifest Completeness

*For any* artifact manifest, it should contain complete information for all artifact types: images (names, tags, sizes), charts (names, versions, URLs), repos (URLs, refs, sizes), binaries (names, versions, paths, sizes, checksums), OS packages (names, versions, architectures), PyPI packages (names, versions, types), and Terraform providers (names, versions, platforms).

**Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8**

### Property 9: Manifest Total Consistency

*For any* artifact manifest, the total artifact count should equal the sum of individual type counts, and the total size should equal the sum of individual type sizes.

**Validates: Requirements 6.9**

### Property 10: Manifest Serialization Round Trip

*For any* artifact manifest, serializing to JSON and deserializing back should produce an equivalent manifest with all fields preserved.

**Validates: Requirements 6.10**

### Property 11: Markdown Export Completeness

*For any* artifact manifest, the Markdown export should contain sections for all artifact types and include the summary table with counts and sizes.

**Validates: Requirements 6.11**

### Property 12: JSON Log Structure

*For any* log entry in JSON format, it should contain all required fields: timestamp, level, message, and trace_id.

**Validates: Requirements 7.2**

### Property 13: Metrics Completeness

*For any* completed build, the exported metrics should include build duration, success/failure status, per-step durations, and artifact counts by type.

**Validates: Requirements 8.2, 8.3, 8.4, 8.5**

### Property 14: Service Cleanup on Failure

*For any* service startup failure, the cleanup process should remove all partially deployed artifacts and containers.

**Validates: Requirements 9.5**

### Property 15: Configuration Validation Completeness

*For any* configuration with missing required variables or invalid repository paths, validation should detect and report all issues.

**Validates: Requirements 10.2, 10.4**

### Property 16: Backward Compatible Configuration Parsing

*For any* valid versions.env file from the bash-based system, the Python system should parse it successfully without modification.

**Validates: Requirements 12.1**

### Property 17: Output Path Compatibility

*For any* build execution, artifact output paths should match the paths used by the bash-based system.

**Validates: Requirements 12.2**

### Property 18: Directory Structure Preservation

*For any* build execution, the kubespray-offline directory structure should remain unchanged and match the expected layout.

**Validates: Requirements 12.3**

### Property 19: Bash Script Preservation

*For any* build execution, all bash scripts in the repository should remain unmodified (no deletions or changes).

**Validates: Requirements 12.5**

### Property 20: Component Manifest Validation

*For any* component manifest with missing required fields or invalid URLs, validation should detect and report all issues.

**Validates: Requirements 13.8**

### Property 21: Manifest Generation Completeness

*For any* valid component manifest, generating zarf.yaml should produce a Zarf manifest that includes all tools, repositories, images (discovered + explicit), and charts.

**Validates: Requirements 14.5**

### Property 22: Package Verification Correctness

*For any* valid package with matching artifact manifest, verification should succeed and report correct artifact count. For any tampered package or mismatched manifest, verification should fail with specific error details.

**Validates: Requirements 15.3, 15.4, 15.5**

## Error Handling

### Error Categories

**Configuration Errors:**
- Missing or invalid versions.env
- Missing required version variables
- Invalid repository paths
- Missing external dependencies (Zarf, Docker)

**Runtime Errors:**
- File I/O failures (permissions, disk space)
- Network failures during asset collection
- Process execution failures (kubespray-offline, Zarf)
- State corruption or lock conflicts

**Validation Errors:**
- Invalid Zarf package structure
- Missing expected artifacts
- Checksum mismatches
- Service health check failures

### Error Handling Strategy

**Fail Fast:**
- Configuration validation before build starts
- Dependency checks (Zarf, Docker) before execution
- Disk space checks before large downloads

**Graceful Degradation:**
- Continue scanning remaining repos if one fails
- Log errors but continue with partial results where safe
- Provide detailed error context for debugging

**Automatic Rollback:**
- Failed steps trigger cleanup of partial artifacts
- State manager marks step as failed with error details
- Resume capability allows retry from failure point

**User Feedback:**
- Clear error messages with actionable guidance
- Structured logs for programmatic analysis
- Exit codes: 0 (success), 1 (config error), 2 (runtime error), 3 (validation error)

### Error Recovery

```python
class BuildOrchestrator:
    def _execute_step(self, step_name: str) -> dict[str, str]:
        checkpoint = StepCheckpoint(name=step_name, status=StepStatus.RUNNING)
        checkpoint.start_time = datetime.now()

        try:
            # Execute step logic
            artifacts = self._run_step_logic(step_name)

            # Mark success
            checkpoint.status = StepStatus.COMPLETED
            checkpoint.artifacts = artifacts
            checkpoint.end_time = datetime.now()

            return artifacts

        except Exception as e:
            # Mark failure
            checkpoint.status = StepStatus.FAILED
            checkpoint.error = str(e)
            checkpoint.end_time = datetime.now()

            # Rollback partial artifacts
            self._rollback_step(step_name)

            # Log structured error
            logger.error(
                "Step failed",
                extra={
                    "step": step_name,
                    "error": str(e),
                    "trace_id": trace_context.get().get("trace_id")
                }
            )

            raise

        finally:
            # Always persist checkpoint
            self.state_mgr.update_step(step_name, checkpoint)
```

## Testing Strategy

### Dual Testing Approach

The testing strategy combines unit tests for specific examples and edge cases with property-based tests for universal correctness properties. Both approaches are complementary and necessary for comprehensive coverage.

**Unit Tests:**
- Specific examples demonstrating correct behavior
- Edge cases (empty inputs, boundary conditions)
- Error conditions and exception handling
- Integration points between components
- CLI command behavior and flag handling

**Property-Based Tests:**
- Universal properties across all inputs
- Comprehensive input coverage through randomization
- Invariant verification (totals, checksums, state consistency)
- Round-trip properties (serialization, state persistence)
- Backward compatibility verification

### Property-Based Testing Configuration

**Framework:** Hypothesis (Python property-based testing library)

**Configuration:**
- Minimum 100 iterations per property test
- Each test tagged with feature name and property number
- Tag format: `# Feature: python-build-improvements, Property N: <property_text>`

**Example Property Test:**

```python
from hypothesis import given, strategies as st
import pytest

# Feature: python-build-improvements, Property 3: State Persistence Round Trip
@given(
    step_name=st.text(min_size=1, max_size=50),
    status=st.sampled_from(StepStatus),
    error=st.one_of(st.none(), st.text()),
    artifacts=st.one_of(st.none(), st.dictionaries(st.text(), st.text()))
)
@pytest.mark.property_test
def test_state_persistence_round_trip(step_name, status, error, artifacts):
    """For any checkpoint, persisting and reading back should preserve all fields."""
    # Create checkpoint
    original = StepCheckpoint(
        name=step_name,
        status=status,
        start_time=datetime.now(),
        end_time=datetime.now(),
        error=error,
        artifacts=artifacts
    )

    # Persist to temp file
    state_mgr = StateManager(Path("/tmp/test_state.json"))
    state = BuildState(
        build_id="test",
        start_time=datetime.now(),
        steps=[original],
        config_hash="abc123"
    )
    state_mgr.write(state)

    # Read back
    restored_state = state_mgr.read()
    restored = restored_state.steps[0]

    # Verify equivalence
    assert restored.name == original.name
    assert restored.status == original.status
    assert restored.error == original.error
    assert restored.artifacts == original.artifacts
```

### Test Organization

```
tests/
├── unit/
│   ├── test_scanner.py           # RepositoryScanner unit tests
│   ├── test_state_manager.py     # StateManager unit tests
│   ├── test_orchestrator.py      # BuildOrchestrator unit tests
│   ├── test_zarf_generator.py    # ZarfGenerator unit tests
│   ├── test_manifest_generator.py # ManifestGenerator unit tests
│   └── test_cli.py               # CLI command tests
├── property/
│   ├── test_properties_scanning.py    # Properties 1-2
│   ├── test_properties_state.py       # Properties 3-6
│   ├── test_properties_zarf.py        # Property 7
│   ├── test_properties_manifest.py    # Properties 8-11
│   ├── test_properties_logging.py     # Property 12
│   ├── test_properties_metrics.py     # Property 13
│   ├── test_properties_deployment.py  # Property 14
│   ├── test_properties_validation.py  # Property 15
│   └── test_properties_compatibility.py # Properties 16-19
└── integration/
    ├── test_full_build.py        # End-to-end build test
    ├── test_resume.py            # Checkpoint/resume test
    └── test_deployment.py        # Bastion service deployment test
```

### Coverage Requirements

- Unit test coverage: >85%
- Property test coverage: All 19 properties implemented
- Integration test coverage: All major workflows (build, resume, deploy)

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest hypothesis pytest-cov

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src

      - name: Run property tests
        run: pytest tests/property/ -v --hypothesis-show-statistics

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```
