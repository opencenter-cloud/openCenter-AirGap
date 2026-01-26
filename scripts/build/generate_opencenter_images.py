#!/usr/bin/env python3
"""
Generate openCenter Platform Service Image List

Scans the gitops-base assets directory to extract all container image
references from Helm values, Kustomize manifests, and application definitions.

Usage:
    python3 generate_opencenter_images.py [OPTIONS]
    python3 generate_opencenter_images.py --output config/opencenter-images.txt
"""

import argparse
import re
import sys
import yaml
from pathlib import Path
from typing import Set, List, Dict


class ImageExtractor:
    """Extract container images from various manifest formats."""
    
    # Common image reference patterns
    IMAGE_PATTERNS = [
        # Standard image reference: registry/repo:tag
        r'image:\s*["\']?([a-zA-Z0-9\.\-/:@]+)["\']?',
        # Repository and tag split
        r'repository:\s*["\']?([a-zA-Z0-9\.\-/:]+)["\']?',
        # Tag field
        r'tag:\s*["\']?([a-zA-Z0-9\.\-_]+)["\']?',
        # Container image in pod specs
        r'- image:\s*["\']?([a-zA-Z0-9\.\-/:@]+)["\']?',
        # Newimage in Kustomize
        r'newImage:\s*["\']?([a-zA-Z0-9\.\-/:@]+)["\']?',
        # Image in HelmRelease
        r'image:\s*["\']?([a-zA-Z0-9\.\-/:@]+)["\']?',
    ]
    
    def __init__(self, gitops_base_path: Path):
        """
        Initialize extractor.
        
        Args:
            gitops_base_path: Path to gitops-base directory
        """
        self.gitops_base = gitops_base_path
        self.images: Set[str] = set()
        self.image_sources: Dict[str, List[str]] = {}
    
    def extract_from_yaml(self, file_path: Path) -> Set[str]:
        """
        Extract images from YAML file.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Set of image references
        """
        images = set()
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
                # Try to parse as YAML
                try:
                    docs = yaml.safe_load_all(content)
                    for doc in docs:
                        if doc:
                            images.update(self._extract_from_dict(doc))
                except yaml.YAMLError:
                    # If YAML parsing fails, use regex
                    pass
                
                # Also use regex patterns as fallback
                for pattern in self.IMAGE_PATTERNS:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        img = match.group(1)
                        if self._is_valid_image(img):
                            images.add(img)
        
        except Exception as e:
            print(f"Warning: Error reading {file_path}: {e}", file=sys.stderr)
        
        return images
    
    def _extract_from_dict(self, data: Dict) -> Set[str]:
        """
        Recursively extract images from dictionary.
        
        Args:
            data: Dictionary to search
            
        Returns:
            Set of image references
        """
        images = set()
        
        if isinstance(data, dict):
            # Check for image field
            if 'image' in data:
                img = data['image']
                if isinstance(img, str) and self._is_valid_image(img):
                    images.add(img)
            
            # Check for repository + tag pattern
            if 'repository' in data and 'tag' in data:
                repo = data['repository']
                tag = data['tag']
                if isinstance(repo, str) and isinstance(tag, str):
                    img = f"{repo}:{tag}"
                    if self._is_valid_image(img):
                        images.add(img)
            
            # Recurse into nested dicts
            for value in data.values():
                if isinstance(value, dict):
                    images.update(self._extract_from_dict(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            images.update(self._extract_from_dict(item))
        
        return images
    
    def _is_valid_image(self, img: str) -> bool:
        """
        Check if string is a valid image reference.
        
        Args:
            img: Image string to validate
            
        Returns:
            True if valid image reference
        """
        # Skip common false positives
        if not img or len(img) < 3:
            return False
        
        # Skip single words (likely field names)
        if img in ['name', 'repository', 'tag', 'image', 'registry']:
            return False
        
        # Skip variable references
        if '{{' in img or '${' in img or '$(' in img:
            return False
        
        # Skip paths
        if img.startswith('/') or img.startswith('./'):
            return False
        
        # Must contain at least one slash or colon (but not just colon)
        if img == ':' or img.endswith(':'):
            return False
        
        # Skip common non-image values
        skip_patterns = [
            'http://', 'https://', 'file://',
            '.yaml', '.yml', '.json', '.txt',
            'localhost', '127.0.0.1',
        ]
        
        for pattern in skip_patterns:
            if pattern in img.lower():
                return False
        
        # Must look like an image reference
        # Either has a slash (registry/repo) or colon with tag (repo:tag)
        has_slash = '/' in img
        has_colon = ':' in img
        has_at = '@' in img
        
        if not (has_slash or has_colon or has_at):
            return False
        
        return True
    
    def scan_directory(self, directory: Path, pattern: str = "**/*.yaml") -> None:
        """
        Scan directory for YAML files and extract images.
        
        Args:
            directory: Directory to scan
            pattern: Glob pattern for files
        """
        if not directory.exists():
            print(f"Warning: Directory not found: {directory}", file=sys.stderr)
            return
        
        files = list(directory.glob(pattern))
        print(f"Scanning {len(files)} files in {directory.relative_to(self.gitops_base)}...")
        
        for file_path in files:
            images = self.extract_from_yaml(file_path)
            for img in images:
                self.images.add(img)
                if img not in self.image_sources:
                    self.image_sources[img] = []
                self.image_sources[img].append(str(file_path.relative_to(self.gitops_base)))
    
    def scan_all(self) -> None:
        """Scan all relevant directories in gitops-base."""
        # Scan applications directory
        apps_dir = self.gitops_base / "applications"
        if apps_dir.exists():
            self.scan_directory(apps_dir, "**/*.yaml")
            self.scan_directory(apps_dir, "**/*.yml")
        
        # Scan IAC directory for Helm values
        iac_dir = self.gitops_base / "iac"
        if iac_dir.exists():
            self.scan_directory(iac_dir, "**/*values*.yaml")
            self.scan_directory(iac_dir, "**/*values*.yml")
    
    def get_images_by_category(self) -> Dict[str, List[str]]:
        """
        Categorize images by service type.
        
        Returns:
            Dictionary mapping categories to image lists
        """
        categories = {
            'FluxCD': [],
            'Gitea': [],
            'Cert-Manager': [],
            'Ingress & Gateway': [],
            'Identity': [],
            'Observability': [],
            'Storage': [],
            'Policy & Security': [],
            'Backup': [],
            'Harbor': [],
            'Headlamp': [],
            'Weave GitOps': [],
            'MetalLB': [],
            'Postgres Operator': [],
            'Kafka': [],
            'Additional': [],
        }
        
        for img in sorted(self.images):
            img_lower = img.lower()
            
            # Categorize by image name patterns
            if 'fluxcd' in img_lower or 'flux-' in img_lower or '/flux' in img_lower:
                categories['FluxCD'].append(img)
            elif 'gitea' in img_lower:
                categories['Gitea'].append(img)
            elif 'cert-manager' in img_lower:
                categories['Cert-Manager'].append(img)
            elif any(x in img_lower for x in ['ingress-nginx', 'nginx-ingress', 
                                                'gateway', 'envoy']):
                categories['Ingress & Gateway'].append(img)
            elif 'keycloak' in img_lower:
                categories['Identity'].append(img)
            elif any(x in img_lower for x in ['prometheus', 'grafana', 'alertmanager', 
                                                'loki', 'tempo', 'mimir', 'otel', 
                                                'opentelemetry', 'kube-state-metrics',
                                                'agent', 'exporter']):
                categories['Observability'].append(img)
            elif any(x in img_lower for x in ['longhorn', 'csi', 'snapshotter', 
                                                'vsphere', 'openstack', 'cinder',
                                                'attacher', 'provisioner', 'resizer',
                                                'livenessprobe', 'node-driver-registrar']):
                categories['Storage'].append(img)
            elif any(x in img_lower for x in ['kyverno', 'olm', 'rbac-manager', 
                                                'sealed-secrets', 'rbac-proxy']):
                categories['Policy & Security'].append(img)
            elif 'velero' in img_lower:
                categories['Backup'].append(img)
            elif 'harbor' in img_lower:
                categories['Harbor'].append(img)
            elif 'headlamp' in img_lower:
                categories['Headlamp'].append(img)
            elif 'wego' in img_lower or 'weave' in img_lower:
                categories['Weave GitOps'].append(img)
            elif 'metallb' in img_lower or 'frr' in img_lower:
                categories['MetalLB'].append(img)
            elif 'postgres' in img_lower or 'pgbouncer' in img_lower or 'spilo' in img_lower:
                categories['Postgres Operator'].append(img)
            elif 'kafka' in img_lower or 'strimzi' in img_lower:
                categories['Kafka'].append(img)
            else:
                categories['Additional'].append(img)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def write_image_list(self, output_path: Path, include_sources: bool = False) -> None:
        """
        Write image list to file.
        
        Args:
            output_path: Path to output file
            include_sources: Whether to include source file comments
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        categories = self.get_images_by_category()
        
        with open(output_path, 'w') as f:
            f.write("# openCenter Platform Service Images\n")
            f.write("# Generated from gitops-base assets\n")
            f.write(f"# Total images: {len(self.images)}\n")
            f.write("\n")
            
            for category, images in categories.items():
                f.write(f"# {category} ({len(images)} images)\n")
                for img in images:
                    f.write(f"{img}\n")
                    if include_sources and img in self.image_sources:
                        sources = self.image_sources[img]
                        for source in sources[:3]:  # Limit to first 3 sources
                            f.write(f"#   Source: {source}\n")
                f.write("\n")
        
        print(f"Image list written to: {output_path}")
        print(f"Total images: {len(self.images)}")
        print(f"Categories: {len(categories)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate openCenter platform service image list',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate image list from gitops-base
  python3 generate_opencenter_images.py
  
  # Specify custom paths
  python3 generate_opencenter_images.py \\
      --gitops-base assets/gitops-base \\
      --output config/opencenter-images.txt
  
  # Include source file comments
  python3 generate_opencenter_images.py --include-sources
        """
    )
    
    parser.add_argument(
        '--gitops-base',
        type=Path,
        default=Path('assets/gitops-base'),
        help='Path to gitops-base directory (default: assets/gitops-base)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('config/opencenter-images.txt'),
        help='Output file path (default: config/opencenter-images.txt)'
    )
    
    parser.add_argument(
        '--include-sources',
        action='store_true',
        help='Include source file comments in output'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate gitops-base path
    if not args.gitops_base.exists():
        print(f"Error: gitops-base directory not found: {args.gitops_base}", file=sys.stderr)
        print("Please ensure gitops-base is cloned to assets/gitops-base", file=sys.stderr)
        return 1
    
    try:
        # Extract images
        extractor = ImageExtractor(args.gitops_base)
        extractor.scan_all()
        
        if len(extractor.images) == 0:
            print("Warning: No images found", file=sys.stderr)
            return 1
        
        # Write output
        extractor.write_image_list(args.output, args.include_sources)
        
        # Print summary
        if args.verbose:
            print("\nImage categories:")
            categories = extractor.get_images_by_category()
            for category, images in categories.items():
                print(f"  {category}: {len(images)} images")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
