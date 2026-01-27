"""Image list merging worker.

Merges openCenter platform service images with kubespray-offline's
additional_images.txt for offline asset collection.
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple


def merge_opencenter_images_worker(project_root: Path) -> bool:
    """Merge openCenter images with kubespray-offline image list.
    
    Copies the curated openCenter image list to kubespray-offline's
    additional_images.txt before download. This ensures all platform
    service images are included in the offline asset collection.
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        True if merge succeeds, False otherwise
    """
    print("\n=== Merging openCenter Platform Service Images ===\n")
    
    # Define paths
    opencenter_images = project_root / "config" / "opencenter-images.txt"
    kubespray_offline_dir = project_root / "build" / "kubespray-offline"
    imagelists_dir = kubespray_offline_dir / "imagelists"
    additional_images = imagelists_dir / "additional_images.txt"
    
    # Validate inputs
    if not opencenter_images.exists():
        print(f"ERROR: openCenter images list not found: {opencenter_images}")
        print("Run: python3 scripts/build/extract_opencenter_images.py")
        return False
    
    if not kubespray_offline_dir.exists():
        print(f"ERROR: kubespray-offline directory not found: {kubespray_offline_dir}")
        print("Clone kubespray-offline first")
        return False
    
    # Create imagelists directory if needed
    imagelists_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Image lists directory: {imagelists_dir}")
    
    # Backup existing file
    if additional_images.exists():
        backup_name = f"additional_images.txt.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        backup_path = imagelists_dir / backup_name
        shutil.copy2(additional_images, backup_path)
        print(f"✓ Backed up existing file to: {backup_name}")
    
    # Copy openCenter images
    shutil.copy2(opencenter_images, additional_images)
    print(f"✓ Copied openCenter images to: {additional_images.name}")
    
    # Count and categorize images
    image_count, categories = analyze_image_list(additional_images)
    
    print(f"\n✓ Merged {image_count} openCenter platform service images")
    print("  kubespray-offline will download these images during asset collection")
    
    # Show categories
    if categories:
        print("\nImage categories:")
        for category in categories:
            print(f"  - {category}")
    
    print("\n✓ Next step: Run kubespray-offline download-all.sh\n")
    return True


def analyze_image_list(image_file: Path) -> Tuple[int, List[str]]:
    """Analyze image list file to count images and extract categories.
    
    Args:
        image_file: Path to image list file
        
    Returns:
        Tuple of (image_count, categories)
    """
    image_count = 0
    categories = []
    
    with open(image_file, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Extract category headers (format: "# CATEGORY (description)")
            # Category must be all uppercase (not just start with uppercase)
            if line.startswith('# ') and len(line) > 2:
                # Extract the text after "# "
                text = line[2:].split('(')[0].strip()
                # Check if it's all uppercase (category) vs mixed case (comment)
                if text and text.isupper():
                    categories.append(text)
                    continue
            
            # Count non-comment lines as images
            if not line.startswith('#'):
                image_count += 1
    
    return image_count, categories


def count_images(image_file: Path) -> int:
    """Count non-comment, non-empty lines in image list.
    
    Args:
        image_file: Path to image list file
        
    Returns:
        Number of images
    """
    count = 0
    with open(image_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                count += 1
    return count


def extract_categories(image_file: Path) -> List[str]:
    """Extract category headers from image list.
    
    Category headers are lines starting with "# " followed by all-uppercase text.
    Format: "# CATEGORY (description)"
    
    Args:
        image_file: Path to image list file
        
    Returns:
        List of category names
    """
    categories = []
    with open(image_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('# ') and len(line) > 2:
                # Extract the text after "# "
                text = line[2:].split('(')[0].strip()
                # Check if it's all uppercase (category) vs mixed case (comment)
                if text and text.isupper():
                    categories.append(text)
    return categories
