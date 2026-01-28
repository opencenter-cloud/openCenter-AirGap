"""Unit tests for ImageManager class."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess
from pathlib import Path

from opencenter_build.image_utils import ImageManager
from opencenter_build.exceptions import BuildError


class TestImageManager:
    """Test ImageManager class."""

    @patch("subprocess.run")
    def test_initialization_success(self, mock_run):
        """Test successful ImageManager initialization."""
        mock_run.return_value = Mock(returncode=0, stdout="skopeo version 1.13.0\n", stderr="")

        mgr = ImageManager()

        assert mgr.skopeo_path == "skopeo"
        assert mgr.podman_path == "podman"
        assert mock_run.call_count == 2  # Called for both skopeo and podman

    @patch("subprocess.run")
    def test_initialization_skopeo_not_found(self, mock_run):
        """Test initialization fails when skopeo not found."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(BuildError) as exc_info:
            ImageManager()

        assert "skopeo not found" in str(exc_info.value)
        assert "apt-get install" in str(exc_info.value)

    @patch("subprocess.run")
    def test_initialization_podman_not_found(self, mock_run):
        """Test initialization fails when podman not found."""

        def side_effect(*args, **kwargs):
            if "skopeo" in args[0]:
                return Mock(returncode=0, stdout="skopeo version 1.13.0\n", stderr="")
            raise FileNotFoundError()

        mock_run.side_effect = side_effect

        with pytest.raises(BuildError) as exc_info:
            ImageManager()

        assert "podman not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_initialization_custom_paths(self, mock_run):
        """Test initialization with custom tool paths."""
        mock_run.return_value = Mock(returncode=0, stdout="version info\n", stderr="")

        mgr = ImageManager(skopeo_path="/usr/local/bin/skopeo", podman_path="/usr/local/bin/podman")

        assert mgr.skopeo_path == "/usr/local/bin/skopeo"
        assert mgr.podman_path == "/usr/local/bin/podman"

    @patch("subprocess.run")
    def test_copy_image_to_dir_success(self, mock_run):
        """Test successful image copy to directory."""
        # Mock tool verification
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        # Mock copy operation
        mock_run.return_value = Mock(returncode=0, stdout="Copying...\n", stderr="")

        dest_dir = Path("/tmp/test/images")
        mgr.copy_image_to_dir("nginx:1.29.2", dest_dir)

        # Verify skopeo copy was called
        call_args = mock_run.call_args[0][0]
        assert "skopeo" in call_args
        assert "copy" in call_args
        assert "docker://nginx:1.29.2" in call_args
        assert f"dir:{dest_dir}" in call_args

    @patch("subprocess.run")
    def test_copy_image_to_dir_with_transport(self, mock_run):
        """Test image copy with explicit transport."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout="Copying...\n", stderr="")

        dest_dir = Path("/tmp/test/images")
        mgr.copy_image_to_dir("docker://nginx:1.29.2", dest_dir)

        call_args = mock_run.call_args[0][0]
        assert "docker://nginx:1.29.2" in call_args

    @patch("subprocess.run")
    def test_copy_image_to_dir_insecure(self, mock_run):
        """Test image copy with insecure flag."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout="Copying...\n", stderr="")

        dest_dir = Path("/tmp/test/images")
        mgr.copy_image_to_dir("nginx:1.29.2", dest_dir, insecure=True)

        call_args = mock_run.call_args[0][0]
        assert "--insecure-policy" in call_args

    @patch("subprocess.run")
    def test_copy_image_to_dir_failure(self, mock_run):
        """Test image copy failure."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: image not found")

        with pytest.raises(BuildError) as exc_info:
            mgr.copy_image_to_dir("nonexistent:latest", Path("/tmp/test"))

        assert "Failed to copy image" in str(exc_info.value)
        assert "image not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_copy_image_to_dir_timeout(self, mock_run):
        """Test image copy timeout."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.side_effect = subprocess.TimeoutExpired("skopeo", 300)

        with pytest.raises(BuildError) as exc_info:
            mgr.copy_image_to_dir("nginx:1.29.2", Path("/tmp/test"))

        assert "Timeout" in str(exc_info.value)

    @patch("subprocess.run")
    def test_sync_images_success(self, mock_run, tmp_path):
        """Test successful image sync."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        # Create test image list
        image_list = tmp_path / "images.txt"
        image_list.write_text("nginx:1.29.2\nregistry:2.8.3\n")

        mock_run.return_value = Mock(returncode=0, stdout="Syncing...\n", stderr="")

        dest_dir = tmp_path / "images"
        mgr.sync_images(image_list, dest_dir)

        call_args = mock_run.call_args[0][0]
        assert "skopeo" in call_args
        assert "sync" in call_args
        assert "--src" in call_args
        assert "docker" in call_args
        assert "--dest" in call_args
        assert "dir" in call_args

    @patch("subprocess.run")
    def test_sync_images_file_not_found(self, mock_run):
        """Test sync with non-existent image list."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        with pytest.raises(BuildError) as exc_info:
            mgr.sync_images(Path("/nonexistent/images.txt"), Path("/tmp/dest"))

        assert "Image list not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_save_image_to_tar_success(self, mock_run, tmp_path):
        """Test successful image save to tar."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout="Saving...\n", stderr="")

        output_file = tmp_path / "nginx.tar"
        mgr.save_image_to_tar("nginx:1.29.2", output_file)

        call_args = mock_run.call_args[0][0]
        assert "podman" in call_args
        assert "save" in call_args
        assert "--format" in call_args
        assert "oci-archive" in call_args
        assert "-o" in call_args
        assert "nginx:1.29.2" in call_args

    @patch("subprocess.run")
    def test_save_image_to_tar_custom_format(self, mock_run, tmp_path):
        """Test image save with custom format."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout="Saving...\n", stderr="")

        output_file = tmp_path / "nginx.tar"
        mgr.save_image_to_tar("nginx:1.29.2", output_file, format="docker-archive")

        call_args = mock_run.call_args[0][0]
        assert "docker-archive" in call_args

    @patch("subprocess.run")
    def test_save_image_to_tar_failure(self, mock_run, tmp_path):
        """Test image save failure."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: image not found")

        with pytest.raises(BuildError) as exc_info:
            mgr.save_image_to_tar("nonexistent:latest", tmp_path / "test.tar")

        assert "Failed to save image" in str(exc_info.value)

    @patch("subprocess.run")
    def test_load_image_from_tar_success(self, mock_run, tmp_path):
        """Test successful image load from tar."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        # Create dummy tar file
        tar_file = tmp_path / "nginx.tar"
        tar_file.write_text("dummy")

        mock_run.return_value = Mock(
            returncode=0, stdout="Loaded image: docker.io/library/nginx:1.29.2\n", stderr=""
        )

        image_ref = mgr.load_image_from_tar(tar_file)

        assert image_ref == "docker.io/library/nginx:1.29.2"
        call_args = mock_run.call_args[0][0]
        assert "podman" in call_args
        assert "load" in call_args
        assert "-i" in call_args

    @patch("subprocess.run")
    def test_load_image_from_tar_quiet(self, mock_run, tmp_path):
        """Test image load with quiet flag."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        tar_file = tmp_path / "nginx.tar"
        tar_file.write_text("dummy")

        mock_run.return_value = Mock(returncode=0, stdout="Loaded image: nginx:1.29.2\n", stderr="")

        mgr.load_image_from_tar(tar_file, quiet=True)

        call_args = mock_run.call_args[0][0]
        assert "--quiet" in call_args

    @patch("subprocess.run")
    def test_load_image_from_tar_file_not_found(self, mock_run):
        """Test load from non-existent tar file."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        with pytest.raises(BuildError) as exc_info:
            mgr.load_image_from_tar(Path("/nonexistent/image.tar"))

        assert "Tar file not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_load_image_from_tar_no_output(self, mock_run, tmp_path):
        """Test load when output doesn't contain image reference."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        tar_file = tmp_path / "nginx.tar"
        tar_file.write_text("dummy")

        mock_run.return_value = Mock(returncode=0, stdout="Some other output\n", stderr="")

        image_ref = mgr.load_image_from_tar(tar_file)

        assert image_ref == ""

    @patch("subprocess.run")
    def test_list_local_images_success(self, mock_run):
        """Test successful local image listing."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(
            returncode=0, stdout="nginx:1.29.2\nregistry:2.8.3\npostgres:15\n", stderr=""
        )

        images = mgr.list_local_images()

        assert len(images) == 3
        assert "nginx:1.29.2" in images
        assert "registry:2.8.3" in images
        assert "postgres:15" in images

    @patch("subprocess.run")
    def test_list_local_images_filters_none(self, mock_run):
        """Test image listing filters out <none> tags."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(
            returncode=0, stdout="nginx:1.29.2\n<none>:<none>\nregistry:2.8.3\n", stderr=""
        )

        images = mgr.list_local_images()

        assert len(images) == 2
        assert "nginx:1.29.2" in images
        assert "registry:2.8.3" in images
        assert "<none>:<none>" not in images

    @patch("subprocess.run")
    def test_list_local_images_empty(self, mock_run):
        """Test listing when no images present."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        images = mgr.list_local_images()

        assert len(images) == 0

    @patch("subprocess.run")
    def test_list_local_images_failure(self, mock_run):
        """Test image listing failure."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error listing images")

        with pytest.raises(BuildError) as exc_info:
            mgr.list_local_images()

        assert "Failed to list images" in str(exc_info.value)

    @patch("subprocess.run")
    def test_inspect_image_success(self, mock_run):
        """Test successful image inspection."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        metadata = {
            "Name": "docker.io/library/nginx:1.29.2",
            "Digest": "sha256:abc123...",
            "RepoTags": ["1.29.2", "latest"],
            "Created": "2024-01-15T10:00:00Z",
        }

        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(metadata), stderr="")

        result = mgr.inspect_image("nginx:1.29.2")

        assert result["Name"] == "docker.io/library/nginx:1.29.2"
        assert result["Digest"] == "sha256:abc123..."
        call_args = mock_run.call_args[0][0]
        assert "skopeo" in call_args
        assert "inspect" in call_args
        assert "docker://nginx:1.29.2" in call_args

    @patch("subprocess.run")
    def test_inspect_image_with_transport(self, mock_run):
        """Test image inspection with explicit transport."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout='{"Name": "test"}', stderr="")

        mgr.inspect_image("docker://nginx:1.29.2")

        call_args = mock_run.call_args[0][0]
        assert "docker://nginx:1.29.2" in call_args

    @patch("subprocess.run")
    def test_inspect_image_failure(self, mock_run):
        """Test image inspection failure."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: image not found")

        with pytest.raises(BuildError) as exc_info:
            mgr.inspect_image("nonexistent:latest")

        assert "Failed to inspect image" in str(exc_info.value)

    @patch("subprocess.run")
    def test_inspect_image_invalid_json(self, mock_run):
        """Test image inspection with invalid JSON response."""
        mock_run.return_value = Mock(returncode=0, stdout="version\n", stderr="")
        mgr = ImageManager()

        mock_run.return_value = Mock(returncode=0, stdout="invalid json{", stderr="")

        with pytest.raises(BuildError) as exc_info:
            mgr.inspect_image("nginx:1.29.2")

        assert "Failed to parse inspect output" in str(exc_info.value)
