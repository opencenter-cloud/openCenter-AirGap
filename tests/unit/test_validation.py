"""Unit tests for configuration validation module.

Tests cover:
- Schema loading and validation
- Valid configuration acceptance
- Invalid configuration rejection
- Missing field detection
- Pattern validation (versions, IPs, hostnames)
- Clear error messages
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

from opencenter_build.validation import ConfigValidator
from opencenter_build.exceptions import ValidationError


@pytest.fixture
def schema_dir() -> Path:
    """Get schema directory path."""
    return Path("config/schemas")


@pytest.fixture
def validator(schema_dir: Path) -> ConfigValidator:
    """Create ConfigValidator instance."""
    return ConfigValidator(schema_dir)


class TestConfigValidatorInit:
    """Test ConfigValidator initialization."""

    def test_init_with_valid_schema_dir(self, schema_dir: Path) -> None:
        """Test initialization with valid schema directory."""
        validator = ConfigValidator(schema_dir)
        assert validator.schema_dir == schema_dir

    def test_init_with_nonexistent_schema_dir(self) -> None:
        """Test initialization with nonexistent schema directory."""
        with pytest.raises(ValidationError, match="Schema directory not found"):
            ConfigValidator(Path("/nonexistent/schemas"))


class TestVersionsEnvValidation:
    """Test versions.env validation."""

    def test_valid_versions_env(self, validator: ConfigValidator) -> None:
        """Test validation of valid versions.env configuration."""
        config = {
            "KUBERNETES_VERSION": "v1.34.3",
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "calico",
            "FLUXCD_VERSION": "v2.2.0",
            "GITEA_VERSION": "1.21.0",
        }
        # Should not raise
        validator.validate_versions_env(config)

    def test_missing_required_field(self, validator: ConfigValidator) -> None:
        """Test validation fails when required field is missing."""
        config = {
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            # Missing KUBERNETES_VERSION
        }
        with pytest.raises(ValidationError, match="KUBERNETES_VERSION"):
            validator.validate_versions_env(config)

    def test_invalid_kubernetes_version_format(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid Kubernetes version format."""
        config = {
            "KUBERNETES_VERSION": "1.34.3",  # Missing 'v' prefix
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "calico",
        }
        with pytest.raises(ValidationError, match="KUBERNETES_VERSION"):
            validator.validate_versions_env(config)

    def test_invalid_terraform_version_format(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid Terraform version format."""
        config = {
            "KUBERNETES_VERSION": "v1.34.3",
            "TERRAFORM_VERSION": "v1.6.6",  # Should not have 'v' prefix
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "calico",
        }
        with pytest.raises(ValidationError, match="TERRAFORM_VERSION"):
            validator.validate_versions_env(config)

    def test_invalid_container_runtime(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid container runtime."""
        config = {
            "KUBERNETES_VERSION": "v1.34.3",
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "docker",  # Not in enum
            "CNI_PLUGIN": "calico",
        }
        with pytest.raises(ValidationError, match="CONTAINER_RUNTIME"):
            validator.validate_versions_env(config)

    def test_invalid_cni_plugin(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid CNI plugin."""
        config = {
            "KUBERNETES_VERSION": "v1.34.3",
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "weave",  # Not in enum
        }
        with pytest.raises(ValidationError, match="CNI_PLUGIN"):
            validator.validate_versions_env(config)

    def test_valid_commit_sha(self, validator: ConfigValidator) -> None:
        """Test validation accepts valid commit SHA."""
        config = {
            "KUBERNETES_VERSION": "v1.34.3",
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "calico",
            "KUBESPRAY_COMMIT_SHA": "abc123def456789012345678901234567890abcd",
        }
        validator.validate_versions_env(config)

    def test_invalid_commit_sha_length(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid commit SHA length."""
        config = {
            "KUBERNETES_VERSION": "v1.34.3",
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "calico",
            "KUBESPRAY_COMMIT_SHA": "abc123",  # Too short
        }
        with pytest.raises(ValidationError, match="KUBESPRAY_COMMIT_SHA"):
            validator.validate_versions_env(config)


class TestNodesFileValidation:
    """Test node inventory validation."""

    def test_valid_nodes_config(self, validator: ConfigValidator) -> None:
        """Test validation of valid node configuration."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "192.168.1.10"},
                {"hostname": "control-02", "ip": "192.168.1.11"},
                {"hostname": "control-03", "ip": "192.168.1.12"},
            ],
            "workers": [
                {"hostname": "worker-01", "ip": "192.168.1.20"},
                {"hostname": "worker-02", "ip": "192.168.1.21"},
            ],
        }
        validator.validate_nodes_file(config)

    def test_missing_control_plane(self, validator: ConfigValidator) -> None:
        """Test validation fails when control_plane is missing."""
        config = {
            "workers": [
                {"hostname": "worker-01", "ip": "192.168.1.20"},
            ],
        }
        with pytest.raises(ValidationError, match="control_plane"):
            validator.validate_nodes_file(config)

    def test_empty_control_plane(self, validator: ConfigValidator) -> None:
        """Test validation fails when control_plane is empty."""
        config = {
            "control_plane": [],
            "workers": [
                {"hostname": "worker-01", "ip": "192.168.1.20"},
            ],
        }
        with pytest.raises(ValidationError, match="control_plane"):
            validator.validate_nodes_file(config)

    def test_missing_hostname(self, validator: ConfigValidator) -> None:
        """Test validation fails when hostname is missing."""
        config = {
            "control_plane": [
                {"ip": "192.168.1.10"},  # Missing hostname
            ],
            "workers": [],
        }
        with pytest.raises(ValidationError, match="hostname"):
            validator.validate_nodes_file(config)

    def test_missing_ip(self, validator: ConfigValidator) -> None:
        """Test validation fails when IP is missing."""
        config = {
            "control_plane": [
                {"hostname": "control-01"},  # Missing ip
            ],
            "workers": [],
        }
        with pytest.raises(ValidationError, match="ip"):
            validator.validate_nodes_file(config)

    def test_invalid_hostname_format(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid hostname format."""
        config = {
            "control_plane": [
                {"hostname": "Control_01", "ip": "192.168.1.10"},  # Uppercase and underscore
            ],
            "workers": [],
        }
        with pytest.raises(ValidationError):
            validator.validate_nodes_file(config)

    def test_invalid_ip_format(self, validator: ConfigValidator) -> None:
        """Test validation accepts any string for IP (format validation not enforced)."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "999.999.999.999"},  # Invalid but accepted
            ],
            "workers": [],
        }
        # IP format validation not enforced - Kubespray will validate at deployment time
        validator.validate_nodes_file(config)

    def test_valid_ipv6(self, validator: ConfigValidator) -> None:
        """Test validation accepts valid IPv6 addresses."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "2001:db8::1"},
            ],
            "workers": [],
        }
        validator.validate_nodes_file(config)

    def test_optional_ssh_port(self, validator: ConfigValidator) -> None:
        """Test validation accepts optional ssh_port field."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "192.168.1.10", "ssh_port": 2222},
            ],
            "workers": [],
        }
        validator.validate_nodes_file(config)

    def test_invalid_ssh_port(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid SSH port."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "192.168.1.10", "ssh_port": 99999},
            ],
            "workers": [],
        }
        with pytest.raises(ValidationError, match="ssh_port"):
            validator.validate_nodes_file(config)

    def test_optional_ansible_host(self, validator: ConfigValidator) -> None:
        """Test validation accepts optional ansible_host field."""
        config = {
            "control_plane": [
                {
                    "hostname": "control-01",
                    "ip": "192.168.1.10",
                    "ansible_host": "10.0.0.100",
                },
            ],
            "workers": [],
        }
        validator.validate_nodes_file(config)

    def test_node_labels(self, validator: ConfigValidator) -> None:
        """Test validation accepts node labels."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "192.168.1.10"},
            ],
            "workers": [
                {
                    "hostname": "worker-01",
                    "ip": "192.168.1.20",
                    "node_labels": {"role": "compute", "zone": "us-east-1a"},
                },
            ],
        }
        validator.validate_nodes_file(config)

    def test_node_taints(self, validator: ConfigValidator) -> None:
        """Test validation accepts node taints."""
        config = {
            "control_plane": [
                {"hostname": "control-01", "ip": "192.168.1.10"},
            ],
            "workers": [
                {
                    "hostname": "worker-01",
                    "ip": "192.168.1.20",
                    "node_taints": ["dedicated=gpu:NoSchedule"],
                },
            ],
        }
        validator.validate_nodes_file(config)


class TestOpenStackConfigValidation:
    """Test OpenStack configuration validation."""

    def test_valid_openstack_config(self, validator: ConfigValidator) -> None:
        """Test validation of valid OpenStack configuration."""
        config = {
            "auth_url": "https://openstack.example.com:5000/v3",
            "project_name": "my-project",
            "username": "my-user",
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 3,
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
        }
        validator.validate_openstack_config(config)

    def test_missing_required_field(self, validator: ConfigValidator) -> None:
        """Test validation fails when required field is missing."""
        config = {
            "auth_url": "https://openstack.example.com:5000/v3",
            "project_name": "my-project",
            # Missing username
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 3,
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
        }
        with pytest.raises(ValidationError, match="username"):
            validator.validate_openstack_config(config)

    def test_invalid_auth_url(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid auth_url."""
        config = {
            "auth_url": "not-a-url",
            "project_name": "my-project",
            "username": "my-user",
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 3,
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
        }
        with pytest.raises(ValidationError):
            validator.validate_openstack_config(config)

    def test_invalid_control_plane_count(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid control_plane_count."""
        config = {
            "auth_url": "https://openstack.example.com:5000/v3",
            "project_name": "my-project",
            "username": "my-user",
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 0,  # Must be at least 1
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
        }
        with pytest.raises(ValidationError, match="control_plane_count"):
            validator.validate_openstack_config(config)

    def test_optional_floating_ip_pool(self, validator: ConfigValidator) -> None:
        """Test validation accepts optional floating_ip_pool."""
        config = {
            "auth_url": "https://openstack.example.com:5000/v3",
            "project_name": "my-project",
            "username": "my-user",
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 3,
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
            "floating_ip_pool": "public",
        }
        validator.validate_openstack_config(config)

    def test_optional_volume_size(self, validator: ConfigValidator) -> None:
        """Test validation accepts optional volume_size."""
        config = {
            "auth_url": "https://openstack.example.com:5000/v3",
            "project_name": "my-project",
            "username": "my-user",
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 3,
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
            "volume_size": 100,
        }
        validator.validate_openstack_config(config)

    def test_invalid_volume_size(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid volume_size."""
        config = {
            "auth_url": "https://openstack.example.com:5000/v3",
            "project_name": "my-project",
            "username": "my-user",
            "password": "my-password",
            "region": "RegionOne",
            "control_plane_count": 3,
            "worker_count": 2,
            "flavor": "m1.large",
            "image": "ubuntu-24.04",
            "network": "private-network",
            "key_pair": "my-keypair",
            "volume_size": 10,  # Below minimum of 20
        }
        with pytest.raises(ValidationError, match="volume_size"):
            validator.validate_openstack_config(config)


class TestZarfVariablesValidation:
    """Test Zarf variables validation."""

    def test_valid_zarf_variables(self, validator: ConfigValidator) -> None:
        """Test validation of valid Zarf variables."""
        config = {
            "install_path": "/opt/opencenter",
            "registry_host": "localhost",
            "registry_port": 5000,
            "cluster_name": "opencenter-cluster",
        }
        validator.validate_zarf_variables(config)

    def test_invalid_install_path(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid install_path."""
        config = {
            "install_path": "opt/opencenter",  # Missing leading slash
        }
        with pytest.raises(ValidationError, match="install_path"):
            validator.validate_zarf_variables(config)

    def test_invalid_registry_port(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid registry_port."""
        config = {
            "registry_port": 99999,  # Above maximum
        }
        with pytest.raises(ValidationError, match="registry_port"):
            validator.validate_zarf_variables(config)

    def test_invalid_cluster_name(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid cluster_name."""
        config = {
            "cluster_name": "OpenCenter_Cluster",  # Uppercase and underscore
        }
        with pytest.raises(ValidationError):
            validator.validate_zarf_variables(config)

    def test_invalid_pod_network_cidr(self, validator: ConfigValidator) -> None:
        """Test validation fails for invalid pod_network_cidr."""
        config = {
            "pod_network_cidr": "10.244.0.0",  # Missing /prefix
        }
        with pytest.raises(ValidationError, match="pod_network_cidr"):
            validator.validate_zarf_variables(config)

    def test_valid_boolean_flags(self, validator: ConfigValidator) -> None:
        """Test validation accepts boolean flags."""
        config = {
            "enable_metrics_server": True,
            "enable_ingress": False,
            "enable_cert_manager": True,
        }
        validator.validate_zarf_variables(config)


class TestSchemaLoading:
    """Test schema loading functionality."""

    def test_load_nonexistent_schema(self, validator: ConfigValidator) -> None:
        """Test loading nonexistent schema raises error."""
        with pytest.raises(ValidationError, match="Schema not found"):
            validator._load_schema("nonexistent.schema.json")

    def test_load_all_schemas(self, validator: ConfigValidator) -> None:
        """Test all schemas can be loaded successfully."""
        schemas = [
            "versions.schema.json",
            "nodes.schema.json",
            "openstack-config.schema.json",
            "zarf-variables.schema.json",
        ]
        for schema_name in schemas:
            schema = validator._load_schema(schema_name)
            assert isinstance(schema, dict)
            assert "$schema" in schema


class TestErrorMessages:
    """Test error message clarity."""

    def test_error_message_includes_field_path(self, validator: ConfigValidator) -> None:
        """Test error messages include field path."""
        config = {
            "control_plane": [
                {"hostname": "control-01"},  # Missing ip
            ],
            "workers": [],
        }
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_nodes_file(config)

        error_message = str(exc_info.value)
        assert "control_plane" in error_message or "ip" in error_message

    def test_error_message_for_pattern_mismatch(self, validator: ConfigValidator) -> None:
        """Test error messages for pattern validation failures."""
        config = {
            "KUBERNETES_VERSION": "1.34.3",  # Missing 'v' prefix
            "TERRAFORM_VERSION": "1.6.6",
            "KUBESPRAY_VERSION": "v2.24.0",
            "UBUNTU_VERSION": "24.04",
            "CONTAINER_RUNTIME": "containerd",
            "CNI_PLUGIN": "calico",
        }
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_versions_env(config)

        error_message = str(exc_info.value)
        assert "KUBERNETES_VERSION" in error_message
