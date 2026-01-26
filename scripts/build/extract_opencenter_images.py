#!/usr/bin/env python3
"""
Extract container image references from openCenter gitops-base manifests.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Set, Dict, List

def extract_images_from_yaml(file_path: Path) -> Set[str]:
    """Extract container image references from a YAML file."""
    images = set()
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Parse YAML
        try:
            docs = yaml.safe_load_all(content)
            for doc in docs:
                if doc:
                    images.update(find_images_in_dict(doc))
        except yaml.YAMLError:
            pass
            
        # Also search for image patterns in raw text (for Helm values)
        # Pattern: repository: <registry>/<org>/<image>
        repo_pattern = r'repository:\s+([a-zA-Z0-9\.\-_/]+)'
        tag_pattern = r'tag:\s+([a-zA-Z0-9\.\-_]+)'
        
        repos = re.findall(repo_pattern, content)
        tags = re.findall(tag_pattern, content)
        
        # Try to pair repos with tags
        for i, repo in enumerate(repos):
            if repo and repo != 'null' and repo != '""' and repo != "''":
                # Look for tag nearby
                tag = None
                if i < len(tags):
                    tag = tags[i]
                
                if tag and tag != 'null':
                    images.add(f"{repo}:{tag}")
                    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        
    return images

def find_images_in_dict(d: dict) -> Set[str]:
    """Recursively find image references in a dictionary."""
    images = set()
    
    if not isinstance(d, dict):
        return images
        
    for key, value in d.items():
        if key == 'image' and isinstance(value, str):
            images.add(value)
        elif key == 'repository' and isinstance(value, str):
            # Store for later pairing with tag
            pass
        elif isinstance(value, dict):
            images.update(find_images_in_dict(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    images.update(find_images_in_dict(item))
                    
    return images

def main():
    """Extract all images from gitops-base manifests."""
    base_dir = Path("assets/gitops-base/applications")
    
    if not base_dir.exists():
        print(f"Error: {base_dir} not found")
        return
        
    all_images = set()
    service_images = {}
    
    # Walk through all YAML files
    for yaml_file in base_dir.rglob("*.yaml"):
        images = extract_images_from_yaml(yaml_file)
        if images:
            # Determine service name from path
            parts = yaml_file.parts
            if 'services' in parts:
                idx = parts.index('services')
                if idx + 1 < len(parts):
                    service = parts[idx + 1]
                    if service not in service_images:
                        service_images[service] = set()
                    service_images[service].update(images)
            elif 'managed-services' in parts:
                idx = parts.index('managed-services')
                if idx + 1 < len(parts):
                    service = parts[idx + 1]
                    if service not in service_images:
                        service_images[service] = set()
                    service_images[service].update(images)
                    
            all_images.update(images)
    
    # Print results
    print("# openCenter Platform Service Images")
    print(f"# Total services: {len(service_images)}")
    print(f"# Total unique images: {len(all_images)}")
    print()
    
    for service in sorted(service_images.keys()):
        print(f"# {service}")
        for image in sorted(service_images[service]):
            print(image)
        print()
    
    # Write to file
    output_file = Path("config/opencenter-images.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("# openCenter Platform Service Images\n")
        f.write(f"# Extracted from gitops-base manifests\n")
        f.write(f"# Total services: {len(service_images)}\n")
        f.write(f"# Total unique images: {len(all_images)}\n")
        f.write("\n")
        
        for service in sorted(service_images.keys()):
            f.write(f"# {service}\n")
            for image in sorted(service_images[service]):
                f.write(f"{image}\n")
            f.write("\n")
    
    print(f"\nWrote {len(all_images)} images to {output_file}")

if __name__ == "__main__":
    main()
