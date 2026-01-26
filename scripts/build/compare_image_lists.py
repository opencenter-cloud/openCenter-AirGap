#!/usr/bin/env python3
"""
Image List Comparison Utility

Compares two image list snapshots (JSON files) and reports differences
in images, tags, or digests. Used for build determinism validation.

Usage:
    python3 compare_image_lists.py <snapshot1.json> <snapshot2.json>
    python3 compare_image_lists.py build/snapshot-1.json build/snapshot-2.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ImageSnapshot:
    """Represents an image list snapshot."""
    
    def __init__(self, data: Dict):
        """
        Initialize snapshot from JSON data.
        
        Args:
            data: Parsed JSON snapshot data
        """
        self.package_name = data.get('package', {}).get('name', '')
        self.package_version = data.get('package', {}).get('version', '')
        self.architecture = data.get('package', {}).get('architecture', '')
        self.image_count = data.get('image_count', 0)
        self.images = data.get('images', [])
        
        # Create lookup structures
        self._image_map = self._build_image_map()
    
    def _build_image_map(self) -> Dict[str, Dict]:
        """
        Build a map of images for quick lookup.
        
        Returns:
            Dictionary mapping image keys to image data
        """
        image_map = {}
        for img in self.images:
            key = self._image_key(img)
            image_map[key] = img
        return image_map
    
    @staticmethod
    def _image_key(image: Dict) -> str:
        """
        Generate a unique key for an image.
        
        Args:
            image: Image dictionary
            
        Returns:
            Unique key string
        """
        name = image.get('name', '')
        tag = image.get('tag', '')
        return f"{name}:{tag}"
    
    def get_image_keys(self) -> Set[str]:
        """
        Get set of all image keys.
        
        Returns:
            Set of image keys
        """
        return set(self._image_map.keys())
    
    def get_image(self, key: str) -> Dict:
        """
        Get image data by key.
        
        Args:
            key: Image key
            
        Returns:
            Image dictionary or empty dict if not found
        """
        return self._image_map.get(key, {})


class ComparisonResult:
    """Represents the result of comparing two snapshots."""
    
    def __init__(self):
        """Initialize empty comparison result."""
        self.identical = True
        self.added_images: List[str] = []
        self.removed_images: List[str] = []
        self.changed_digests: List[Tuple[str, str, str]] = []
        self.changed_tags: List[Tuple[str, str, str]] = []
        self.metadata_differences: List[str] = []
    
    def has_differences(self) -> bool:
        """
        Check if there are any differences.
        
        Returns:
            True if differences exist, False otherwise
        """
        return (
            len(self.added_images) > 0 or
            len(self.removed_images) > 0 or
            len(self.changed_digests) > 0 or
            len(self.changed_tags) > 0 or
            len(self.metadata_differences) > 0
        )
    
    def print_report(self, verbose: bool = False) -> None:
        """
        Print comparison report.
        
        Args:
            verbose: Whether to print verbose output
        """
        if not self.has_differences():
            print("✓ Snapshots are identical")
            print("  No differences in images, tags, or digests")
            return
        
        print("✗ Snapshots differ")
        print()
        
        # Metadata differences
        if self.metadata_differences:
            print("Metadata Differences:")
            for diff in self.metadata_differences:
                print(f"  - {diff}")
            print()
        
        # Added images
        if self.added_images:
            print(f"Added Images ({len(self.added_images)}):")
            for img in sorted(self.added_images):
                print(f"  + {img}")
            print()
        
        # Removed images
        if self.removed_images:
            print(f"Removed Images ({len(self.removed_images)}):")
            for img in sorted(self.removed_images):
                print(f"  - {img}")
            print()
        
        # Changed digests
        if self.changed_digests:
            print(f"Changed Digests ({len(self.changed_digests)}):")
            for img, old_digest, new_digest in self.changed_digests:
                print(f"  ~ {img}")
                if verbose:
                    print(f"    Old: {old_digest}")
                    print(f"    New: {new_digest}")
            print()
        
        # Changed tags
        if self.changed_tags:
            print(f"Changed Tags ({len(self.changed_tags)}):")
            for img, old_tag, new_tag in self.changed_tags:
                print(f"  ~ {img}")
                print(f"    Old: {old_tag}")
                print(f"    New: {new_tag}")
            print()
        
        # Summary
        total_changes = (
            len(self.added_images) +
            len(self.removed_images) +
            len(self.changed_digests) +
            len(self.changed_tags)
        )
        print(f"Total differences: {total_changes}")


def load_snapshot(path: Path) -> ImageSnapshot:
    """
    Load a snapshot from JSON file.
    
    Args:
        path: Path to snapshot JSON file
        
    Returns:
        ImageSnapshot object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not path.exists():
        raise FileNotFoundError(f"Snapshot not found: {path}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    return ImageSnapshot(data)


def compare_snapshots(snapshot1: ImageSnapshot, snapshot2: ImageSnapshot) -> ComparisonResult:
    """
    Compare two image snapshots.
    
    Args:
        snapshot1: First snapshot
        snapshot2: Second snapshot
        
    Returns:
        ComparisonResult with differences
    """
    result = ComparisonResult()
    
    # Compare metadata
    if snapshot1.package_name != snapshot2.package_name:
        result.metadata_differences.append(
            f"Package name: {snapshot1.package_name} vs {snapshot2.package_name}"
        )
    
    if snapshot1.package_version != snapshot2.package_version:
        result.metadata_differences.append(
            f"Package version: {snapshot1.package_version} vs {snapshot2.package_version}"
        )
    
    if snapshot1.architecture != snapshot2.architecture:
        result.metadata_differences.append(
            f"Architecture: {snapshot1.architecture} vs {snapshot2.architecture}"
        )
    
    # Get image keys
    keys1 = snapshot1.get_image_keys()
    keys2 = snapshot2.get_image_keys()
    
    # Find added and removed images
    result.added_images = list(keys2 - keys1)
    result.removed_images = list(keys1 - keys2)
    
    # Find changed images (same key, different digest or tag)
    common_keys = keys1 & keys2
    
    for key in common_keys:
        img1 = snapshot1.get_image(key)
        img2 = snapshot2.get_image(key)
        
        # Compare digests
        digest1 = img1.get('digest', '')
        digest2 = img2.get('digest', '')
        
        if digest1 and digest2 and digest1 != digest2:
            result.changed_digests.append((key, digest1, digest2))
        
        # Compare tags (should be same since key includes tag, but check anyway)
        tag1 = img1.get('tag', '')
        tag2 = img2.get('tag', '')
        
        if tag1 != tag2:
            result.changed_tags.append((key, tag1, tag2))
    
    # Update identical flag
    result.identical = not result.has_differences()
    
    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Compare two image list snapshots',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare two snapshots
  python3 compare_image_lists.py snapshot1.json snapshot2.json
  
  # Compare with verbose output
  python3 compare_image_lists.py -v snapshot1.json snapshot2.json
  
Exit Codes:
  0 - Snapshots are identical
  1 - Snapshots differ
  2 - Error occurred
        """
    )
    
    parser.add_argument(
        'snapshot1',
        type=Path,
        help='Path to first snapshot JSON file'
    )
    
    parser.add_argument(
        'snapshot2',
        type=Path,
        help='Path to second snapshot JSON file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    try:
        # Load snapshots
        print(f"Loading snapshot 1: {args.snapshot1}")
        snapshot1 = load_snapshot(args.snapshot1)
        print(f"  Images: {snapshot1.image_count}")
        
        print(f"Loading snapshot 2: {args.snapshot2}")
        snapshot2 = load_snapshot(args.snapshot2)
        print(f"  Images: {snapshot2.image_count}")
        
        print()
        
        # Compare
        result = compare_snapshots(snapshot1, snapshot2)
        
        # Output results
        if args.json:
            output = {
                'identical': result.identical,
                'added_images': result.added_images,
                'removed_images': result.removed_images,
                'changed_digests': [
                    {'image': img, 'old': old, 'new': new}
                    for img, old, new in result.changed_digests
                ],
                'changed_tags': [
                    {'image': img, 'old': old, 'new': new}
                    for img, old, new in result.changed_tags
                ],
                'metadata_differences': result.metadata_differences
            }
            print(json.dumps(output, indent=2))
        else:
            result.print_report(verbose=args.verbose)
        
        # Exit with appropriate code
        if result.identical:
            return 0
        else:
            return 1
    
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
