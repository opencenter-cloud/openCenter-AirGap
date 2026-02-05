"""Zarf package manifest generation.

This module provides functionality for generating zarf.yaml manifests from
build configuration. It creates Zarf package definitions with components for
images, charts, repositories, files, and deployment actions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from opencenter_build.config import BuildConfig
from opencenter_build.exceptions import ConfigError


@dataclass
class ZarfGenerator:
    """Generates Zarf package manifests from build configuration.

    The ZarfGenerator creates zarf.yaml files that define Zarf packages for
    air-gapped deployments. It generates components for container images,
    Helm charts, Git repositories, binary files, and deployment actions.

    Attributes:
        config: Build configuration with versions and paths
    """

    config: BuildConfig

    def generate(self, output: Path = Path("zarf.yaml")) -> None:
        """Generate zarf.yaml from configuration.

        Creates a complete Zarf package definition with metadata, variables,
        and components. The generated manifest follows Zarf v0.32+ schema.

        Args:
            output: Output path for zarf.yaml (default: "zarf.yaml")

        Raises:
            ConfigError: If manifest generation or writing fails

        Example:
            >>> config = BuildConfig.from_env_file(Path("config/versions.env"))
            >>> generator = ZarfGenerator(config)
            >>> generator.generate(Path("zarf.yaml"))
        """
        try:
            manifest = self._create_manifest()
            self._write_manifest(manifest, output)
        except Exception as exc:
            raise ConfigError(f"Failed to generate Zarf manifest: {exc}") from exc

    def _create_manifest(self) -> dict[str, Any]:
        """Create complete Zarf manifest structure.

        Returns:
            Dictionary representing complete zarf.yaml structure
        """
        return {
            "kind": "ZarfPackageConfig",
            "metadata": self._create_metadata(),
            "variables": self._create_variables(),
            "components": self._create_components(),
        }

    def _create_metadata(self) -> dict[str, Any]:
        """Create metadata section.

        Returns:
            Metadata dictionary with package information
        """
        return {
            "name": "opencenter-airgap",
            "description": "Air-gapped Kubernetes cluster deployment with Kubespray",
            "version": self.config.opencenter_gitops_base_version.lstrip("v"),
            "architecture": self.config.target_arch,
            "authors": "openCenter Team",
            "url": "https://github.com/opencenter/opencenter-airgap",
            "vendor": "openCenter",
        }

    def _create_variables(self) -> list[dict[str, Any]]:
        """Create variables section.

        Returns:
            List of Zarf variable definitions
        """
        return [
            {
                "name": "DEPLOYMENT_MODE",
                "description": "Deployment mode: baremetal or openstack",
                "default": "baremetal",
                "prompt": False,
            },
            {
                "name": "BASTION_IP",
                "description": "IP address of bastion host",
                "default": "",
                "prompt": True,
            },
            {
                "name": "SSH_USER",
                "description": "SSH user for node access",
                "default": "deployer",
                "prompt": False,
            },
            {
                "name": "INSTALL_PATH",
                "description": "Installation directory on bastion",
                "default": "/opt/opencenter",
                "prompt": False,
            },
            {
                "name": "REGISTRY_PORT",
                "description": "Local registry port",
                "default": "35000",
                "prompt": False,
            },
            {
                "name": "NGINX_PORT",
                "description": "Nginx file server port",
                "default": "80",
                "prompt": False,
            },
        ]

    def _create_components(self) -> list[dict[str, Any]]:
        """Create all Zarf components.

        Returns:
            List of component definitions
        """
        return [
            self._create_bootstrap_component(),
            self._create_terraform_component(),
            self._create_repos_component(),
            self._create_kubespray_component(),
            self._create_images_component(),
            self._create_deploy_component(),
        ]

    def _create_bootstrap_component(self) -> dict[str, Any]:
        """Create bootstrap-tools component.

        Provides Python environment and deployment scripts.

        Returns:
            Bootstrap component definition
        """
        return {
            "name": "bootstrap-tools",
            "description": "Python environment and deployment scripts",
            "required": True,
            "files": [
                {
                    "source": "assets/python-wheels/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/python-wheels/",
                    "executable": False,
                },
                {
                    "source": "assets/target-scripts/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/target-scripts/",
                    "executable": True,
                },
            ],
            "actions": {
                "onDeploy": {
                    "after": [
                        {
                            "cmd": "python3 -m venv ###ZARF_VAR_INSTALL_PATH###/venv",
                            "description": "Create Python virtual environment",
                        },
                        {
                            "cmd": (
                                "###ZARF_VAR_INSTALL_PATH###/venv/bin/pip install "
                                "--no-index --find-links=###ZARF_VAR_INSTALL_PATH###/python-wheels/ "
                                "ansible jinja2 netaddr"
                            ),
                            "description": "Install Python dependencies",
                        },
                    ]
                }
            },
        }

    def _create_terraform_component(self) -> dict[str, Any]:
        """Create terraform-providers component.

        Provides Terraform provider mirror for OpenStack deployments.

        Returns:
            Terraform component definition
        """
        return {
            "name": "terraform-providers",
            "description": "Terraform provider filesystem mirror for OpenStack",
            "required": False,
            "files": [
                {
                    "source": "assets/terraform-mirror/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/terraform-mirror/",
                    "executable": False,
                }
            ],
            "actions": {
                "onDeploy": {
                    "after": [
                        {
                            "cmd": "mkdir -p ###ZARF_VAR_INSTALL_PATH###/terraform-cache",
                            "description": "Create Terraform cache directory",
                        },
                        {
                            "cmd": self._create_terraformrc_command(),
                            "description": "Configure Terraform filesystem mirror",
                        },
                    ]
                }
            },
        }

    def _create_terraformrc_command(self) -> str:
        """Create command to write .terraformrc configuration.

        Returns:
            Shell command string to create .terraformrc
        """
        terraformrc_content = """
plugin_cache_dir   = "###ZARF_VAR_INSTALL_PATH###/terraform-cache"
disable_checkpoint = true

provider_installation {
  filesystem_mirror {
    path    = "###ZARF_VAR_INSTALL_PATH###/terraform-mirror"
    include = ["*/*"]
  }
  direct {
    exclude = ["*/*"]
  }
}
"""
        return f"cat > /root/.terraformrc << 'EOF'\n{terraformrc_content}\nEOF"

    def _create_repos_component(self) -> dict[str, Any]:
        """Create git-repositories component.

        Reads repositories from component manifest and creates Zarf repos
        component. Zarf will clone these during package creation.

        Returns:
            Repositories component definition
        """
        manifest_path = Path("config/components.yaml")
        repos_list = []

        if manifest_path.exists():
            try:
                from opencenter_build.component_manifest import read_manifest

                manifest = read_manifest(manifest_path)
                for repo in manifest.repositories:
                    repos_list.append(f"{repo.url}@{repo.ref}")
            except Exception:
                # If manifest read fails, return empty component
                pass

        return {
            "name": "git-repositories",
            "description": "Git repositories for Kubespray and GitOps",
            "required": True,
            "repos": repos_list,
        }

    def _create_kubespray_component(self) -> dict[str, Any]:
        """Create kubespray-core component.

        Provides Kubespray playbooks, K8s binaries, and package repositories.

        Returns:
            Kubespray component definition
        """
        return {
            "name": "kubespray-core",
            "description": "Kubespray playbooks, K8s binaries, and package repositories",
            "required": True,
            "files": [
                {
                    "source": "assets/kubespray/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/kubespray/",
                    "executable": False,
                },
                {
                    "source": "assets/k8s-binaries/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/k8s-binaries/",
                    "executable": False,
                },
                {
                    "source": "assets/repos/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/repos/",
                    "executable": False,
                },
                {
                    "source": "assets/playbook/",
                    "target": "###ZARF_VAR_INSTALL_PATH###/playbook/",
                    "executable": False,
                },
            ],
        }

    def _create_images_component(self) -> dict[str, Any]:
        """Create k8s-images component from discovered images.

        Reads image list from config/all-images.txt and creates a component
        that loads images into local registry on deployment.

        Returns:
            Images component definition
        """
        return {
            "name": "k8s-images",
            "description": "Container images for Kubernetes and core services",
            "required": False,
            "actions": {
                "onDeploy": {
                    "before": [
                        {
                            "cmd": self._create_image_load_command(),
                            "description": "Load images if available",
                        }
                    ]
                }
            },
        }

    def _create_image_load_command(self) -> str:
        """Create command to load images into registry.

        Returns:
            Shell command string to load and push images
        """
        return """if [ -d "###ZARF_VAR_INSTALL_PATH###/images" ] && [ "$(ls -A ###ZARF_VAR_INSTALL_PATH###/images 2>/dev/null)" ]; then
  podman ps -q -f name=local-registry | grep . || podman run -d -p ###ZARF_VAR_REGISTRY_PORT###:5000 -v /var/lib/registry:/var/lib/registry --restart=always --name local-registry registry:2.8.3
  ###ZARF_VAR_INSTALL_PATH###/target-scripts/load-push-all-images.sh
else
  echo "No images directory found, skipping image loading"
fi"""

    def _create_deploy_component(self) -> dict[str, Any]:
        """Create deploy-cluster component.

        Orchestrates bastion setup including nginx, registry, and Python venv.

        Returns:
            Deploy component definition
        """
        return {
            "name": "deploy-cluster",
            "description": "Cluster deployment orchestration",
            "required": True,
            "actions": {
                "onDeploy": {
                    "after": [
                        {
                            "cmd": "###ZARF_VAR_INSTALL_PATH###/target-scripts/setup-all.sh",
                            "description": "Setup bastion services (nginx, registry, Python)",
                            "dir": "###ZARF_VAR_INSTALL_PATH###",
                        }
                    ]
                }
            },
        }

    def _write_manifest(self, manifest: dict[str, Any], output: Path) -> None:
        """Write manifest to YAML file.

        Args:
            manifest: Manifest dictionary to write
            output: Output file path

        Raises:
            ConfigError: If file cannot be written
        """
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            content = yaml.safe_dump(
                manifest,
                default_flow_style=False,
                sort_keys=False,
                width=120,
                indent=2,
            )
            output.write_text(content)
        except Exception as exc:
            raise ConfigError(f"Failed to write manifest to {output}: {exc}") from exc
