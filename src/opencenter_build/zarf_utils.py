"""Zarf package generation and manipulation utilities.

This module provides functions for generating Zarf package definitions
and working with Zarf artifacts.
"""

import shutil
from pathlib import Path
from typing import Any

import yaml

from opencenter_build.exceptions import PackageError
from opencenter_build.logging import get_logger
from opencenter_build.transaction import transactional_operation

logger = get_logger(__name__)


def generate_zarf_component(
    name: str,
    description: str,
    required: bool = True,
    files: list[dict[str, str]] | None = None,
    images: list[str] | None = None,
    actions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a Zarf component definition.

    Args:
        name: Component name
        description: Component description
        required: Whether component is required (default True)
        files: List of file definitions with source and target
        images: List of container image references
        actions: Component actions (onCreate, onDeploy, etc.)

    Returns:
        Component definition dictionary

    Example:
        >>> component = generate_zarf_component(
        ...     name="kubespray",
        ...     description="Kubespray offline assets",
        ...     files=[{"source": "build/files", "target": "/opt/opencenter/files"}]
        ... )
    """
    component: dict[str, Any] = {
        "name": name,
        "description": description,
        "required": required,
    }

    if files:
        component["files"] = files

    if images:
        component["images"] = images

    if actions:
        component["actions"] = actions

    return component


def generate_zarf_metadata(
    name: str,
    version: str,
    description: str,
    architecture: str = "amd64",
) -> dict[str, Any]:
    """Generate Zarf package metadata.

    Args:
        name: Package name
        version: Package version
        description: Package description
        architecture: Target architecture (default "amd64")

    Returns:
        Metadata dictionary

    Example:
        >>> metadata = generate_zarf_metadata(
        ...     name="opencenter-airgap",
        ...     version="1.0.0",
        ...     description="Air-gapped Kubernetes deployment"
        ... )
    """
    return {
        "name": name,
        "version": version,
        "description": description,
        "architecture": architecture,
    }


def write_zarf_yaml(
    output_path: Path,
    metadata: dict[str, Any],
    components: list[dict[str, Any]],
    variables: list[dict[str, Any]] | None = None,
    constants: list[dict[str, Any]] | None = None,
) -> None:
    """Write Zarf package definition to YAML file with automatic rollback.

    Creates a backup of existing file before writing. If an error occurs,
    the backup is automatically restored.

    Args:
        output_path: Path to output zarf.yaml file
        metadata: Package metadata
        components: List of component definitions
        variables: Optional list of package variables
        constants: Optional list of package constants

    Raises:
        PackageError: If file cannot be written

    Example:
        >>> metadata = generate_zarf_metadata("pkg", "1.0.0", "desc")
        >>> components = [generate_zarf_component("comp", "desc")]
        >>> write_zarf_yaml(Path("zarf.yaml"), metadata, components)
    """
    zarf_def: dict[str, Any] = {
        "kind": "ZarfPackageConfig",
        "metadata": metadata,
        "components": components,
    }

    if variables:
        zarf_def["variables"] = variables

    if constants:
        zarf_def["constants"] = constants

    try:
        with transactional_operation() as tx:
            # Backup existing file if present
            if output_path.exists():
                backup_path = output_path.with_suffix(".yaml.backup")
                shutil.copy(output_path, backup_path)
                tx.add_rollback(lambda: shutil.move(str(backup_path), str(output_path)))

            # Write new file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            content = yaml.safe_dump(zarf_def, default_flow_style=False, sort_keys=False, width=120)
            output_path.write_text(content)

            # Validate structure
            errors = validate_zarf_structure(zarf_def)
            if errors:
                raise PackageError(f"Generated invalid zarf.yaml: {', '.join(errors)}")

    except PackageError:
        raise
    except Exception as exc:
        raise PackageError(f"Failed to write zarf.yaml to {output_path}: {exc}") from exc


def read_zarf_yaml(zarf_file: Path) -> dict[str, Any]:
    """Read and parse Zarf package definition.

    Args:
        zarf_file: Path to zarf.yaml file

    Returns:
        Parsed Zarf package definition

    Raises:
        PackageError: If file cannot be read or parsed

    Example:
        >>> zarf_def = read_zarf_yaml(Path("zarf.yaml"))
        >>> print(zarf_def["metadata"]["name"])
    """
    if not zarf_file.exists():
        raise PackageError(f"Zarf file not found: {zarf_file}")

    try:
        content = zarf_file.read_text()
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise PackageError(f"Invalid zarf.yaml: expected dict, got {type(data).__name__}")
        return data
    except yaml.YAMLError as exc:
        raise PackageError(f"Failed to parse {zarf_file}: {exc}") from exc
    except Exception as exc:
        raise PackageError(f"Failed to read {zarf_file}: {exc}") from exc


def validate_zarf_structure(zarf_def: dict[str, Any]) -> list[str]:
    """Validate Zarf package definition structure.

    Checks for required fields and common issues.

    Args:
        zarf_def: Parsed Zarf package definition

    Returns:
        List of validation error messages (empty if valid)

    Example:
        >>> zarf_def = read_zarf_yaml(Path("zarf.yaml"))
        >>> errors = validate_zarf_structure(zarf_def)
        >>> if errors:
        ...     print("Validation errors:", errors)
    """
    errors: list[str] = []

    # Check kind
    if zarf_def.get("kind") != "ZarfPackageConfig":
        errors.append("Missing or invalid 'kind' field (expected 'ZarfPackageConfig')")

    # Check metadata
    metadata = zarf_def.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("Missing or invalid 'metadata' field")
    else:
        for field in ["name", "version", "description"]:
            if not metadata.get(field):
                errors.append(f"Missing required metadata field: {field}")

    # Check components
    components = zarf_def.get("components", [])
    if not isinstance(components, list):
        errors.append("Missing or invalid 'components' field")
    elif not components:
        errors.append("Package must have at least one component")
    else:
        for idx, component in enumerate(components):
            if not isinstance(component, dict):
                errors.append(f"Component {idx} is not a dict")
                continue
            if not component.get("name"):
                errors.append(f"Component {idx} missing 'name' field")
            if not component.get("description"):
                errors.append(f"Component {idx} missing 'description' field")

    return errors


def generate_images_block() -> tuple[str, int]:
    """Generate images block by reading image list and formatting as YAML.

    Reads the all-images.txt file and generates a YAML images block
    suitable for inclusion in a Zarf component.

    Returns:
        Tuple of (yaml_block, image_count)

    Raises:
        PackageError: If image list cannot be read or processed

    Example:
        >>> yaml_block, count = generate_images_block()
        >>> print(f"Generated block with {count} images")
    """
    from pathlib import Path
    from opencenter_build.image_utils import parse_image_list, generate_yaml_block

    project_root = Path.cwd()
    image_list_file = project_root / "config" / "all-images.txt"

    if not image_list_file.exists():
        raise PackageError(f"Image list not found: {image_list_file}")

    try:
        images = parse_image_list(image_list_file)
        yaml_block = generate_yaml_block(images, indent=2)
        return yaml_block, len(images)
    except Exception as exc:
        raise PackageError(f"Failed to generate images block: {exc}") from exc


def generate_zarf_yaml_from_template(
    template_path: Path,
    output_path: Path,
    dry_run: bool = False,
) -> None:
    """Generate final zarf.yaml from template with automatic rollback.

    Reads a template file, generates the images block, and writes
    the final zarf.yaml with all components. Creates backup before
    writing and restores on failure.

    Args:
        template_path: Path to zarf.yaml template
        output_path: Path to output zarf.yaml
        dry_run: If True, print output instead of writing file

    Raises:
        PackageError: If template cannot be read or output cannot be written

    Example:
        >>> generate_zarf_yaml_from_template(
        ...     Path("templates/zarf.yaml.template"),
        ...     Path("zarf.yaml")
        ... )
    """
    if not template_path.exists():
        raise PackageError(f"Template not found: {template_path}")

    try:
        # Read template
        template_content = template_path.read_text()

        # Generate images block
        images_block, image_count = generate_images_block()

        # Replace placeholder in template
        # Assuming template has a marker like "# IMAGES_PLACEHOLDER"
        final_content = template_content.replace("# IMAGES_PLACEHOLDER", images_block)

        if dry_run:
            logger.info(f"Generated zarf.yaml with {image_count} images:")
            logger.info(final_content)
        else:
            with transactional_operation() as tx:
                # Backup existing file if present
                if output_path.exists():
                    backup_path = output_path.with_suffix(".yaml.backup")
                    shutil.copy(output_path, backup_path)
                    tx.add_rollback(lambda: shutil.move(str(backup_path), str(output_path)))

                # Write new file
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(final_content)

                logger.info(f"Generated {output_path} with {image_count} images")

    except PackageError:
        raise
    except Exception as exc:
        raise PackageError(f"Failed to generate zarf.yaml: {exc}") from exc
