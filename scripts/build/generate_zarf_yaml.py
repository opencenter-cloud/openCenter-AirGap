#!/usr/bin/env python3
"""
Zarf Package Configuration Generator for openCenter AirGap

Generates zarf.yaml from asset inventory and configuration.
Integrates kubespray-offline outputs into Zarf components.

Requirements: 2.1, 2.3, 2.10
"""

import os
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ZarfVariable:
    """Zarf package variable definition"""
    name: str
    description: str
    default: Optional[str] = None
    prompt: bool = False


@dataclass
class ZarfFile:
    """File mapping for Zarf component"""
    source: str
    target: str
    executable: bool = False


@dataclass
class ZarfAction:
    """Action to execute during deployment"""
    cmd: str
    description: Optional[str] = None
    dir: Optional[str] = None
    env: Optional[List[str]] = None


@dataclass
class ZarfComponent:
    """Zarf package component definition"""
    name: str
    description: str
    required: bool = True
    files: Optional[List[ZarfFile]] = None
    images: Optional[List[str]] = None
    actions: Optional[Dict[str, Dict[str, List[ZarfAction]]]] = None


class ZarfPackageGenerator:
    """Generate zarf.yaml from asset inventory"""
    
    def __init__(self, project_root: Path, config: Dict[str, str]):
        self.project_root = project_root
        self.config = config
        self.assets_dir = project_root / "assets"
        self.version = self._get_version()
        
    def _get_version(self) -> str:
        """Extract version from config or use default"""
        # Try to read from VERSION file or git tag
        version_file = self.project_root / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "1.0.0"
    
    def _discover_images(self) -> List[str]:
        """
        Discover container images from kubespray-offline outputs.
        Images are loaded into podman during asset organization.
        """
        images = []
        
        # Core infrastructure images (from kubespray-offline)
        images.extend([
            f"docker.io/library/registry:{self.config.get('REGISTRY_VERSION', '2.8.3')}",
            f"docker.io/library/nginx:{self.config.get('NGINX_VERSION', '1.29.2')}",
        ])
        
        # Kubernetes control plane images
        k8s_version = self.config.get('KUBERNETES_VERSION', 'v1.34.3')
        images.extend([
            f"registry.k8s.io/kube-apiserver:{k8s_version}",
            f"registry.k8s.io/kube-controller-manager:{k8s_version}",
            f"registry.k8s.io/kube-scheduler:{k8s_version}",
            f"registry.k8s.io/kube-proxy:{k8s_version}",
            f"registry.k8s.io/pause:3.10",
            f"registry.k8s.io/coredns/coredns:v1.11.1",
            f"registry.k8s.io/etcd:3.5.15-0",
        ])
        
        # CNI images (Calico)
        if self.config.get('CNI_PLUGIN') == 'calico':
            images.extend([
                "docker.io/calico/cni:v3.29.1",
                "docker.io/calico/node:v3.29.1",
                "docker.io/calico/kube-controllers:v3.29.1",
            ])
        
        # Core services images
        images.extend([
            f"ghcr.io/fluxcd/source-controller:{self.config.get('FLUXCD_VERSION', 'v2.2.0')}",
            f"ghcr.io/fluxcd/kustomize-controller:{self.config.get('FLUXCD_VERSION', 'v2.2.0')}",
            f"ghcr.io/fluxcd/helm-controller:{self.config.get('FLUXCD_VERSION', 'v2.2.0')}",
            f"ghcr.io/fluxcd/notification-controller:{self.config.get('FLUXCD_VERSION', 'v2.2.0')}",
            f"quay.io/jetstack/cert-manager-controller:{self.config.get('CERT_MANAGER_VERSION', 'v1.13.0')}",
            f"quay.io/jetstack/cert-manager-webhook:{self.config.get('CERT_MANAGER_VERSION', 'v1.13.0')}",
            f"quay.io/jetstack/cert-manager-cainjector:{self.config.get('CERT_MANAGER_VERSION', 'v1.13.0')}",
            f"registry.k8s.io/ingress-nginx/controller:{self.config.get('INGRESS_NGINX_VERSION', 'v1.9.0')}",
            f"quay.io/keycloak/keycloak:{self.config.get('KEYCLOAK_VERSION', '21.1.1')}",
            f"quay.io/prometheus/prometheus:{self.config.get('PROMETHEUS_VERSION', 'v2.48.0')}",
            f"grafana/grafana:{self.config.get('GRAFANA_VERSION', '10.2.0')}",
        ])
        
        return images
    
    def _create_bootstrap_component(self) -> ZarfComponent:
        """Create bootstrap-tools component with Python wheels"""
        files = [
            ZarfFile(
                source="assets/python-wheels/",
                target="###ZARF_VAR_INSTALL_PATH###/python-wheels/"
            ),
            ZarfFile(
                source="assets/target-scripts/",
                target="###ZARF_VAR_INSTALL_PATH###/target-scripts/",
                executable=True
            ),
        ]
        
        # Add Terraform binary if OpenStack mode
        terraform_bin = self.assets_dir / "terraform" / "terraform"
        if terraform_bin.exists():
            files.append(ZarfFile(
                source="assets/terraform/terraform",
                target="/usr/local/bin/terraform",
                executable=True
            ))
        
        actions = {
            "onDeploy": {
                "after": [
                    ZarfAction(
                        cmd="python3 -m venv ###ZARF_VAR_INSTALL_PATH###/venv",
                        description="Create Python virtual environment"
                    ),
                    ZarfAction(
                        cmd="###ZARF_VAR_INSTALL_PATH###/venv/bin/pip install --no-index --find-links=###ZARF_VAR_INSTALL_PATH###/python-wheels/ ansible jinja2 netaddr",
                        description="Install Python dependencies"
                    ),
                ]
            }
        }
        
        return ZarfComponent(
            name="bootstrap-tools",
            description="Python environment and deployment scripts",
            required=True,
            files=files,
            actions=actions
        )
    
    def _create_terraform_component(self) -> ZarfComponent:
        """Create terraform-providers component (optional, OpenStack only)"""
        files = [
            ZarfFile(
                source="assets/terraform-mirror/",
                target="###ZARF_VAR_INSTALL_PATH###/terraform-mirror/"
            ),
        ]
        
        # Create .terraformrc configuration
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
        
        actions = {
            "onDeploy": {
                "after": [
                    ZarfAction(
                        cmd=f"mkdir -p ###ZARF_VAR_INSTALL_PATH###/terraform-cache",
                        description="Create Terraform cache directory"
                    ),
                    ZarfAction(
                        cmd=f"cat > /root/.terraformrc << 'EOF'\n{terraformrc_content}\nEOF",
                        description="Configure Terraform filesystem mirror"
                    ),
                ]
            }
        }
        
        return ZarfComponent(
            name="terraform-providers",
            description="Terraform provider filesystem mirror for OpenStack",
            required=False,
            files=files,
            actions=actions
        )
    
    def _create_kubespray_component(self) -> ZarfComponent:
        """Create kubespray-core component with K8s binaries and playbooks"""
        files = [
            ZarfFile(
                source="assets/kubespray/",
                target="###ZARF_VAR_INSTALL_PATH###/kubespray/"
            ),
            ZarfFile(
                source="assets/k8s-binaries/",
                target="###ZARF_VAR_INSTALL_PATH###/k8s-binaries/"
            ),
            ZarfFile(
                source="assets/repos/",
                target="###ZARF_VAR_INSTALL_PATH###/repos/"
            ),
            ZarfFile(
                source="assets/playbook/",
                target="###ZARF_VAR_INSTALL_PATH###/playbook/"
            ),
        ]
        
        return ZarfComponent(
            name="kubespray-core",
            description="Kubespray playbooks, K8s binaries, and package repositories",
            required=True,
            files=files
        )
    
    def _create_images_component(self) -> ZarfComponent:
        """Create k8s-images component with all container images"""
        images = self._discover_images()
        
        actions = {
            "onDeploy": {
                "before": [
                    ZarfAction(
                        cmd="podman ps -q -f name=local-registry | grep . || podman run -d -p 35000:5000 -v /var/lib/registry:/var/lib/registry --restart=always --name local-registry registry:2",
                        description="Start local container registry on port 35000"
                    ),
                ],
                "after": [
                    ZarfAction(
                        cmd="###ZARF_VAR_INSTALL_PATH###/target-scripts/load-push-all-images.sh",
                        description="Push images to local registry",
                        dir="###ZARF_VAR_INSTALL_PATH###"
                    ),
                ]
            }
        }
        
        return ZarfComponent(
            name="k8s-images",
            description="Container images for Kubernetes and core services",
            required=True,
            images=images,
            actions=actions
        )
    
    def _create_deploy_component(self) -> ZarfComponent:
        """Create deploy-cluster component with orchestration"""
        actions = {
            "onDeploy": {
                "after": [
                    ZarfAction(
                        cmd="###ZARF_VAR_INSTALL_PATH###/target-scripts/setup-all.sh",
                        description="Setup bastion services (nginx, registry, Python)",
                        dir="###ZARF_VAR_INSTALL_PATH###"
                    ),
                ]
            }
        }
        
        return ZarfComponent(
            name="deploy-cluster",
            description="Cluster deployment orchestration",
            required=True,
            actions=actions
        )
    
    def generate(self) -> Dict[str, Any]:
        """Generate complete zarf.yaml structure"""
        
        # Package metadata
        package = {
            "kind": "ZarfPackageConfig",
            "metadata": {
                "name": "openCenter-airgap",
                "description": "Air-gapped Kubernetes cluster deployment with Kubespray",
                "version": self.version,
                "architecture": self.config.get("TARGET_ARCH", "amd64"),
                "authors": "openCenter Team",
                "url": "https://github.com/opencenter/opencenter-airgap",
                "vendor": "openCenter",
            }
        }
        
        # Package variables
        variables = [
            ZarfVariable(
                name="DEPLOYMENT_MODE",
                description="Deployment mode: baremetal or openstack",
                default="baremetal"
            ),
            ZarfVariable(
                name="BASTION_IP",
                description="IP address of bastion host",
                prompt=True
            ),
            ZarfVariable(
                name="SSH_USER",
                description="SSH user for node access",
                default="deployer"
            ),
            ZarfVariable(
                name="INSTALL_PATH",
                description="Installation directory on bastion",
                default="/opt/opencenter"
            ),
            ZarfVariable(
                name="REGISTRY_PORT",
                description="Local registry port",
                default="35000"
            ),
            ZarfVariable(
                name="NGINX_PORT",
                description="Nginx file server port",
                default="80"
            ),
        ]
        
        package["variables"] = [asdict(v) for v in variables]
        
        # Package components
        components = [
            self._create_bootstrap_component(),
            self._create_terraform_component(),
            self._create_kubespray_component(),
            self._create_images_component(),
            self._create_deploy_component(),
        ]
        
        # Convert components to dict format
        package["components"] = []
        for comp in components:
            comp_dict = {"name": comp.name, "description": comp.description, "required": comp.required}
            
            if comp.files:
                comp_dict["files"] = [asdict(f) for f in comp.files]
            
            if comp.images:
                comp_dict["images"] = comp.images
            
            if comp.actions:
                comp_dict["actions"] = {}
                for phase, action_types in comp.actions.items():
                    comp_dict["actions"][phase] = {}
                    for action_type, actions in action_types.items():
                        comp_dict["actions"][phase][action_type] = [
                            {k: v for k, v in asdict(a).items() if v is not None}
                            for a in actions
                        ]
            
            package["components"].append(comp_dict)
        
        return package
    
    def write_yaml(self, output_path: Path):
        """Write generated configuration to zarf.yaml"""
        package = self.generate()
        
        with open(output_path, 'w') as f:
            yaml.dump(package, f, default_flow_style=False, sort_keys=False, width=120)
        
        print(f"Generated zarf.yaml at: {output_path}")
        print(f"Package: {package['metadata']['name']} v{package['metadata']['version']}")
        print(f"Components: {len(package['components'])}")
        print(f"Variables: {len(package['variables'])}")


def load_config(config_file: Path) -> Dict[str, str]:
    """Load configuration from versions.env file"""
    config = {}
    
    if not config_file.exists():
        print(f"Warning: Config file not found: {config_file}", file=sys.stderr)
        return config
    
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                config[key.strip()] = value
    
    return config


def main():
    """Main entry point"""
    project_root = Path(__file__).parent.parent.parent
    config_file = project_root / "config" / "versions.env"
    output_file = project_root / "zarf.yaml"
    
    # Load configuration
    config = load_config(config_file)
    
    # Generate zarf.yaml
    generator = ZarfPackageGenerator(project_root, config)
    generator.write_yaml(output_file)
    
    print("\nNext steps:")
    print("1. Review generated zarf.yaml")
    print("2. Run: zarf package create --confirm")
    print("3. Verify package: zarf package inspect <package-file> --sbom")


if __name__ == "__main__":
    main()
