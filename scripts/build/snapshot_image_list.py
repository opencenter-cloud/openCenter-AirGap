#!/usr/bin/env python3
"""
Image List Snapshot Utility

Extracts image names, tags, and digests from a Zarf package and exports
to JSON format for determinism comparison.

Usage:
    python3 snapshot_image_list.py <zarf-package> <output-json>
    python3 snapshot_image_list.py dist/zarf-package-*.tar.zst snapshot.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


def run_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """
    Execute a shell command and return the result.
    
    Args:
        cmd: Command and arguments as list
        check: Whether to raise exception on non-zero exit
        
    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(cmd)}", file=sys.stderr)
        print(f"Exit code: {e.returncode}", file=sys.stderr)
        print(f"Stderr: {e.stderr}", file=sys.stderr)
        raise


def check_zarf_installed() -> bool:
    """
    Check if Zarf CLI is installed and available.
    
    Returns:
        True if Zarf is installed, False otherwise
    """
    try:
        result = run_command(['zarf', 'version'], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def inspect_zarf_package(package_path: Path) -> Dict:
    """
    Inspect a Zarf package and extract metadata.
    
    Args:
        package_path: Path to Zarf package file
        
    Returns:
        Dictionary containing package metadata
        
    Raises:
        RuntimeError: If inspection fails
    """
    if not package_path.exists():
        raise FileNotFoundError(f"Package not found: {package_path}")
    
    print(f"Inspecting Zarf package: {package_path}")
    
    result = run_command(['zarf', 'package', 'inspect', str(package_path), '--output-format=json'])
    
    try:
        metadata = json.loads(result.stdout)
        return metadata
    except json.JSONDecodeError as e:
        print(f"Error parsing Zarf inspect output: {e}", file=sys.stderr)
        print(f"Output: {result.stdout}", file=sys.stderr)
        raise RuntimeError("Failed to parse Zarf package metadata")


def extract_images_from_metadata(metadata: Dict) -> List[Dict[str, str]]:
    """
    Extract image information from Zarf package metadata.
    
    Args:
        metadata: Zarf package metadata dictionary
        
    Returns:
        List of image dictionaries with name, tag, digest
    """
    images = []
    
    # Navigate metadata structure to find images
    # Zarf metadata structure: metadata -> components -> images
    components = metadata.get('components', [])
    
    for component in components:
        component_name = component.get('name', 'unknown')
        component_images = component.get('images', [])
        
        for image in component_images:
            # Image can be a string or a dict
            if isinstance(image, str):
                # Parse image string: registry/repo:tag or registry/repo@digest
                image_info = parse_image_string(image)
                image_info['component'] = component_name
                images.append(image_info)
            elif isinstance(image, dict):
                # Image is already a dict with structured info
                image_info = {
                    'component': component_name,
                    'name': image.get('name', ''),
                    'tag': image.get('tag', ''),
                    'digest': image.get('digest', '')
                }
                images.append(image_info)
    
    return images


def parse_image_string(image_str: str) -> Dict[str, str]:
    """
    Parse an image string into components.
    
    Args:
        image_str: Image string (e.g., "registry.k8s.io/kube-apiserver:v1.28.6")
        
    Returns:
        Dictionary with name, tag, digest
    """
    image_info = {
        'name': '',
        'tag': '',
        'digest': ''
    }
    
    # Check for digest (@sha256:...)
    if '@' in image_str:
        name_part, digest = image_str.split('@', 1)
        image_info['name'] = name_part
        image_info['digest'] = digest
    # Check for tag (:tag)
    elif ':' in image_str:
        # Handle registry with port (e.g., localhost:5000/image:tag)
        parts = image_str.rsplit(':', 1)
        if '/' in parts[1]:
            # This is a registry with port, not a tag
            image_info['name'] = image_str
            image_info['tag'] = 'latest'
        else:
            image_info['name'] = parts[0]
            image_info['tag'] = parts[1]
    else:
        image_info['name'] = image_str
        image_info['tag'] = 'latest'
    
    return image_info


def get_image_digests_from_podman() -> Dict[str, str]:
    """
    Get image digests from local podman/docker.
    
    Returns:
        Dictionary mapping image names to digests
    """
    digests = {}
    
    # Try podman first
    try:
        result = run_command(['podman', 'images', '--format', 'json'], check=False)
        if result.returncode == 0:
            images = json.loads(result.stdout)
            for img in images:
                names = img.get('Names', []) or img.get('RepoTags', [])
                digest = img.get('Digest', '') or img.get('Id', '')
                for name in names:
                    if name and name != '<none>:<none>':
                        digests[name] = digest
            return digests
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    # Try docker as fallback
    try:
        result = run_command(['docker', 'images', '--format', '{{json .}}'], check=False)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    img = json.loads(line)
                    repo = img.get('Repository', '')
                    tag = img.get('Tag', '')
                    digest = img.get('Digest', '') or img.get('ID', '')
                    if repo and tag and repo != '<none>':
                        name = f"{repo}:{tag}"
                        digests[name] = digest
            return digests
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    return digests


def create_snapshot(package_path: Path, output_path: Path) -> None:
    """
    Create an image list snapshot from a Zarf package.
    
    Args:
        package_path: Path to Zarf package
        output_path: Path to output JSON file
    """
    # Check Zarf is installed
    if not check_zarf_installed():
        raise RuntimeError("Zarf CLI not found. Please install Zarf.")
    
    # Inspect package
    metadata = inspect_zarf_package(package_path)
    
    # Extract images
    images = extract_images_from_metadata(metadata)
    
    # Get local digests if available
    local_digests = get_image_digests_from_podman()
    
    # Enrich images with local digests if available
    for image in images:
        image_name = image['name']
        image_tag = image['tag']
        full_name = f"{image_name}:{image_tag}" if image_tag else image_name
        
        if full_name in local_digests and not image['digest']:
            image['digest'] = local_digests[full_name]
    
    # Sort images for deterministic output
    images.sort(key=lambda x: (x['component'], x['name'], x['tag']))
    
    # Create snapshot
    snapshot = {
        'package': {
            'name': metadata.get('name', ''),
            'version': metadata.get('version', ''),
            'architecture': metadata.get('architecture', ''),
        },
        'snapshot_date': None,  # Will be set by JSON encoder
        'image_count': len(images),
        'images': images
    }
    
    # Write snapshot
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
    
    print(f"Snapshot created: {output_path}")
    print(f"Total images: {len(images)}")
    print(f"Components: {len(set(img['component'] for img in images))}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Create image list snapshot from Zarf package',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create snapshot from package
  python3 snapshot_image_list.py dist/zarf-package-*.tar.zst snapshot.json
  
  # Create snapshot with specific output path
  python3 snapshot_image_list.py package.tar.zst build/snapshot-v1.json
        """
    )
    
    parser.add_argument(
        'package',
        type=Path,
        help='Path to Zarf package file'
    )
    
    parser.add_argument(
        'output',
        type=Path,
        help='Path to output JSON snapshot file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    try:
        create_snapshot(args.package, args.output)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
