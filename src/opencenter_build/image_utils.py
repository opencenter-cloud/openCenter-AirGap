"""Container image parsing and manipulation utilities.

This module provides functions for parsing container image references,
extracting components, and validating image names.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from opencenter_build.exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class ImageReference:
    """Parsed container image reference.

    Attributes:
        registry: Registry hostname (e.g., "docker.io", "gcr.io")
        repository: Repository path (e.g., "library/nginx", "bitnami/postgresql")
        tag: Image tag (e.g., "latest", "1.21.0")
        digest: Optional SHA256 digest
        original: Original unparsed image reference
    """

    registry: str
    repository: str
    tag: str
    digest: Optional[str]
    original: str

    def __str__(self) -> str:
        """Return canonical image reference string."""
        ref = f"{self.registry}/{self.repository}:{self.tag}"
        if self.digest:
            ref += f"@{self.digest}"
        return ref


def parse_image_reference(image: str) -> ImageReference:
    """Parse container image reference into components.

    Handles various image reference formats:
    - nginx:1.21
    - docker.io/library/nginx:1.21
    - gcr.io/project/image:tag@sha256:abc123...
    - quay.io/org/repo:v1.0.0

    Args:
        image: Image reference string

    Returns:
        Parsed ImageReference object

    Raises:
        ValidationError: If image reference is invalid

    Example:
        >>> ref = parse_image_reference("nginx:1.21")
        >>> print(ref.registry)
        docker.io
        >>> print(ref.repository)
        library/nginx
        >>> print(ref.tag)
        1.21
    """
    if not image or not image.strip():
        raise ValidationError("Image reference cannot be empty")

    original = image.strip()
    digest: Optional[str] = None

    # Extract digest if present (image@sha256:...)
    if "@" in original:
        image, digest = original.rsplit("@", 1)
        if not digest.startswith("sha256:"):
            raise ValidationError(f"Invalid digest format in: {original}")

    # Extract tag (default to "latest" if not specified)
    tag = "latest"
    if ":" in image:
        image, tag = image.rsplit(":", 1)

    # Parse registry and repository
    parts = image.split("/")

    if len(parts) == 1:
        # Short form: nginx -> docker.io/library/nginx
        registry = "docker.io"
        repository = f"library/{parts[0]}"
    elif len(parts) == 2:
        # Could be: registry/image or org/image
        if "." in parts[0] or ":" in parts[0] or parts[0] == "localhost":
            # Has registry: gcr.io/image
            registry = parts[0]
            repository = parts[1]
        else:
            # No registry: org/image -> docker.io/org/image
            registry = "docker.io"
            repository = image
    else:
        # Full form: registry/org/image
        registry = parts[0]
        repository = "/".join(parts[1:])

    return ImageReference(
        registry=registry,
        repository=repository,
        tag=tag,
        digest=digest,
        original=original,
    )


def normalize_image_reference(image: str) -> str:
    """Normalize image reference to canonical form.

    Expands short-form references to fully qualified form with registry.

    Args:
        image: Image reference string

    Returns:
        Normalized image reference

    Example:
        >>> normalize_image_reference("nginx:1.21")
        'docker.io/library/nginx:1.21'
    """
    ref = parse_image_reference(image)
    return str(ref)


def extract_images_from_file(file_path: str) -> list[str]:
    """Extract image references from a text file.

    Reads file line by line, extracting valid image references.
    Skips comments (lines starting with #) and empty lines.

    Args:
        file_path: Path to file containing image references

    Returns:
        List of image reference strings

    Raises:
        ValidationError: If file cannot be read

    Example:
        >>> images = extract_images_from_file("config/all-images.txt")
        >>> print(len(images))
        139
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            images = []
            for line in file:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                images.append(line)
            return images
    except Exception as exc:
        raise ValidationError(f"Failed to read image file {file_path}: {exc}") from exc


def validate_image_tag(tag: str) -> bool:
    """Validate image tag format.

    Tags must match Docker tag naming rules:
    - Alphanumeric, dots, dashes, underscores
    - Max 128 characters
    - Cannot start with dot or dash

    Args:
        tag: Image tag string

    Returns:
        True if valid, False otherwise

    Example:
        >>> validate_image_tag("v1.21.0")
        True
        >>> validate_image_tag(".invalid")
        False
    """
    if not tag or len(tag) > 128:
        return False

    # Tag pattern: alphanumeric, dots, dashes, underscores
    # Cannot start with dot or dash
    pattern = r"^[a-zA-Z0-9_][a-zA-Z0-9._-]*$"
    return bool(re.match(pattern, tag))


def parse_image_list(image_file: str | Path) -> list[str]:
    """Extract non-comment, non-empty lines from image list file.

    Reads an image list file and returns valid image references,
    skipping comments (lines starting with #) and empty lines.

    Args:
        image_file: Path to image list file

    Returns:
        List of image reference strings

    Raises:
        ValidationError: If file cannot be read

    Example:
        >>> images = parse_image_list("config/all-images.txt")
        >>> print(len(images))
        139
    """
    file_path = Path(image_file)
    if not file_path.exists():
        raise ValidationError(f"Image list file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            images = []
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                images.append(line)
            return images
    except Exception as exc:
        raise ValidationError(f"Failed to read image list {file_path}: {exc}") from exc


def generate_yaml_block(images: list[str], indent: int = 2) -> str:
    """Generate YAML images block for zarf.yaml component.

    Creates a properly indented YAML block with image references.

    Args:
        images: List of image reference strings
        indent: Number of spaces for base indentation (default 2)

    Returns:
        Formatted YAML string with images block

    Example:
        >>> images = ["nginx:1.29.2", "registry:2.8.3"]
        >>> yaml_block = generate_yaml_block(images, indent=2)
        >>> print(yaml_block)
          images:
            - nginx:1.29.2
            - registry:2.8.3
    """
    if not images:
        return ""

    base_indent = " " * indent
    item_indent = " " * (indent + 2)

    lines = [f"{base_indent}images:"]
    for image in images:
        lines.append(f"{item_indent}- {image}")

    return "\n".join(lines)


def validate_images(images: list[str]) -> bool:
    """Validate image references for common issues.

    Checks for:
    - Missing tags (warns but allows)
    - Invalid characters (spaces)
    - Use of 'latest' tag (warns but allows)

    Args:
        images: List of image reference strings

    Returns:
        True if all images are valid, False if any have errors

    Example:
        >>> images = ["nginx:1.29.2", "registry:2.8.3"]
        >>> validate_images(images)
        True
    """
    all_valid = True

    for image in images:
        # Check for spaces (invalid)
        if " " in image:
            logger.error(f"Image contains spaces: {image}")
            all_valid = False
            continue

        # Check for missing tag (warning)
        if ":" not in image:
            logger.warning(f"Image missing tag (will default to 'latest'): {image}")
            all_valid = False
            continue

        # Check for 'latest' tag (warning)
        if image.endswith(":latest"):
            logger.warning(f"Image uses 'latest' tag (not recommended): {image}")
            # Don't set all_valid to False for latest tag, just warn
            continue

    return all_valid


import subprocess
from typing import Dict, Any, List

from opencenter_build.exceptions import BuildError


class ImageManager:
    """Manage container images using Skopeo and Podman.

    This class provides a unified interface for container image operations
    using Skopeo (for registry operations) and Podman (for tar operations).

    Design rationale:
    - Skopeo: Daemonless, no root required, optimized for registry operations
    - Podman: Docker-compatible CLI for tar archive operations
    - No Docker: Eliminates daemon dependency, improves security posture

    Attributes:
        skopeo_path: Path to skopeo binary
        podman_path: Path to podman binary
    """

    def __init__(self, skopeo_path: str = "skopeo", podman_path: str = "podman"):
        """Initialize ImageManager and verify tools are available.

        Args:
            skopeo_path: Path to skopeo binary (default: "skopeo")
            podman_path: Path to podman binary (default: "podman")

        Raises:
            BuildError: If skopeo or podman not found
        """
        self.skopeo_path = skopeo_path
        self.podman_path = podman_path
        self._verify_tools()

    def _verify_tools(self) -> None:
        """Verify Skopeo and Podman are installed and accessible.

        Raises:
            BuildError: If tools not found or not executable
        """
        for tool, path in [("skopeo", self.skopeo_path), ("podman", self.podman_path)]:
            try:
                result = subprocess.run(
                    [path, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    raise BuildError(
                        f"{tool} not working properly. " f"Install: sudo apt-get install {tool}"
                    )
                logger.info(f"{tool}: {result.stdout.strip()}")
            except FileNotFoundError:
                raise BuildError(
                    f"{tool} not found at '{path}'. " f"Install: sudo apt-get install {tool}"
                )
            except subprocess.TimeoutExpired:
                raise BuildError(f"{tool} command timed out")

    def copy_image_to_dir(self, source_image: str, dest_dir: Path, insecure: bool = False) -> None:
        """Copy image from registry to directory using Skopeo.

        Uses Skopeo for daemonless, direct registry-to-directory copy.
        Ideal for air-gap image collection.

        Args:
            source_image: Source image reference (e.g., "docker://nginx:1.29.2")
            dest_dir: Destination directory path
            insecure: Allow insecure connections (default: False)

        Raises:
            BuildError: If copy operation fails

        Example:
            >>> mgr = ImageManager()
            >>> mgr.copy_image_to_dir(
            ...     "docker://registry.k8s.io/pause:3.9",
            ...     Path("build/images/pause")
            ... )
        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = [self.skopeo_path, "copy"]
        if insecure:
            cmd.append("--insecure-policy")

        # Add source transport if not specified
        if "://" not in source_image:
            source_image = f"docker://{source_image}"

        cmd.extend([source_image, f"dir:{dest_dir}"])

        logger.info(f"Copying {source_image} to {dest_dir}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minutes

            if result.returncode != 0:
                raise BuildError(f"Failed to copy image {source_image}: {result.stderr}")

            logger.debug(f"Copy output: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise BuildError(f"Timeout copying image {source_image}")
        except Exception as e:
            raise BuildError(f"Error copying image {source_image}: {e}")

    def sync_images(
        self,
        image_list: Path,
        dest_dir: Path,
        src_transport: str = "docker",
        dest_transport: str = "dir",
    ) -> None:
        """Sync multiple images using Skopeo sync.

        Efficiently syncs multiple images from a list file.

        Args:
            image_list: Path to file containing image references
            dest_dir: Destination directory
            src_transport: Source transport type (default: "docker")
            dest_transport: Destination transport type (default: "dir")

        Raises:
            BuildError: If sync operation fails

        Example:
            >>> mgr = ImageManager()
            >>> mgr.sync_images(
            ...     Path("config/images.yaml"),
            ...     Path("build/images")
            ... )
        """
        if not image_list.exists():
            raise BuildError(f"Image list not found: {image_list}")

        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.skopeo_path,
            "sync",
            "--src",
            src_transport,
            "--dest",
            dest_transport,
            str(image_list),
            str(dest_dir),
        ]

        logger.info(f"Syncing images from {image_list} to {dest_dir}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes

            if result.returncode != 0:
                raise BuildError(f"Failed to sync images: {result.stderr}")

            logger.debug(f"Sync output: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise BuildError("Timeout syncing images")
        except Exception as e:
            raise BuildError(f"Error syncing images: {e}")

    def save_image_to_tar(
        self, image_ref: str, output_file: Path, format: str = "oci-archive"
    ) -> None:
        """Save image to tar archive using Podman.

        Args:
            image_ref: Image reference to save
            output_file: Output tar file path
            format: Archive format (default: "oci-archive")

        Raises:
            BuildError: If save operation fails

        Example:
            >>> mgr = ImageManager()
            >>> mgr.save_image_to_tar(
            ...     "nginx:1.29.2",
            ...     Path("build/images/nginx.tar")
            ... )
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)

        cmd = [self.podman_path, "save", "--format", format, "-o", str(output_file), image_ref]

        logger.info(f"Saving {image_ref} to {output_file}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minutes

            if result.returncode != 0:
                raise BuildError(f"Failed to save image {image_ref}: {result.stderr}")

            logger.debug(f"Save output: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise BuildError(f"Timeout saving image {image_ref}")
        except Exception as e:
            raise BuildError(f"Error saving image {image_ref}: {e}")

    def load_image_from_tar(self, tar_file: Path, quiet: bool = False) -> str:
        """Load image from tar archive using Podman.

        Args:
            tar_file: Path to tar archive
            quiet: Suppress output (default: False)

        Returns:
            Loaded image reference

        Raises:
            BuildError: If load operation fails

        Example:
            >>> mgr = ImageManager()
            >>> ref = mgr.load_image_from_tar(Path("build/images/nginx.tar"))
            >>> print(ref)
            nginx:1.29.2
        """
        if not tar_file.exists():
            raise BuildError(f"Tar file not found: {tar_file}")

        cmd = [self.podman_path, "load"]
        if quiet:
            cmd.append("--quiet")
        cmd.extend(["-i", str(tar_file)])

        logger.info(f"Loading image from {tar_file}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 minutes

            if result.returncode != 0:
                raise BuildError(f"Failed to load image from {tar_file}: {result.stderr}")

            # Extract image reference from output
            # Output format: "Loaded image: docker.io/library/nginx:1.29.2"
            for line in result.stdout.splitlines():
                if "Loaded image:" in line:
                    image_ref = line.split("Loaded image:")[-1].strip()
                    logger.info(f"Loaded: {image_ref}")
                    return image_ref

            # If no "Loaded image:" line, return empty string
            logger.warning(f"Could not extract image reference from output: {result.stdout}")
            return ""

        except subprocess.TimeoutExpired:
            raise BuildError(f"Timeout loading image from {tar_file}")
        except Exception as e:
            raise BuildError(f"Error loading image from {tar_file}: {e}")

    def list_local_images(self) -> List[str]:
        """List locally stored images using Podman.

        Returns:
            List of image references

        Raises:
            BuildError: If list operation fails

        Example:
            >>> mgr = ImageManager()
            >>> images = mgr.list_local_images()
            >>> print(len(images))
            15
        """
        cmd = [self.podman_path, "images", "--format", "{{.Repository}}:{{.Tag}}"]

        logger.debug("Listing local images")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise BuildError(f"Failed to list images: {result.stderr}")

            images = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and not line.startswith("<none>")
            ]

            logger.debug(f"Found {len(images)} local images")
            return images

        except subprocess.TimeoutExpired:
            raise BuildError("Timeout listing images")
        except Exception as e:
            raise BuildError(f"Error listing images: {e}")

    def inspect_image(self, image_ref: str) -> Dict[str, Any]:
        """Inspect image metadata using Skopeo.

        Args:
            image_ref: Image reference to inspect

        Returns:
            Dictionary containing image metadata

        Raises:
            BuildError: If inspect operation fails

        Example:
            >>> mgr = ImageManager()
            >>> metadata = mgr.inspect_image("nginx:1.29.2")
            >>> print(metadata["Name"])
            docker.io/library/nginx:1.29.2
        """
        import json

        # Add docker:// transport if not specified
        if "://" not in image_ref:
            image_ref = f"docker://{image_ref}"

        cmd = [self.skopeo_path, "inspect", image_ref]

        logger.debug(f"Inspecting {image_ref}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                raise BuildError(f"Failed to inspect image {image_ref}: {result.stderr}")

            metadata: Dict[str, Any] = json.loads(result.stdout)
            return metadata

        except subprocess.TimeoutExpired:
            raise BuildError(f"Timeout inspecting image {image_ref}")
        except json.JSONDecodeError as e:
            raise BuildError(f"Failed to parse inspect output: {e}")
        except Exception as e:
            raise BuildError(f"Error inspecting image {image_ref}: {e}")
