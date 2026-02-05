#!/usr/bin/env python3
"""Generate Zarf images block from config/all-images.txt.

This script reads the consolidated image list and generates a YAML fragment
that can be injected into zarf.yaml. It filters out comments and empty lines,
and outputs valid YAML syntax for the images block.

Usage:
    python3 scripts/build/generate_zarf_images_block.py > images_block.yaml
    python3 scripts/build/generate_zarf_images_block.py --validate
"""

import sys
from pathlib import Path
from typing import List


def parse_image_list(image_file: Path) -> List[str]:
    """Extract non-comment, non-empty lines from image list.

    Args:
        image_file: Path to the image list file

    Returns:
        List of image references (registry/repo:tag format)

    Raises:
        FileNotFoundError: If image file doesn't exist
    """
    if not image_file.exists():
        raise FileNotFoundError(f"Image list not found: {image_file}")

    images = []
    with open(image_file, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Basic validation: should contain at least one character
            if ":" not in line:
                print(f"Warning: Line {line_num} missing tag: {line}", file=sys.stderr)

            images.append(line)

    return images


def generate_yaml_block(images: List[str], indent: int = 2) -> str:
    """Generate YAML images block for zarf.yaml.

    Args:
        images: List of image references
        indent: Number of spaces for base indentation

    Returns:
        YAML-formatted string with images block
    """
    base_indent = " " * indent
    item_indent = " " * (indent + 2)

    lines = [f"{base_indent}images:"]
    for img in images:
        lines.append(f"{item_indent}- {img}")

    return "\n".join(lines)


def validate_images(images: List[str]) -> bool:
    """Validate image references for common issues.

    Args:
        images: List of image references to validate

    Returns:
        True if all images are valid, False otherwise
    """
    valid = True

    for img in images:
        # Check for tag
        if ":" not in img:
            print(f"Error: Image missing tag: {img}", file=sys.stderr)
            valid = False

        # Check for invalid characters
        if " " in img:
            print(f"Error: Image contains spaces: {img}", file=sys.stderr)
            valid = False

        # Check for 'latest' tag (discouraged in air-gap)
        if img.endswith(":latest"):
            print(f"Warning: Image uses 'latest' tag: {img}", file=sys.stderr)

    return valid


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent.parent
    image_file = project_root / "config" / "all-images.txt"

    # Check for validation flag
    validate_only = "--validate" in sys.argv

    try:
        images = parse_image_list(image_file)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run scripts/build/generate_image_lists.sh first", file=sys.stderr)
        sys.exit(1)

    if not images:
        print("Error: No images found in image list", file=sys.stderr)
        sys.exit(1)

    # Validate images
    if not validate_images(images):
        print("\nValidation failed. Fix errors above.", file=sys.stderr)
        sys.exit(1)

    if validate_only:
        print(f"✓ Validated {len(images)} images", file=sys.stderr)
        sys.exit(0)

    # Generate YAML block
    yaml_block = generate_yaml_block(images)
    print(yaml_block)

    # Print summary to stderr (won't interfere with stdout)
    print(f"\n# Generated images block with {len(images)} images", file=sys.stderr)
    print(f"# Source: {image_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
