"""Unit tests for merge_images worker."""

import pytest
from pathlib import Path
import sys

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

from workers.merge_images import (
    merge_opencenter_images_worker,
    analyze_image_list,
    count_images,
    extract_categories
)


class TestMergeImages:
    """Tests for merge_opencenter_images_worker."""
    
    def test_merge_fails_without_opencenter_images(self, tmp_path):
        """Test merge fails if openCenter images file doesn't exist."""
        # Create kubespray-offline directory but no opencenter-images.txt
        kubespray_dir = tmp_path / "build" / "kubespray-offline"
        kubespray_dir.mkdir(parents=True)
        
        result = merge_opencenter_images_worker(tmp_path)
        assert result is False
    
    def test_merge_fails_without_kubespray_offline(self, tmp_path):
        """Test merge fails if kubespray-offline directory doesn't exist."""
        # Create opencenter-images.txt but no kubespray-offline directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        opencenter_images = config_dir / "opencenter-images.txt"
        opencenter_images.write_text("ghcr.io/test/image:v1.0.0\n")
        
        result = merge_opencenter_images_worker(tmp_path)
        assert result is False
    
    def test_merge_creates_imagelists_directory(self, tmp_path):
        """Test merge creates imagelists directory if it doesn't exist."""
        # Setup
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        opencenter_images = config_dir / "opencenter-images.txt"
        opencenter_images.write_text("ghcr.io/test/image:v1.0.0\n")
        
        kubespray_dir = tmp_path / "build" / "kubespray-offline"
        kubespray_dir.mkdir(parents=True)
        
        # Execute
        result = merge_opencenter_images_worker(tmp_path)
        
        # Verify
        assert result is True
        imagelists_dir = kubespray_dir / "imagelists"
        assert imagelists_dir.exists()
        assert imagelists_dir.is_dir()
    
    def test_merge_copies_images_to_additional_images(self, tmp_path):
        """Test merge copies openCenter images to additional_images.txt."""
        # Setup
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        opencenter_images = config_dir / "opencenter-images.txt"
        test_content = """# FLUX (GitOps)
ghcr.io/fluxcd/flux-controller:v2.2.0
ghcr.io/fluxcd/kustomize-controller:v1.2.0

# KEYCLOAK (Identity)
quay.io/keycloak/keycloak:21.1.1
"""
        opencenter_images.write_text(test_content)
        
        kubespray_dir = tmp_path / "build" / "kubespray-offline"
        kubespray_dir.mkdir(parents=True)
        
        # Execute
        result = merge_opencenter_images_worker(tmp_path)
        
        # Verify
        assert result is True
        additional_images = kubespray_dir / "imagelists" / "additional_images.txt"
        assert additional_images.exists()
        assert additional_images.read_text() == test_content
    
    def test_merge_backs_up_existing_file(self, tmp_path):
        """Test merge backs up existing additional_images.txt."""
        # Setup
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        opencenter_images = config_dir / "opencenter-images.txt"
        opencenter_images.write_text("ghcr.io/test/new:v1.0.0\n")
        
        kubespray_dir = tmp_path / "build" / "kubespray-offline"
        imagelists_dir = kubespray_dir / "imagelists"
        imagelists_dir.mkdir(parents=True)
        
        additional_images = imagelists_dir / "additional_images.txt"
        old_content = "ghcr.io/test/old:v0.9.0\n"
        additional_images.write_text(old_content)
        
        # Execute
        result = merge_opencenter_images_worker(tmp_path)
        
        # Verify
        assert result is True
        
        # Check backup was created
        backups = list(imagelists_dir.glob("additional_images.txt.backup-*"))
        assert len(backups) == 1
        assert backups[0].read_text() == old_content
        
        # Check new content
        assert additional_images.read_text() == "ghcr.io/test/new:v1.0.0\n"
    
    def test_merge_idempotent(self, tmp_path):
        """Test merge is idempotent (can run multiple times)."""
        # Setup
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        opencenter_images = config_dir / "opencenter-images.txt"
        test_content = "ghcr.io/test/image:v1.0.0\n"
        opencenter_images.write_text(test_content)
        
        kubespray_dir = tmp_path / "build" / "kubespray-offline"
        kubespray_dir.mkdir(parents=True)
        
        # Execute multiple times
        result1 = merge_opencenter_images_worker(tmp_path)
        result2 = merge_opencenter_images_worker(tmp_path)
        result3 = merge_opencenter_images_worker(tmp_path)
        
        # All should succeed
        assert result1 is True
        assert result2 is True
        assert result3 is True
        
        # Final content should match
        additional_images = kubespray_dir / "imagelists" / "additional_images.txt"
        assert additional_images.read_text() == test_content


class TestAnalyzeImageList:
    """Tests for analyze_image_list function."""
    
    def test_analyze_empty_file(self, tmp_path):
        """Test analyzing empty image list."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("")
        
        count, categories = analyze_image_list(image_file)
        
        assert count == 0
        assert categories == []
    
    def test_analyze_images_only(self, tmp_path):
        """Test analyzing file with only images (no categories)."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""ghcr.io/test/image1:v1.0.0
ghcr.io/test/image2:v2.0.0
ghcr.io/test/image3:v3.0.0
""")
        
        count, categories = analyze_image_list(image_file)
        
        assert count == 3
        assert categories == []
    
    def test_analyze_with_categories(self, tmp_path):
        """Test analyzing file with categories."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# FLUX (GitOps)
ghcr.io/fluxcd/flux-controller:v2.2.0
ghcr.io/fluxcd/kustomize-controller:v1.2.0

# KEYCLOAK (Identity)
quay.io/keycloak/keycloak:21.1.1

# PROMETHEUS (Monitoring)
quay.io/prometheus/prometheus:v2.48.0
""")
        
        count, categories = analyze_image_list(image_file)
        
        assert count == 4
        assert categories == ["FLUX", "KEYCLOAK", "PROMETHEUS"]
    
    def test_analyze_ignores_comments(self, tmp_path):
        """Test that regular comments are not counted as images."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# This is a comment
# Another comment
ghcr.io/test/image:v1.0.0
# Yet another comment
ghcr.io/test/image2:v2.0.0
""")
        
        count, categories = analyze_image_list(image_file)
        
        assert count == 2
        # Regular comments (lowercase) should not be categories
        assert categories == []
    
    def test_analyze_ignores_empty_lines(self, tmp_path):
        """Test that empty lines are ignored."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""
ghcr.io/test/image1:v1.0.0

ghcr.io/test/image2:v2.0.0

""")
        
        count, categories = analyze_image_list(image_file)
        
        assert count == 2


class TestCountImages:
    """Tests for count_images function."""
    
    def test_count_empty_file(self, tmp_path):
        """Test counting images in empty file."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("")
        
        count = count_images(image_file)
        assert count == 0
    
    def test_count_images_only(self, tmp_path):
        """Test counting images without comments."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""ghcr.io/test/image1:v1.0.0
ghcr.io/test/image2:v2.0.0
ghcr.io/test/image3:v3.0.0
""")
        
        count = count_images(image_file)
        assert count == 3
    
    def test_count_excludes_comments(self, tmp_path):
        """Test that comments are not counted."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# Comment
ghcr.io/test/image1:v1.0.0
# Another comment
ghcr.io/test/image2:v2.0.0
""")
        
        count = count_images(image_file)
        assert count == 2
    
    def test_count_excludes_empty_lines(self, tmp_path):
        """Test that empty lines are not counted."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""
ghcr.io/test/image1:v1.0.0

ghcr.io/test/image2:v2.0.0

""")
        
        count = count_images(image_file)
        assert count == 2


class TestExtractCategories:
    """Tests for extract_categories function."""
    
    def test_extract_no_categories(self, tmp_path):
        """Test extracting categories from file with none."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""ghcr.io/test/image1:v1.0.0
ghcr.io/test/image2:v2.0.0
""")
        
        categories = extract_categories(image_file)
        assert categories == []
    
    def test_extract_single_category(self, tmp_path):
        """Test extracting single category."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# FLUX (GitOps)
ghcr.io/fluxcd/flux-controller:v2.2.0
""")
        
        categories = extract_categories(image_file)
        assert categories == ["FLUX"]
    
    def test_extract_multiple_categories(self, tmp_path):
        """Test extracting multiple categories."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# FLUX (GitOps)
ghcr.io/fluxcd/flux-controller:v2.2.0

# KEYCLOAK (Identity)
quay.io/keycloak/keycloak:21.1.1

# PROMETHEUS (Monitoring)
quay.io/prometheus/prometheus:v2.48.0
""")
        
        categories = extract_categories(image_file)
        assert categories == ["FLUX", "KEYCLOAK", "PROMETHEUS"]
    
    def test_extract_ignores_lowercase_comments(self, tmp_path):
        """Test that lowercase comments are not extracted as categories."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# This is a regular comment
# FLUX (GitOps)
ghcr.io/fluxcd/flux-controller:v2.2.0
# another comment
""")
        
        categories = extract_categories(image_file)
        assert categories == ["FLUX"]
    
    def test_extract_removes_description(self, tmp_path):
        """Test that category descriptions in parentheses are removed."""
        image_file = tmp_path / "images.txt"
        image_file.write_text("""# FLUX (GitOps Controller)
# KEYCLOAK (Identity and Access Management)
# PROMETHEUS (Monitoring and Alerting)
""")
        
        categories = extract_categories(image_file)
        assert categories == ["FLUX", "KEYCLOAK", "PROMETHEUS"]
