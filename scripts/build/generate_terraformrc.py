#!/usr/bin/env python3
"""
Generate .terraformrc configuration for offline Terraform operation.

This script creates a Terraform CLI configuration file that:
1. Points to a filesystem mirror for provider plugins
2. Disables checkpoint and upgrade checks
3. Configures plugin cache directory

Requirements: 4.5, 4.6
"""

import argparse
import os
import sys
from pathlib import Path


def generate_terraformrc(
    mirror_path: str,
    cache_dir: str,
    output_path: str,
    disable_checkpoint: bool = True,
    disable_upgrade_check: bool = True
) -> None:
    """
    Generate .terraformrc configuration file.
    
    Args:
        mirror_path: Absolute path to filesystem mirror directory
        cache_dir: Absolute path to plugin cache directory
        output_path: Path where .terraformrc should be written
        disable_checkpoint: Disable checkpoint API calls
        disable_upgrade_check: Disable upgrade version checks
    """
    # Validate mirror path exists
    if not os.path.isdir(mirror_path):
        raise ValueError(f"Mirror path does not exist: {mirror_path}")
    
    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)
    
    # Generate configuration content
    config_lines = []
    
    # Plugin cache directory
    config_lines.append(f'plugin_cache_dir = "{cache_dir}"')
    config_lines.append('')
    
    # Disable checkpoint
    if disable_checkpoint:
        config_lines.append('disable_checkpoint = true')
    
    # Disable upgrade check
    if disable_upgrade_check:
        config_lines.append('disable_checkpoint_signature = true')
    
    config_lines.append('')
    
    # Provider installation from filesystem mirror
    config_lines.append('provider_installation {')
    config_lines.append('  filesystem_mirror {')
    config_lines.append(f'    path    = "{mirror_path}"')
    config_lines.append('    include = ["*/*"]')
    config_lines.append('  }')
    config_lines.append('')
    config_lines.append('  # Disable direct installation from registry')
    config_lines.append('  direct {')
    config_lines.append('    exclude = ["*/*"]')
    config_lines.append('  }')
    config_lines.append('}')
    config_lines.append('')
    
    # Write configuration file
    config_content = '\n'.join(config_lines)
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(config_content)
    
    print(f"Generated .terraformrc at: {output_path}")
    print(f"  Mirror path: {mirror_path}")
    print(f"  Cache directory: {cache_dir}")
    print(f"  Checkpoint disabled: {disable_checkpoint}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate .terraformrc for offline Terraform operation'
    )
    parser.add_argument(
        '--mirror-path',
        required=True,
        help='Absolute path to Terraform filesystem mirror'
    )
    parser.add_argument(
        '--cache-dir',
        required=True,
        help='Absolute path to plugin cache directory'
    )
    parser.add_argument(
        '--output',
        default='.terraformrc',
        help='Output path for .terraformrc file (default: .terraformrc)'
    )
    parser.add_argument(
        '--enable-checkpoint',
        action='store_true',
        help='Enable checkpoint API calls (default: disabled)'
    )
    
    args = parser.parse_args()
    
    try:
        generate_terraformrc(
            mirror_path=os.path.abspath(args.mirror_path),
            cache_dir=os.path.abspath(args.cache_dir),
            output_path=args.output,
            disable_checkpoint=not args.enable_checkpoint
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
