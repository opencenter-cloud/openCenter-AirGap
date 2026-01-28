#!/usr/bin/env python3
"""Generate final zarf.yaml from template with dynamic images block.

This script reads zarf.yaml.template, generates the images block from
config/all-images.txt, and produces the final zarf.yaml file.

Usage:
    python3 scripts/build/generate_zarf_yaml.py
    python3 scripts/build/generate_zarf_yaml.py --dry-run
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple


def generate_images_block() -> Tuple[str, int]:
    """Generate images block by calling generate_zarf_images_block.py.

    Returns:
        Tuple of (yaml_block, image_count)

    Raises:
        subprocess.CalledProcessError: If image generation fails
    """
    script_path = Path(__file__).parent / "generate_zarf_images_block.py"

    result = subprocess.run(
        ["python3", str(script_path)], capture_output=True, text=True, check=True
    )

    yaml_block = result.stdout

    # Extract image count from stderr
    image_count = 0
    for line in result.stderr.splitlines():
        if "Generated images block with" in line:
            try:
                image_count = int(line.split("with")[1].split("images")[0].strip())
            except (IndexError, ValueError):
                pass

    return yaml_block, image_count


def generate_zarf_yaml(dry_run: bool = False) -> None:
    """Generate final zarf.yaml from template.

    Args:
        dry_run: If True, print output instead of writing file

    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    project_root = Path(__file__).parent.parent.parent
    template_file = project_root / "zarf.yaml.template"
    output_file = project_root / "zarf.yaml"

    if not template_file.exists():
        raise FileNotFoundError(
            f"Template not found: {template_file}\n" "Run: cp zarf.yaml zarf.yaml.template"
        )

    # Read template
    with open(template_file, encoding="utf-8") as f:
        template = f.read()

    # Check for placeholder
    if "###IMAGES_BLOCK###" not in template:
        print("Error: Template missing ###IMAGES_BLOCK### placeholder", file=sys.stderr)
        sys.exit(1)

    # Generate images block
    print("Generating images block...", file=sys.stderr)
    try:
        images_block, image_count = generate_images_block()
    except subprocess.CalledProcessError as e:
        print(f"Error generating images block:", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

    # Replace placeholder
    final_yaml = template.replace("###IMAGES_BLOCK###", images_block)

    if dry_run:
        print("=== Generated zarf.yaml (dry-run) ===")
        print(final_yaml)
        print(f"\n=== Summary: {image_count} images ===", file=sys.stderr)
    else:
        # Write final zarf.yaml
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_yaml)

        print(f"✓ Generated {output_file}", file=sys.stderr)
        print(f"✓ Included {image_count} container images", file=sys.stderr)


def main():
    """Main entry point."""
    dry_run = "--dry-run" in sys.argv

    try:
        generate_zarf_yaml(dry_run=dry_run)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
