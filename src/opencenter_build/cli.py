"""Command-line interface for openCenter AirGap build system.

This module provides the main CLI entry point using Typer and Rich for
a modern, user-friendly command-line experience.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from opencenter_build.component_manifest import ComponentManifest, create_default_manifest
from opencenter_build.config import parse_versions_env
from opencenter_build.exceptions import ConfigError, ValidationError

console = Console()

app = typer.Typer(
    name="opencenter-airgap",
    help="Build tool for openCenter AirGap packages",
    no_args_is_help=True,
)


@app.command()
def init(
    create_manifest: bool = typer.Option(
        False, "--create-manifest", help="Create component manifest from template"
    ),
    template: str = typer.Option("baremetal", "--template", help="Template: baremetal, openstack"),
    config_file: Path = typer.Option(
        Path("config/versions.env"), "--config", help="Configuration file path"
    ),
) -> None:
    """Initialize project configuration.

    Creates necessary directory structure and optionally generates a component
    manifest from a template. Validates existing configuration if present.
    """
    from opencenter_build.component_manifest import (
        create_default_manifest,
        write_manifest,
    )

    try:
        # Create directory structure
        directories = [
            Path("config"),
            Path("config/schemas"),
            Path("build"),
            Path("dist"),
            Path("assets"),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✓[/green] Created directory: {directory}")

        # Validate config file if it exists
        if config_file.exists():
            try:
                versions = parse_versions_env(config_file)
                console.print(f"[green]✓[/green] Validated configuration: {config_file}")
                console.print(f"  Found {len(versions)} version variables")
            except ConfigError as exc:
                console.print(f"[yellow]⚠[/yellow] Configuration validation warning: {exc}")
        else:
            console.print(f"[yellow]⚠[/yellow] Configuration file not found: {config_file}")
            console.print(f"  Create {config_file} with version variables")

        # Create component manifest if requested
        if create_manifest:
            manifest_path = Path("config/components.yaml")

            if manifest_path.exists():
                console.print(
                    f"[yellow]⚠[/yellow] Component manifest already exists: {manifest_path}"
                )
                overwrite = typer.confirm("Overwrite existing manifest?")
                if not overwrite:
                    console.print("[yellow]Skipped manifest creation[/yellow]")
                    return

            # Create manifest from template
            manifest = create_default_manifest(template=template)
            write_manifest(manifest, manifest_path)

            console.print(f"[green]✓[/green] Created component manifest: {manifest_path}")
            console.print(f"  Template: {template}")

        # Display success summary
        console.print()
        console.print(
            Panel.fit(
                "[bold green]Initialization complete![/bold green]\n\n"
                "Next steps:\n"
                "1. Edit config/versions.env with component versions\n"
                "2. Edit config/components.yaml to add tools and repositories\n"
                "3. Run 'opencenter-airgap validate' to check configuration\n"
                "4. Run 'opencenter-airgap scan' to discover images",
                title="Success",
                border_style="green",
            )
        )

    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def add(
    component_type: str = typer.Argument(..., help="Component type: tool, repo, image, chart"),
    name: str = typer.Argument(..., help="Component name"),
    version: Optional[str] = typer.Option(None, "--version", help="Component version"),
    url: Optional[str] = typer.Option(None, "--url", help="Component URL"),
    ref: Optional[str] = typer.Option(None, "--ref", help="Git ref (for repos)"),
    repo: Optional[str] = typer.Option(None, "--repo", help="Helm repo URL (for charts)"),
    extract: bool = typer.Option(False, "--extract", help="Extract archive (for tools)"),
    binary: Optional[str] = typer.Option(
        None, "--binary", help="Binary path in archive (for tools)"
    ),
    manifest_path: Path = typer.Option(
        Path("config/components.yaml"), "--manifest", help="Component manifest path"
    ),
) -> None:
    """Add component to manifest.

    Adds a tool, repository, image, or chart to the component manifest.
    Creates the manifest if it doesn't exist.

    Examples:
        Add a tool:
            opencenter-airgap add tool helm --version 3.14.0 --url https://get.helm.sh/helm-v3.14.0-linux-amd64.tar.gz --extract --binary linux-amd64/helm

        Add a repository:
            opencenter-airgap add repo kubespray --url https://github.com/kubernetes-sigs/kubespray.git --ref master

        Add an image:
            opencenter-airgap add image nginx:1.21

        Add a chart:
            opencenter-airgap add chart cert-manager --version v1.13.0 --repo https://charts.jetstack.io
    """
    from opencenter_build.component_manifest import (
        ComponentManifest,
        read_manifest,
        write_manifest,
    )

    try:
        # Load or create manifest
        if manifest_path.exists():
            manifest = read_manifest(manifest_path)
            console.print(f"[cyan]Loaded manifest:[/cyan] {manifest_path}")
        else:
            manifest = ComponentManifest()
            console.print(f"[cyan]Creating new manifest:[/cyan] {manifest_path}")

        # Add component based on type
        if component_type == "tool":
            if not version or not url:
                console.print("[red]Error:[/red] --version and --url required for tools")
                raise typer.Exit(code=1)

            manifest.add_tool(
                name=name,
                version=version,
                url=url,
                extract=extract,
                binary=binary,
            )
            console.print(f"[green]✓[/green] Added tool: {name} v{version}")

        elif component_type == "repo":
            if not url or not ref:
                console.print("[red]Error:[/red] --url and --ref required for repositories")
                raise typer.Exit(code=1)

            manifest.add_repository(name=name, url=url, ref=ref)
            console.print(f"[green]✓[/green] Added repository: {name} ({ref})")

        elif component_type == "image":
            manifest.add_image(name)
            console.print(f"[green]✓[/green] Added image: {name}")

        elif component_type == "chart":
            if not version or not repo:
                console.print("[red]Error:[/red] --version and --repo required for charts")
                raise typer.Exit(code=1)

            manifest.add_chart(name=name, repo=repo, version=version)
            console.print(f"[green]✓[/green] Added chart: {name} v{version}")

        else:
            console.print(
                f"[red]Error:[/red] Unknown component type: {component_type}\n"
                "Valid types: tool, repo, image, chart"
            )
            raise typer.Exit(code=1)

        # Save manifest
        write_manifest(manifest, manifest_path)
        console.print(f"[green]✓[/green] Saved manifest: {manifest_path}")

    except ConfigError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def scan(
    repos: Optional[list[Path]] = typer.Option(
        None, "--repo", help="Repository paths to scan (can be specified multiple times)"
    ),
    discover_images: bool = typer.Option(
        False, "--discover-images", help="Discover images from component manifest repositories"
    ),
    concurrency: Optional[int] = typer.Option(
        None, "--concurrency", help="Number of worker processes"
    ),
    output: Path = typer.Option(
        Path("config/all-images.txt"), "--output", help="Output file for discovered images"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
) -> None:
    """Scan repositories for container images.

    Discovers container images in Git repositories using concurrent scanning.
    Can scan explicit repository paths or auto-discover from component manifest.

    Examples:
        Scan specific repositories:
            opencenter-airgap scan --repo kubespray --repo opencenter-gitops-base

        Discover from component manifest:
            opencenter-airgap scan --discover-images
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from opencenter_build.scanner import RepositoryScanner

    try:
        # Determine repositories to scan
        repos_to_scan: list[Path] = []

        if discover_images:
            # Load component manifest and extract repository paths
            manifest_path = Path("config/components.yaml")
            if not manifest_path.exists():
                console.print(
                    f"[bold red]Error:[/bold red] Component manifest not found: {manifest_path}"
                )
                console.print("Run 'opencenter-airgap init --create-manifest' first")
                raise typer.Exit(code=1)

            from opencenter_build.component_manifest import read_manifest

            manifest = read_manifest(manifest_path)

            # Check if repositories are cloned
            for repo_spec in manifest.repositories:
                repo_path = Path("build") / repo_spec.name
                if repo_path.exists():
                    repos_to_scan.append(repo_path)
                else:
                    console.print(f"[yellow]⚠[/yellow] Repository not found: {repo_path}")
                    console.print(f"  Clone {repo_spec.url} to {repo_path}")

        if repos:
            repos_to_scan.extend(repos)

        if not repos_to_scan:
            console.print("[bold red]Error:[/bold red] No repositories to scan")
            console.print("Specify --repo or use --discover-images")
            raise typer.Exit(code=1)

        # Validate repositories exist
        valid_repos = []
        for repo in repos_to_scan:
            if repo.exists() and repo.is_dir():
                valid_repos.append(repo)
            else:
                console.print(f"[yellow]⚠[/yellow] Repository not found: {repo}")

        if not valid_repos:
            console.print("[bold red]Error:[/bold red] No valid repositories found")
            raise typer.Exit(code=1)

        console.print(f"[cyan]Scanning {len(valid_repos)} repositories...[/cyan]")
        if verbose:
            for repo in valid_repos:
                console.print(f"  - {repo}")

        # Create scanner
        scanner = RepositoryScanner(
            repos=valid_repos,
            max_workers=concurrency,
        )

        # Scan with progress bar
        all_images: set[str] = set()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning repositories...", total=len(valid_repos))

            results = scanner.scan_all()

            for repo_path, images in results.items():
                all_images.update(images)
                progress.update(task, advance=1)
                if verbose:
                    console.print(f"  {repo_path}: {len(images)} images")

        # Write results
        output.parent.mkdir(parents=True, exist_ok=True)
        sorted_images = sorted(all_images)
        output.write_text("\n".join(sorted_images) + "\n")

        console.print()
        console.print(f"[green]✓[/green] Discovered {len(all_images)} unique images")
        console.print(f"[green]✓[/green] Wrote results to: {output}")

        if verbose:
            console.print("\nTop 10 images:")
            for image in sorted_images[:10]:
                console.print(f"  - {image}")

    except ConfigError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def generate_manifest(
    output: Path = typer.Option(
        Path("zarf.yaml"), "--output", help="Output path for Zarf manifest"
    ),
    component_manifest: Path = typer.Option(
        Path("config/components.yaml"), "--components", help="Component manifest path"
    ),
    config_file: Path = typer.Option(
        Path("config/versions.env"), "--config", help="Configuration file path"
    ),
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Validate generated manifest"
    ),
) -> None:
    """Generate Zarf manifest from component manifest.

    Reads the component manifest and configuration, resolves templates,
    expands auto-discovery directives, and generates a complete zarf.yaml.

    Example:
        opencenter-airgap generate-manifest --output zarf.yaml
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from opencenter_build.config import BuildConfig
    from opencenter_build.zarf_generator import ZarfGenerator

    try:
        # Load component manifest
        if not component_manifest.exists():
            console.print(
                f"[bold red]Error:[/bold red] Component manifest not found: {component_manifest}"
            )
            console.print("Run 'opencenter-airgap init --create-manifest' first")
            raise typer.Exit(code=1)

        console.print(f"[cyan]Loading component manifest...[/cyan]")
        from opencenter_build.component_manifest import read_manifest

        manifest = read_manifest(component_manifest)
        console.print(
            f"[green]✓[/green] Loaded {len(manifest.tools)} tools, {len(manifest.repositories)} repos"
        )

        # Load configuration
        if not config_file.exists():
            console.print(f"[bold red]Error:[/bold red] Configuration not found: {config_file}")
            console.print("Create config/versions.env with version variables")
            raise typer.Exit(code=1)

        console.print(f"[cyan]Loading configuration...[/cyan]")
        config = BuildConfig.from_env_file(config_file)
        console.print(f"[green]✓[/green] Loaded configuration")

        # Generate Zarf manifest
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating Zarf manifest...", total=None)

            generator = ZarfGenerator(config)
            generator.generate(output)

            progress.update(task, completed=True)

        console.print(f"[green]✓[/green] Generated Zarf manifest: {output}")

        # Validate if requested
        if validate:
            console.print(f"[cyan]Validating manifest...[/cyan]")

            # Basic validation - check file exists and is valid YAML
            try:
                manifest_data = yaml.safe_load(output.read_text())

                # Check required fields
                required_fields = ["kind", "metadata", "components"]
                missing = [f for f in required_fields if f not in manifest_data]

                if missing:
                    console.print(
                        f"[yellow]⚠[/yellow] Missing required fields: {', '.join(missing)}"
                    )
                else:
                    console.print(f"[green]✓[/green] Manifest validation passed")

                    # Display summary
                    components = manifest_data.get("components", [])
                    console.print(f"  Components: {len(components)}")

            except yaml.YAMLError as exc:
                console.print(f"[bold red]Error:[/bold red] Invalid YAML: {exc}")
                raise typer.Exit(code=1)

    except ConfigError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def build(
    clean: bool = typer.Option(False, "--clean", help="Clean build (ignore checkpoints)"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from checkpoint"),
    config_file: Path = typer.Option(
        Path("config/versions.env"), "--config", help="Configuration file path"
    ),
    state_file: Path = typer.Option(Path("build/state.json"), "--state", help="State file path"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
) -> None:
    """Build air-gap package with all artifacts.

    Executes the complete build pipeline with checkpoint/resume capability.
    Displays progress for each step and handles errors gracefully.

    Examples:
        Clean build:
            opencenter-airgap build --clean

        Resume from checkpoint:
            opencenter-airgap build --resume
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from opencenter_build.config import BuildConfig
    from opencenter_build.orchestrator import BuildOrchestrator
    from opencenter_build.state import StateManager

    try:
        # Load configuration
        if not config_file.exists():
            console.print(f"[bold red]Error:[/bold red] Configuration not found: {config_file}")
            console.print("Create config/versions.env with version variables")
            raise typer.Exit(code=1)

        console.print(f"[cyan]Loading configuration...[/cyan]")
        config = BuildConfig.from_env_file(config_file)
        console.print(f"[green]✓[/green] Loaded configuration")

        # Initialize state manager
        state_mgr = StateManager(state_file)

        # Create orchestrator
        orchestrator = BuildOrchestrator(config, state_mgr, clean=clean)

        # Register step handlers
        from opencenter_build.scanner import RepositoryScanner
        from opencenter_build.manifest import ManifestGenerator
        from opencenter_build.zarf_generator import ZarfGenerator

        def scan_repositories() -> dict[str, str]:
            """Scan repositories for container images."""
            console.print("  [cyan]Scanning repositories...[/cyan]")

            # Read git repositories list
            git_repos_file = Path("config/git-repositories.txt")
            if not git_repos_file.exists():
                console.print(f"  [yellow]⚠[/yellow] No git-repositories.txt found, skipping scan")
                return {"images": "config/all-images.txt", "count": "0"}

            # Parse repository paths
            repo_paths = []
            for line in git_repos_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Extract repo name from URL or path
                    repo_name = line.split("/")[-1].replace(".git", "")
                    repo_path = Path("build") / repo_name
                    if repo_path.exists():
                        repo_paths.append(repo_path)

            if not repo_paths:
                console.print(
                    f"  [yellow]⚠[/yellow] No repositories found in build/, skipping scan"
                )
                return {"images": "config/all-images.txt", "count": "0"}

            # Scan repositories
            scanner = RepositoryScanner(repos=repo_paths)
            results = scanner.scan_all()

            # Collect all unique images
            all_images = set()
            for images in results.values():
                all_images.update(images)

            # Write to output file
            output_file = Path("config/all-images.txt")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text("\n".join(sorted(all_images)) + "\n")

            console.print(f"  [green]✓[/green] Found {len(all_images)} images")
            return {"images": str(output_file), "count": str(len(all_images))}

        def collect_kubespray_offline() -> dict[str, str]:
            """Collect kubespray-offline assets."""
            console.print("  [cyan]Collecting kubespray-offline assets...[/cyan]")

            # Check if kubespray-offline exists
            kubespray_dir = Path("build/kubespray-offline")
            if not kubespray_dir.exists():
                console.print(
                    f"  [yellow]⚠[/yellow] kubespray-offline not found at {kubespray_dir}"
                )
                console.print(
                    f"  [cyan]Clone: git clone https://github.com/kubespray-offline/kubespray-offline.git build/kubespray-offline[/cyan]"
                )
                return {"assets": "", "status": "skipped", "reason": "kubespray_offline_not_found"}

            # Check if download-all.sh exists
            download_script = kubespray_dir / "download-all.sh"
            if not download_script.exists():
                console.print(f"  [yellow]⚠[/yellow] download-all.sh not found in {kubespray_dir}")
                return {"assets": "", "status": "skipped", "reason": "download_script_not_found"}

            # Check if outputs already exist
            outputs_dir = kubespray_dir / "outputs"
            if outputs_dir.exists():
                # Count artifacts
                file_count = sum(1 for _ in outputs_dir.rglob("*") if _.is_file())
                if file_count > 0:
                    console.print(
                        f"  [green]✓[/green] Found {file_count} existing artifacts in {outputs_dir}"
                    )
                    return {
                        "assets": str(outputs_dir),
                        "status": "verified",
                        "count": str(file_count),
                    }

            # Run download-all.sh if outputs don't exist
            console.print(f"  [cyan]Running kubespray-offline download-all.sh...[/cyan]")
            console.print(
                f"  [yellow]⚠[/yellow] This may take 30-60 minutes depending on network speed"
            )

            try:
                import subprocess

                result = subprocess.run(
                    ["bash", str(download_script)],
                    cwd=str(kubespray_dir),
                    capture_output=True,
                    text=True,
                    timeout=7200,  # 2 hour timeout
                )

                if result.returncode != 0:
                    console.print(f"  [red]✗[/red] kubespray-offline download failed")
                    console.print(f"  [red]{result.stderr}[/red]")
                    return {"assets": "", "status": "failed", "error": result.stderr}

                # Verify outputs were created
                if outputs_dir.exists():
                    file_count = sum(1 for _ in outputs_dir.rglob("*") if _.is_file())
                    console.print(f"  [green]✓[/green] Downloaded {file_count} artifacts")
                    return {
                        "assets": str(outputs_dir),
                        "status": "downloaded",
                        "count": str(file_count),
                    }
                else:
                    console.print(
                        f"  [yellow]⚠[/yellow] Download completed but outputs directory not found"
                    )
                    return {"assets": "", "status": "unknown"}

            except subprocess.TimeoutExpired:
                console.print(f"  [red]✗[/red] kubespray-offline download timed out after 2 hours")
                return {"assets": "", "status": "timeout"}
            except Exception as exc:
                console.print(f"  [red]✗[/red] kubespray-offline download error: {exc}")
                return {"assets": "", "status": "error", "error": str(exc)}

        def mirror_terraform_providers() -> dict[str, str]:
            """Mirror Terraform providers."""
            console.print("  [cyan]Mirroring Terraform providers...[/cyan]")

            # Check if Terraform modules exist
            terraform_dir = Path("assets/terraform")
            if not terraform_dir.exists():
                console.print(f"  [yellow]⚠[/yellow] No Terraform modules found at {terraform_dir}")
                console.print(
                    f"  [cyan]Skipping provider mirroring (OpenStack deployments only)[/cyan]"
                )
                return {"providers": "", "status": "skipped", "reason": "no_terraform_modules"}

            # Check if terraform CLI is available
            import shutil

            if not shutil.which("terraform"):
                console.print(f"  [yellow]⚠[/yellow] Terraform CLI not available")
                console.print(
                    f"  [cyan]Install terraform: https://www.terraform.io/downloads[/cyan]"
                )
                return {"providers": "", "status": "skipped", "reason": "terraform_cli_not_found"}

            # Create mirror directory
            mirror_dir = Path("assets/terraform-mirror")
            mirror_dir.mkdir(parents=True, exist_ok=True)

            # Run terraform providers mirror
            console.print(f"  [cyan]Running terraform providers mirror...[/cyan]")

            try:
                import subprocess

                result = subprocess.run(
                    [
                        "terraform",
                        "providers",
                        "mirror",
                        "-platform=linux_amd64",
                        str(mirror_dir),
                    ],
                    cwd=str(terraform_dir),
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout
                )

                if result.returncode != 0:
                    console.print(f"  [red]✗[/red] Terraform provider mirror failed")
                    console.print(f"  [red]{result.stderr}[/red]")
                    return {"providers": "", "status": "failed", "error": result.stderr}

                # Count mirrored providers
                provider_count = sum(1 for _ in mirror_dir.rglob("*.zip") if _.is_file())
                console.print(
                    f"  [green]✓[/green] Mirrored {provider_count} providers to {mirror_dir}"
                )

                # Generate .terraformrc for offline use
                terraformrc = Path("assets/terraform-config/.terraformrc")
                terraformrc.parent.mkdir(parents=True, exist_ok=True)
                terraformrc.write_text(
                    f"provider_installation {{\n"
                    f"  filesystem_mirror {{\n"
                    f'    path    = "{mirror_dir.absolute()}"\n'
                    f'    include = ["*/*"]\n'
                    f"  }}\n"
                    f"  direct {{\n"
                    f'    exclude = ["*/*"]\n'
                    f"  }}\n"
                    f"}}\n"
                )
                console.print(f"  [green]✓[/green] Generated .terraformrc for offline use")

                return {
                    "providers": str(mirror_dir),
                    "status": "mirrored",
                    "count": str(provider_count),
                    "config": str(terraformrc),
                }

            except subprocess.TimeoutExpired:
                console.print(f"  [red]✗[/red] Terraform provider mirror timed out")
                return {"providers": "", "status": "timeout"}
            except Exception as exc:
                console.print(f"  [red]✗[/red] Terraform provider mirror error: {exc}")
                return {"providers": "", "status": "error", "error": str(exc)}

        def organize_assets() -> dict[str, str]:
            """Organize assets for packaging."""
            console.print("  [cyan]Organizing assets...[/cyan]")

            assets_dir = Path("assets")
            assets_dir.mkdir(parents=True, exist_ok=True)

            # Count assets
            asset_count = sum(1 for _ in assets_dir.rglob("*") if _.is_file())

            console.print(f"  [green]✓[/green] Organized {asset_count} asset files")
            return {"assets": str(assets_dir), "count": str(asset_count)}

        def create_zarf_package() -> dict[str, str]:
            """Create Zarf package."""
            console.print("  [cyan]Creating Zarf package...[/cyan]")

            # Generate zarf.yaml if needed
            zarf_file = Path("zarf.yaml")
            if not zarf_file.exists():
                console.print("  [cyan]Generating zarf.yaml...[/cyan]")
                generator = ZarfGenerator(config)
                generator.generate(zarf_file)
                console.print(f"  [green]✓[/green] Generated zarf.yaml")

            # Check if zarf CLI is available
            import shutil

            if not shutil.which("zarf"):
                console.print(
                    f"  [yellow]⚠[/yellow] Zarf CLI not available - skipping package creation"
                )
                console.print(
                    f"  [cyan]Install zarf: https://docs.zarf.dev/getting-started/install/[/cyan]"
                )
                return {"package": "", "status": "skipped", "reason": "zarf_cli_not_found"}

            # Create package with zarf CLI
            dist_dir = Path("dist")
            dist_dir.mkdir(parents=True, exist_ok=True)

            try:
                import subprocess

                result = subprocess.run(
                    ["zarf", "package", "create", "--confirm", "-o", str(dist_dir)],
                    capture_output=True,
                    text=True,
                    timeout=3600,  # 1 hour timeout for large packages
                )

                if result.returncode != 0:
                    console.print(f"  [red]✗[/red] Zarf package creation failed")
                    console.print(f"  [red]{result.stderr}[/red]")
                    return {"package": "", "status": "failed", "error": result.stderr}

                # Find created package
                packages = list(dist_dir.glob("zarf-package-*.tar.zst"))
                if packages:
                    package_path = packages[0]
                    console.print(f"  [green]✓[/green] Created package: {package_path}")
                    return {"package": str(package_path), "status": "created"}
                else:
                    console.print(
                        f"  [yellow]⚠[/yellow] Package created but not found in {dist_dir}"
                    )
                    return {"package": "", "status": "unknown"}

            except subprocess.TimeoutExpired:
                console.print(f"  [red]✗[/red] Zarf package creation timed out")
                return {"package": "", "status": "timeout"}
            except Exception as exc:
                console.print(f"  [red]✗[/red] Zarf package creation error: {exc}")
                return {"package": "", "status": "error", "error": str(exc)}

        def generate_manifest() -> dict[str, str]:
            """Generate artifact manifest."""
            console.print("  [cyan]Generating artifact manifest...[/cyan]")

            # Use project root as build directory
            build_dir = Path(".")
            generator = ManifestGenerator(build_dir)
            manifest_obj = generator.generate()

            dist_dir = Path("dist")
            dist_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = dist_dir / "artifact-manifest.json"

            # Write manifest to JSON file
            manifest_path.write_text(json.dumps(manifest_obj.to_dict(), indent=2))

            artifact_count = manifest_obj.total_artifacts
            console.print(f"  [green]✓[/green] Generated manifest with {artifact_count} artifacts")

            return {"manifest": str(manifest_path), "artifacts": str(artifact_count)}

        orchestrator.register_step_handler("scan_repositories", scan_repositories)
        orchestrator.register_step_handler("collect_kubespray_offline", collect_kubespray_offline)
        orchestrator.register_step_handler("mirror_terraform_providers", mirror_terraform_providers)
        orchestrator.register_step_handler("organize_assets", organize_assets)
        orchestrator.register_step_handler("create_zarf_package", create_zarf_package)
        orchestrator.register_step_handler("generate_manifest", generate_manifest)

        # Execute build
        console.print()
        console.print(f"[bold cyan]Starting build...[/bold cyan]")
        if clean:
            console.print("[yellow]Clean build - ignoring checkpoints[/yellow]")
        elif resume:
            console.print("[cyan]Resume mode - will skip completed steps[/cyan]")
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Building...", total=len(orchestrator.steps))

            result = orchestrator.execute(resume=resume)

            progress.update(task, completed=result.completed_steps)

        # Display results
        console.print()
        if result.success:
            console.print(
                Panel.fit(
                    f"[bold green]Build completed successfully![/bold green]\n\n"
                    f"Build ID: {result.build_id}\n"
                    f"Duration: {result.duration_seconds:.1f}s\n"
                    f"Steps: {result.completed_steps}/{result.total_steps}",
                    title="Success",
                    border_style="green",
                )
            )

            # Display output locations
            console.print()
            console.print("[bold cyan]Build Artifacts:[/bold cyan]")

            # Show manifest location
            manifest_path = Path("dist/artifact-manifest.json")
            if manifest_path.exists():
                console.print(f"  [green]✓[/green] Manifest: {manifest_path}")

            # Show zarf.yaml location
            zarf_path = Path("zarf.yaml")
            if zarf_path.exists():
                console.print(f"  [green]✓[/green] Zarf config: {zarf_path}")

            # Show package location (if created)
            if result.package_path:
                package_path = Path(result.package_path)
                if package_path.exists():
                    console.print(f"  [green]✓[/green] Package: {result.package_path}")
                else:
                    console.print(
                        f"  [yellow]⚠[/yellow] Package: {result.package_path} (not created - requires Zarf CLI)"
                    )

            # Show state file
            state_path = Path(state_file)
            if state_path.exists():
                console.print(f"  [cyan]ℹ[/cyan] State: {state_path}")

        else:
            console.print(
                Panel.fit(
                    f"[bold red]Build failed[/bold red]\n\n"
                    f"Build ID: {result.build_id}\n"
                    f"Duration: {result.duration_seconds:.1f}s\n"
                    f"Steps: {result.completed_steps}/{result.total_steps}\n"
                    f"Error: {result.error}",
                    title="Failed",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

    except ConfigError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def validate(
    strict: bool = typer.Option(False, "--strict", help="Fail on warnings"),
    check_upstream: bool = typer.Option(
        False, "--check-upstream", help="Verify URLs are reachable"
    ),
    config_file: Path = typer.Option(
        Path("config/versions.env"), "--config", help="Configuration file path"
    ),
    component_manifest: Path = typer.Option(
        Path("config/components.yaml"), "--components", help="Component manifest path"
    ),
) -> None:
    """Validate configuration files and schemas.

    Checks configuration files for errors before starting a build.
    Validates versions.env, component manifest, and optionally checks
    that URLs are reachable.

    Examples:
        Basic validation:
            opencenter-airgap validate

        Strict mode (fail on warnings):
            opencenter-airgap validate --strict

        Check upstream URLs:
            opencenter-airgap validate --check-upstream
    """
    from rich.table import Table
    from opencenter_build.validation import ComprehensiveConfigValidator

    try:
        console.print("[bold cyan]Validating configuration...[/bold cyan]\n")

        # Create validator
        validator = ComprehensiveConfigValidator(config_file=config_file)

        # Run validation
        result = validator.validate_all(
            check_repos=True,
            check_dependencies=True,
            check_component_manifest=component_manifest.exists(),
            component_manifest_path=component_manifest if component_manifest.exists() else None,
        )

        # Display summary
        console.print()
        table = Table(title="Validation Summary")
        table.add_column("Category", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Count")

        if result.errors:
            table.add_row("Errors", "[red]✗[/red]", str(len(result.errors)))
        else:
            table.add_row("Errors", "[green]✓[/green]", "0")

        if result.warnings:
            table.add_row("Warnings", "[yellow]⚠[/yellow]", str(len(result.warnings)))
        else:
            table.add_row("Warnings", "[green]✓[/green]", "0")

        console.print(table)

        # Display errors and warnings
        if result.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in result.errors:
                console.print(f"  - {error}")

        if result.warnings:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in result.warnings:
                console.print(f"  - {warning}")

        # Check upstream URLs if requested
        if check_upstream:
            console.print("\n[yellow]⚠[/yellow] Upstream URL checking not yet implemented")

        # Exit with appropriate code
        if result.errors:
            console.print("\n[bold red]Validation failed[/bold red]")
            raise typer.Exit(code=1)
        elif result.warnings and strict:
            console.print("\n[bold yellow]Validation failed (strict mode)[/bold yellow]")
            raise typer.Exit(code=1)
        else:
            console.print("\n[bold green]Validation passed[/bold green]")

    except ConfigError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def verify(
    package: Path = typer.Argument(..., help="Package path to verify"),
    manifest: Optional[Path] = typer.Option(
        None, "--manifest", help="Artifact manifest path for comparison"
    ),
) -> None:
    """Verify package integrity and signatures.

    Verifies Zarf package integrity through signature validation,
    checksum verification, and optional manifest comparison.

    Examples:
        Basic verification:
            opencenter-airgap verify dist/zarf-package-*.tar.zst

        With manifest comparison:
            opencenter-airgap verify dist/zarf-package-*.tar.zst --manifest dist/artifact-manifest.json
    """
    from rich.table import Table
    from opencenter_build.verifier import PackageVerifier

    try:
        console.print(f"[bold cyan]Verifying package: {package}[/bold cyan]\n")

        # Create verifier
        verifier = PackageVerifier()

        # Verify package
        result = verifier.verify(package, manifest)

        # Display results
        table = Table(title="Verification Results")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")

        # Signature check
        if result.signature_valid:
            table.add_row("Signature", "[green]✓ Valid[/green]")
        else:
            table.add_row("Signature", "[yellow]⚠ Not available[/yellow]")

        # Checksum check
        if result.checksums_valid:
            table.add_row("Checksums", "[green]✓ Valid[/green]")
        else:
            table.add_row("Checksums", "[red]✗ Invalid[/red]")

        # Manifest check
        if manifest:
            if result.manifest_matches:
                table.add_row("Manifest", "[green]✓ Matches[/green]")
            else:
                table.add_row("Manifest", "[red]✗ Mismatch[/red]")

        console.print(table)

        # Display artifact count
        if result.artifact_count > 0:
            console.print(f"\n[cyan]Artifacts verified: {result.artifact_count}[/cyan]")

        # Display errors
        if result.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in result.errors:
                console.print(f"  - {error}")

        # Final status
        console.print()
        if result.success:
            console.print(
                Panel.fit(
                    "[bold green]Verification passed[/bold green]\n\n"
                    f"Package: {package}\n"
                    f"Artifacts: {result.artifact_count}",
                    title="Success",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[bold red]Verification failed[/bold red]\n\n"
                    f"Package: {package}\n"
                    f"Errors: {len(result.errors)}",
                    title="Failed",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

    except ValidationError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def status(
    state_file: Path = typer.Option(Path("build/state.json"), "--state", help="State file path"),
) -> None:
    """Show current build status and progress.

    Displays the status of all build steps, showing which are completed,
    in progress, or pending. Shows progress percentage and build ID.

    Example:
        opencenter-airgap status
    """
    from rich.table import Table
    from opencenter_build.state import StateManager, StepStatus

    try:
        # Load state
        state_mgr = StateManager(state_file)
        build_state = state_mgr.read_build_state()

        if build_state is None:
            console.print("[yellow]No build in progress[/yellow]")
            console.print("Run 'opencenter-airgap build' to start a build")
            return

        # Count step statuses
        completed = sum(1 for step in build_state.steps if step.status == StepStatus.COMPLETED)
        failed = sum(1 for step in build_state.steps if step.status == StepStatus.FAILED)
        running = sum(1 for step in build_state.steps if step.status == StepStatus.RUNNING)
        pending = sum(1 for step in build_state.steps if step.status == StepStatus.PENDING)
        total = len(build_state.steps)

        # Calculate progress
        progress_pct = (completed / total * 100) if total > 0 else 0

        # Display header
        console.print(f"[bold cyan]Build Status[/bold cyan]\n")
        console.print(f"Build ID: {build_state.build_id}")
        console.print(f"Started: {build_state.start_time}")
        console.print(f"Config Hash: {build_state.config_hash[:16]}...")
        console.print(f"Progress: {completed}/{total} steps ({progress_pct:.1f}%)\n")

        # Create status table
        table = Table(title="Build Steps")
        table.add_column("Step", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Duration")
        table.add_column("Error", style="red")

        for step in build_state.steps:
            # Format status
            if step.status == StepStatus.COMPLETED:
                status_str = "[green]✓ Completed[/green]"
            elif step.status == StepStatus.FAILED:
                status_str = "[red]✗ Failed[/red]"
            elif step.status == StepStatus.RUNNING:
                status_str = "[yellow]⟳ Running[/yellow]"
            else:
                status_str = "[dim]○ Pending[/dim]"

            # Calculate duration
            duration_str = ""
            if step.start_time and step.end_time:
                try:
                    from datetime import datetime

                    start = datetime.fromisoformat(step.start_time)
                    end = datetime.fromisoformat(step.end_time)
                    duration = (end - start).total_seconds()
                    duration_str = f"{duration:.1f}s"
                except Exception:
                    pass

            # Error message
            error_str = (
                step.error[:50] + "..."
                if step.error and len(step.error) > 50
                else (step.error or "")
            )

            table.add_row(step.name, status_str, duration_str, error_str)

        console.print(table)

        # Display summary
        console.print()
        if failed > 0:
            console.print(f"[red]✗ {failed} step(s) failed[/red]")
        elif running > 0:
            console.print(f"[yellow]⟳ Build in progress ({running} running)[/yellow]")
        elif completed == total:
            console.print(f"[green]✓ Build completed successfully[/green]")

            # Show build artifacts if build is complete
            console.print()
            console.print("[bold cyan]Build Artifacts:[/bold cyan]")

            # Check for manifest
            manifest_path = Path("dist/artifact-manifest.json")
            if manifest_path.exists():
                console.print(f"  [green]✓[/green] Manifest: {manifest_path}")
                # Read manifest to show artifact count
                try:
                    import json

                    manifest_data = json.loads(manifest_path.read_text())
                    artifact_count = manifest_data.get("total_artifacts", 0)
                    console.print(f"    [dim]└─ {artifact_count} artifacts[/dim]")
                except Exception:
                    pass

            # Check for zarf.yaml
            zarf_path = Path("zarf.yaml")
            if zarf_path.exists():
                console.print(f"  [green]✓[/green] Zarf config: {zarf_path}")

            # Check for package
            package_path = Path("dist/zarf-package-opencenter-airgap.tar.zst")
            if package_path.exists():
                size_mb = package_path.stat().st_size / (1024 * 1024)
                console.print(f"  [green]✓[/green] Package: {package_path}")
                console.print(f"    [dim]└─ {size_mb:.1f} MB[/dim]")
            else:
                console.print(
                    f"  [yellow]⚠[/yellow] Package: {package_path} (not created - requires Zarf CLI)"
                )

            # Show state file
            if state_file.exists():
                console.print(f"  [cyan]ℹ[/cyan] State: {state_file}")

        else:
            console.print(f"[cyan]○ {pending} step(s) pending[/cyan]")

    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def clean(
    state_file: Path = typer.Option(Path("build/state.json"), "--state", help="State file path"),
    build_dir: Path = typer.Option(Path("build"), "--build-dir", help="Build directory path"),
    dist_dir: Path = typer.Option(Path("dist"), "--dist-dir", help="Distribution directory path"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Clean build artifacts and state.

    Removes build artifacts, distribution packages, and state files.
    Prompts for confirmation before deletion unless --yes is specified.

    Examples:
        Clean with confirmation:
            opencenter-airgap clean

        Clean without confirmation:
            opencenter-airgap clean --yes
    """
    import shutil

    try:
        # List items to delete
        items_to_delete = []

        if state_file.exists():
            items_to_delete.append(("State file", state_file))

        if build_dir.exists():
            # Count files in build dir
            file_count = sum(1 for _ in build_dir.rglob("*") if _.is_file())
            items_to_delete.append(("Build directory", build_dir, file_count))

        if dist_dir.exists():
            # Count files in dist dir
            file_count = sum(1 for _ in dist_dir.rglob("*") if _.is_file())
            items_to_delete.append(("Distribution directory", dist_dir, file_count))

        if not items_to_delete:
            console.print("[green]Nothing to clean[/green]")
            return

        # Display items to delete
        console.print("[bold cyan]Items to delete:[/bold cyan]\n")
        for item in items_to_delete:
            if len(item) == 3:
                name, path, count = item
                console.print(f"  - {name}: {path} ({count} files)")
            else:
                name, path = item
                console.print(f"  - {name}: {path}")

        # Confirm deletion
        if not confirm:
            console.print()
            confirm = typer.confirm("Delete these items?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Delete items
        console.print()
        for item in items_to_delete:
            name = item[0]
            path = item[1]

            try:
                if path.is_file():
                    path.unlink()
                    console.print(f"[green]✓[/green] Deleted {name}: {path}")
                elif path.is_dir():
                    shutil.rmtree(path)
                    console.print(f"[green]✓[/green] Deleted {name}: {path}")
            except Exception as exc:
                console.print(f"[red]✗[/red] Failed to delete {name}: {exc}")

        console.print()
        console.print("[bold green]Clean complete[/bold green]")

    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def serve(
    package: Path = typer.Argument(..., help="Zarf package path to deploy"),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Verify package signature before deployment"
    ),
    nginx_port: int = typer.Option(80, "--nginx-port", help="Nginx file server port"),
    registry_port: int = typer.Option(31999, "--registry-port", help="Container registry port"),
    git_port: int = typer.Option(3000, "--git-port", help="Git server port"),
    install_path: Path = typer.Option(
        Path("/opt/opencenter"), "--install-path", help="Installation path on bastion"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
) -> None:
    """Deploy package and start bastion services.

    Deploys the Zarf package and starts all required bastion services:
    - Container registry (Zarf init)
    - Git server (Zarf init)
    - Nginx file server (Docker container)

    Verifies service health after startup and displays service URLs.

    Examples:
        Deploy package:
            opencenter-airgap serve dist/zarf-package-*.tar.zst

        Deploy without verification:
            opencenter-airgap serve dist/zarf-package-*.tar.zst --no-verify

        Custom ports:
            opencenter-airgap serve dist/zarf-package-*.tar.zst --nginx-port 8080 --registry-port 5000
    """
    import time
    import urllib.request
    from rich.progress import Progress, SpinnerColumn, TextColumn

    try:
        # Verify package exists
        if not package.exists():
            console.print(f"[bold red]Error:[/bold red] Package not found: {package}")
            raise typer.Exit(code=1)

        console.print(f"[bold cyan]Deploying package: {package}[/bold cyan]\n")

        # Verify package if requested
        if verify:
            console.print("[cyan]1. Verifying package integrity...[/cyan]")
            from opencenter_build.verifier import PackageVerifier

            verifier = PackageVerifier()
            result = verifier.verify(package, None)

            if not result.success:
                console.print("[red]✗ Package verification failed[/red]")
                for error in result.errors:
                    console.print(f"  - {error}")
                raise typer.Exit(code=1)

            console.print("[green]✓ Package verification passed[/green]\n")

        # Deploy Zarf package
        console.print("[cyan]2. Deploying Zarf package...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Executing zarf package deploy...", total=None)

            try:
                result = subprocess.run(
                    ["zarf", "package", "deploy", str(package), "--confirm"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                if verbose:
                    console.print(result.stdout)

                progress.update(task, completed=True)
                console.print("[green]✓ Zarf package deployed[/green]\n")

            except subprocess.CalledProcessError as exc:
                progress.update(task, completed=True)
                console.print(f"[red]✗ Zarf deployment failed[/red]")
                console.print(f"  Exit code: {exc.returncode}")
                if verbose or exc.stderr:
                    console.print(f"  Error: {exc.stderr}")
                raise typer.Exit(code=1)
            except FileNotFoundError:
                progress.update(task, completed=True)
                console.print("[red]✗ Zarf not found in PATH[/red]")
                console.print("  Install Zarf: https://zarf.dev/install/")
                raise typer.Exit(code=1)

        # Start nginx container
        console.print("[cyan]3. Starting nginx file server...[/cyan]")

        nginx_container_name = "opencenter-nginx"

        # Check if container already exists
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={nginx_container_name}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            if nginx_container_name in result.stdout:
                # Stop and remove existing container
                subprocess.run(
                    ["docker", "stop", nginx_container_name],
                    capture_output=True,
                    check=False,
                )
                subprocess.run(
                    ["docker", "rm", nginx_container_name],
                    capture_output=True,
                    check=False,
                )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Start nginx container with volume mounts
        try:
            nginx_cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                nginx_container_name,
                "-p",
                f"{nginx_port}:80",
                "-v",
                f"{install_path}/files:/usr/share/nginx/html/files:ro",
                "-v",
                f"{install_path}/debs:/usr/share/nginx/html/debs:ro",
                "-v",
                f"{install_path}/pypi:/usr/share/nginx/html/pypi:ro",
                "nginx:1.29.2",
            ]

            result = subprocess.run(
                nginx_cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            console.print(f"[green]✓ Nginx container started: {nginx_container_name}[/green]\n")

        except subprocess.CalledProcessError as exc:
            console.print(f"[red]✗ Failed to start nginx container[/red]")
            console.print(f"  Exit code: {exc.returncode}")
            if verbose or exc.stderr:
                console.print(f"  Error: {exc.stderr}")

            # Cleanup on failure
            console.print("\n[yellow]Cleaning up partial deployment...[/yellow]")
            _cleanup_services(nginx_container_name, verbose)
            raise typer.Exit(code=1)
        except FileNotFoundError:
            console.print("[red]✗ Docker not found in PATH[/red]")
            console.print("  Install Docker: https://docs.docker.com/get-docker/")
            raise typer.Exit(code=1)

        # Verify service health
        console.print("[cyan]4. Verifying service health...[/cyan]")

        services = [
            ("Nginx file server", f"http://localhost:{nginx_port}/files/", 200),
            ("Nginx debs", f"http://localhost:{nginx_port}/debs/", 200),
            ("Nginx pypi", f"http://localhost:{nginx_port}/pypi/", 200),
            ("Container registry", f"http://localhost:{registry_port}/v2/_catalog", 200),
            ("Git server", f"http://localhost:{git_port}/api/v1/repos/search", 200),
        ]

        failed_checks = []

        for service_name, url, expected_status in services:
            try:
                # Wait a bit for service to be ready
                time.sleep(1)

                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == expected_status:
                        console.print(f"  [green]✓[/green] {service_name}: {url}")
                    else:
                        console.print(
                            f"  [yellow]⚠[/yellow] {service_name}: HTTP {response.status}"
                        )
                        failed_checks.append((service_name, f"HTTP {response.status}"))
            except urllib.error.URLError as exc:
                console.print(f"  [yellow]⚠[/yellow] {service_name}: {exc.reason}")
                failed_checks.append((service_name, str(exc.reason)))
            except Exception as exc:
                console.print(f"  [yellow]⚠[/yellow] {service_name}: {exc}")
                failed_checks.append((service_name, str(exc)))

        console.print()

        # Display service URLs
        if not failed_checks:
            console.print(
                Panel.fit(
                    "[bold green]Deployment successful![/bold green]\n\n"
                    "Service URLs:\n"
                    f"  Files:    http://localhost:{nginx_port}/files/\n"
                    f"  Debs:     http://localhost:{nginx_port}/debs/\n"
                    f"  PyPI:     http://localhost:{nginx_port}/pypi/\n"
                    f"  Registry: http://localhost:{registry_port}/v2/_catalog\n"
                    f"  Git:      http://localhost:{git_port}/",
                    title="Success",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel.fit(
                    f"[bold yellow]Deployment completed with warnings[/bold yellow]\n\n"
                    f"{len(failed_checks)} service(s) failed health check:\n"
                    + "\n".join(f"  - {name}: {error}" for name, error in failed_checks)
                    + "\n\nCheck service logs for details.",
                    title="Warning",
                    border_style="yellow",
                )
            )

    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


def _cleanup_services(nginx_container_name: str, verbose: bool = False) -> None:
    """Clean up partially deployed services.

    Args:
        nginx_container_name: Name of nginx container to remove
        verbose: Enable verbose output
    """
    try:
        # Stop nginx container
        try:
            subprocess.run(
                ["docker", "stop", nginx_container_name],
                capture_output=not verbose,
                check=False,
            )
        except Exception as exc:
            if verbose:
                console.print(f"[yellow]⚠[/yellow] Stop warning: {exc}")

        # Remove nginx container
        try:
            subprocess.run(
                ["docker", "rm", nginx_container_name],
                capture_output=not verbose,
                check=False,
            )
        except Exception as exc:
            if verbose:
                console.print(f"[yellow]⚠[/yellow] Remove warning: {exc}")

        console.print(f"[green]✓[/green] Cleaned up nginx container")
    except Exception as exc:
        if verbose:
            console.print(f"[yellow]⚠[/yellow] Cleanup warning: {exc}")


@app.command()
def version() -> None:
    """Display tool version information.

    Shows the version of opencenter-airgap, Python, and key dependencies.

    Example:
        opencenter-airgap version
    """
    from rich.table import Table
    from opencenter_build import __version__

    console.print(f"[bold green]opencenter-airgap[/bold green] version {__version__}\n")

    # Create version table
    table = Table(title="Environment")
    table.add_column("Component", style="cyan")
    table.add_column("Version")

    # Python version
    table.add_row("Python", sys.version.split()[0])

    # Key dependencies
    dependencies = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("pyyaml", "yaml"),
        ("hypothesis", "hypothesis"),
        ("jsonschema", "jsonschema"),
    ]

    for dep_name, import_name in dependencies:
        try:
            module = __import__(import_name)
            version_str = getattr(module, "__version__", "unknown")
            table.add_row(dep_name, version_str)
        except ImportError:
            table.add_row(dep_name, "[red]not installed[/red]")

    console.print(table)


@app.command()
def release(
    version: Optional[str] = typer.Argument(
        None, help="Version to release (e.g., 1.0.0 or v1.0.0)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without creating tag"
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt"),
) -> None:
    """Create a release tag and push to trigger CI/CD.

    Creates an annotated git tag and pushes to origin, triggering the GitHub
    Actions release workflow to build and publish artifacts.

    Examples:
        Release current version from pyproject.toml:
            opencenter-airgap release

        Release specific version:
            opencenter-airgap release 1.0.1

        Dry run to preview:
            opencenter-airgap release 1.0.1 --dry-run
    """
    import re
    from datetime import datetime

    try:
        # Get version
        if not version:
            # Read from pyproject.toml
            pyproject_path = Path("pyproject.toml")
            if not pyproject_path.exists():
                console.print("[red]Error:[/red] pyproject.toml not found")
                raise typer.Exit(code=1)

            import tomli

            with open(pyproject_path, "rb") as f:
                pyproject = tomli.load(f)

            version = pyproject.get("project", {}).get("version")
            if not version:
                console.print("[red]Error:[/red] No version found in pyproject.toml")
                raise typer.Exit(code=1)

            console.print(f"[cyan]Using version from pyproject.toml:[/cyan] {version}")

        # Normalize version (add 'v' prefix if missing)
        if not version.startswith("v"):
            version = f"v{version}"

        # Validate version format
        if not re.match(r"^v?\d+\.\d+\.\d+$", version):
            console.print(f"[red]Error:[/red] Invalid version format: {version}")
            console.print("Expected format: X.Y.Z or vX.Y.Z")
            raise typer.Exit(code=1)

        # Check git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        if result.stdout.strip():
            console.print("[red]Error:[/red] Working directory is not clean")
            console.print("\nUncommitted changes:")
            console.print(result.stdout)
            console.print("\nCommit or stash changes first")
            raise typer.Exit(code=1)

        # Check remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            console.print("[red]Error:[/red] No git remote 'origin' configured")
            raise typer.Exit(code=1)

        remote_url = result.stdout.strip()

        # Check if tag exists
        result = subprocess.run(
            ["git", "tag", "-l", version],
            capture_output=True,
            text=True,
            check=True,
        )

        if result.stdout.strip():
            console.print(f"[red]Error:[/red] Tag {version} already exists")

            # Show recent tags
            result = subprocess.run(
                ["git", "tag", "-l", "v*", "--sort=-version:refname"],
                capture_output=True,
                text=True,
                check=True,
            )
            recent_tags = result.stdout.strip().split("\n")[:5]
            console.print("\nRecent tags:")
            for tag in recent_tags:
                console.print(f"  {tag}")

            raise typer.Exit(code=1)

        # Get current branch and commit
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = result.stdout.strip()

        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        latest_commit = result.stdout.strip()

        # Display release info
        console.print()
        console.print(
            Panel.fit(
                f"[bold]Release Information[/bold]\n\n"
                f"Version: [cyan]{version}[/cyan]\n"
                f"Branch: [cyan]{current_branch}[/cyan]\n"
                f"Commit: [cyan]{latest_commit}[/cyan]\n"
                f"Remote: [cyan]{remote_url}[/cyan]\n"
                f"Time: [cyan]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/cyan]",
                title="Release",
                border_style="cyan",
            )
        )

        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            console.print("\nWould execute:")
            console.print(f"  git tag -a {version} -m 'Release {version}'")
            console.print(f"  git push origin {version}")
            return

        # Confirm release
        if not force:
            console.print()
            confirm = typer.confirm("Create and push release tag?")
            if not confirm:
                console.print("[yellow]Release cancelled[/yellow]")
                return

        # Create tag
        console.print(f"\n[cyan]Creating tag:[/cyan] {version}")
        result = subprocess.run(
            ["git", "tag", "-a", version, "-m", f"Release {version}"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            console.print(f"[red]Error:[/red] Failed to create tag")
            console.print(result.stderr)
            raise typer.Exit(code=1)

        console.print("[green]✓[/green] Tag created")

        # Push tag
        console.print(f"[cyan]Pushing tag to origin...[/cyan]")
        result = subprocess.run(
            ["git", "push", "origin", version],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            console.print(f"[red]Error:[/red] Failed to push tag")
            console.print(result.stderr)
            console.print(f"\n[yellow]Tag created locally but not pushed[/yellow]")
            console.print(f"To push manually: git push origin {version}")
            console.print(f"To delete tag: git tag -d {version}")
            raise typer.Exit(code=1)

        console.print("[green]✓[/green] Tag pushed")

        # Extract GitHub repo from remote URL
        github_match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote_url)
        if github_match:
            repo_path = github_match.group(1)
            actions_url = f"https://github.com/{repo_path}/actions"

            console.print()
            console.print(
                Panel.fit(
                    f"[bold green]Release tag created successfully![/bold green]\n\n"
                    f"GitHub Actions will build and publish the release.\n\n"
                    f"Monitor progress:\n"
                    f"[cyan]{actions_url}[/cyan]",
                    title="Success",
                    border_style="green",
                )
            )
        else:
            console.print()
            console.print("[bold green]Release tag created successfully![/bold green]")
            console.print("CI/CD pipeline will build and publish the release")

    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Error:[/red] Git command failed: {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
