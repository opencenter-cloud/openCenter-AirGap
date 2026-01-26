#!/usr/bin/env python3
"""
Checkpoint 5: Comprehensive Asset Collection Verification

Validates that kubespray-offline asset collection is complete and ready for Zarf packaging.
Checks all required components: binaries, images, packages, scripts, and configurations.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class AssetVerifier:
    def __init__(self, outputs_dir: str):
        self.outputs_dir = Path(outputs_dir)
        self.errors = []
        self.warnings = []
        self.checks_passed = 0
        self.checks_total = 0
        
    def check(self, condition: bool, success_msg: str, error_msg: str) -> bool:
        """Record a check result"""
        self.checks_total += 1
        if condition:
            self.checks_passed += 1
            print(f"{GREEN}✓{RESET} {success_msg}")
            return True
        else:
            self.errors.append(error_msg)
            print(f"{RED}✗{RESET} {error_msg}")
            return False
    
    def warn(self, message: str):
        """Record a warning"""
        self.warnings.append(message)
        print(f"{YELLOW}⚠{RESET} {message}")
    
    def info(self, message: str):
        """Print info message"""
        print(f"{BLUE}ℹ{RESET} {message}")
    
    def verify_kubernetes_binaries(self) -> bool:
        """Verify K8s binaries are present"""
        self.info("\n=== Verifying Kubernetes Binaries ===")
        
        files_dir = self.outputs_dir / "files"
        
        # Check kubernetes directory
        k8s_dir = files_dir / "kubernetes"
        self.check(
            k8s_dir.exists(),
            "Kubernetes directory exists",
            "Kubernetes directory not found"
        )
        
        if k8s_dir.exists():
            # Find version directory
            version_dirs = [d for d in k8s_dir.iterdir() if d.is_dir() and d.name.startswith('v')]
            if version_dirs:
                version_dir = version_dirs[0]
                self.info(f"  Found Kubernetes version: {version_dir.name}")
                
                # Check for required binaries
                required_binaries = ['kubeadm', 'kubectl', 'kubelet']
                for binary in required_binaries:
                    binary_path = version_dir / binary
                    self.check(
                        binary_path.exists(),
                        f"  Binary present: {binary}",
                        f"  Missing binary: {binary}"
                    )
        
        # Check container runtime components
        self.check(
            (files_dir / "runc").exists(),
            "runc directory exists",
            "runc directory not found"
        )
        
        # Check for containerd
        containerd_files = list(files_dir.glob("containerd-*.tar.gz"))
        self.check(
            len(containerd_files) > 0,
            f"containerd archive found: {containerd_files[0].name if containerd_files else 'none'}",
            "containerd archive not found"
        )
        
        # Check for nerdctl
        nerdctl_files = list(files_dir.glob("nerdctl-*.tar.gz"))
        self.check(
            len(nerdctl_files) > 0,
            f"nerdctl archive found: {nerdctl_files[0].name if nerdctl_files else 'none'}",
            "nerdctl archive not found"
        )
        
        # Check for helm
        helm_files = list(files_dir.glob("helm-*.tar.gz"))
        self.check(
            len(helm_files) > 0,
            f"helm archive found: {helm_files[0].name if helm_files else 'none'}",
            "helm archive not found"
        )
        
        # Check for kubespray tarball
        kubespray_files = list(files_dir.glob("kubespray-*.tar.gz"))
        self.check(
            len(kubespray_files) > 0,
            f"kubespray tarball found: {kubespray_files[0].name if kubespray_files else 'none'}",
            "kubespray tarball not found"
        )
        
        return len(self.errors) == 0
    
    def verify_container_images(self) -> bool:
        """Verify container images are present"""
        self.info("\n=== Verifying Container Images ===")
        
        images_dir = self.outputs_dir / "images"
        self.check(
            images_dir.exists(),
            "Images directory exists",
            "Images directory not found"
        )
        
        if not images_dir.exists():
            return False
        
        # Count image files
        image_files = list(images_dir.glob("*.tar.gz"))
        self.info(f"  Total image archives: {len(image_files)}")
        
        # Check for critical images
        critical_images = {
            'registry': 'registry',
            'nginx': 'nginx',
            'kube-apiserver': 'kube-apiserver',
            'kube-controller-manager': 'kube-controller-manager',
            'kube-scheduler': 'kube-scheduler',
            'kube-proxy': 'kube-proxy',
            'etcd': 'etcd',
            'coredns': 'coredns',
        }
        
        for name, pattern in critical_images.items():
            matching = [f for f in image_files if pattern in f.name]
            self.check(
                len(matching) > 0,
                f"  Critical image found: {name}",
                f"  Missing critical image: {name}"
            )
        
        # Check for FluxCD images
        fluxcd_components = ['source-controller', 'kustomize-controller', 'helm-controller', 'notification-controller']
        for component in fluxcd_components:
            matching = [f for f in image_files if component in f.name]
            self.check(
                len(matching) > 0,
                f"  FluxCD component: {component}",
                f"  Missing FluxCD component: {component}"
            )
        
        # Check for cert-manager images
        certmanager_components = ['cert-manager-controller', 'cert-manager-webhook', 'cert-manager-cainjector']
        for component in certmanager_components:
            matching = [f for f in image_files if component in f.name]
            self.check(
                len(matching) > 0,
                f"  cert-manager component: {component}",
                f"  Missing cert-manager component: {component}"
            )
        
        # Check for ingress-nginx
        matching = [f for f in image_files if 'ingress-nginx' in f.name]
        self.check(
            len(matching) > 0,
            "  ingress-nginx controller found",
            "  Missing ingress-nginx controller"
        )
        
        # Check for Keycloak
        matching = [f for f in image_files if 'keycloak' in f.name]
        self.check(
            len(matching) > 0,
            "  Keycloak image found",
            "  Missing Keycloak image"
        )
        
        # Check for Prometheus stack
        prometheus_components = ['prometheus', 'grafana', 'alertmanager']
        for component in prometheus_components:
            matching = [f for f in image_files if component in f.name]
            if len(matching) > 0:
                self.check(True, f"  Prometheus stack: {component}", "")
            else:
                self.warn(f"  Prometheus stack component not found: {component}")
        
        # Check total size
        total_size = sum(f.stat().st_size for f in image_files)
        size_gb = total_size / (1024**3)
        self.info(f"  Total images size: {size_gb:.2f} GB")
        
        if size_gb < 1.0:
            self.warn(f"  Images size seems low ({size_gb:.2f} GB), expected > 2 GB")
        
        return len(self.errors) == 0
    
    def verify_deb_repository(self) -> bool:
        """Verify DEB repository is present"""
        self.info("\n=== Verifying DEB Repository ===")
        
        debs_dir = self.outputs_dir / "debs" / "local"
        self.check(
            debs_dir.exists(),
            "DEB repository directory exists",
            "DEB repository directory not found"
        )
        
        if not debs_dir.exists():
            return False
        
        # Check for repository metadata
        self.check(
            (debs_dir / "Packages.gz").exists(),
            "  Packages.gz present",
            "  Packages.gz not found"
        )
        
        self.check(
            (debs_dir / "Release").exists(),
            "  Release file present",
            "  Release file not found"
        )
        
        # Check for packages directory
        pkgs_dir = debs_dir / "pkgs"
        if pkgs_dir.exists():
            deb_files = list(pkgs_dir.glob("*.deb"))
            self.info(f"  Total DEB packages: {len(deb_files)}")
            self.check(
                len(deb_files) > 100,
                f"  Sufficient packages ({len(deb_files)} packages)",
                f"  Too few packages ({len(deb_files)} packages, expected > 100)"
            )
        
        return len(self.errors) == 0
    
    def verify_pypi_mirror(self) -> bool:
        """Verify PyPI mirror is present"""
        self.info("\n=== Verifying PyPI Mirror ===")
        
        pypi_dir = self.outputs_dir / "pypi"
        self.check(
            pypi_dir.exists(),
            "PyPI directory exists",
            "PyPI directory not found"
        )
        
        if not pypi_dir.exists():
            return False
        
        # Check for required Python packages
        required_packages = [
            'ansible',
            'ansible-core',
            'jinja2',
            'netaddr',
            'pyyaml',
            'cryptography',
        ]
        
        for package in required_packages:
            package_dir = pypi_dir / package
            self.check(
                package_dir.exists(),
                f"  Package directory: {package}",
                f"  Missing package directory: {package}"
            )
        
        # Count total packages
        package_dirs = [d for d in pypi_dir.iterdir() if d.is_dir() and d.name != 'files']
        self.info(f"  Total package directories: {len(package_dirs)}")
        
        # Check for wheel files
        files_dir = pypi_dir / "files"
        if files_dir.exists():
            wheel_files = list(files_dir.glob("*.whl"))
            self.info(f"  Total wheel files: {len(wheel_files)}")
            self.check(
                len(wheel_files) > 10,
                f"  Sufficient wheels ({len(wheel_files)} files)",
                f"  Too few wheels ({len(wheel_files)} files, expected > 10)"
            )
        
        return len(self.errors) == 0
    
    def verify_playbook(self) -> bool:
        """Verify offline-repo.yml playbook is present"""
        self.info("\n=== Verifying Playbook ===")
        
        playbook_dir = self.outputs_dir / "playbook"
        self.check(
            playbook_dir.exists(),
            "Playbook directory exists",
            "Playbook directory not found"
        )
        
        if playbook_dir.exists():
            self.check(
                (playbook_dir / "offline-repo.yml").exists(),
                "  offline-repo.yml present",
                "  offline-repo.yml not found"
            )
            
            roles_dir = playbook_dir / "roles"
            self.check(
                roles_dir.exists(),
                "  roles directory present",
                "  roles directory not found"
            )
        
        return len(self.errors) == 0
    
    def verify_target_scripts(self) -> bool:
        """Verify target scripts are present"""
        self.info("\n=== Verifying Target Scripts ===")
        
        required_scripts = [
            'setup-all.sh',
            'setup-container.sh',
            'start-nginx.sh',
            'start-registry.sh',
            'load-push-all-images.sh',
            'extract-kubespray.sh',
            'setup-offline.sh',
            'setup-py.sh',
            'config.sh',
        ]
        
        for script in required_scripts:
            script_path = self.outputs_dir / script
            self.check(
                script_path.exists(),
                f"  Script present: {script}",
                f"  Missing script: {script}"
            )
            
            # Check if executable
            if script_path.exists() and script.endswith('.sh'):
                is_executable = os.access(script_path, os.X_OK)
                if not is_executable:
                    self.warn(f"  Script not executable: {script}")
        
        return len(self.errors) == 0
    
    def verify_offline_yml(self) -> bool:
        """Verify offline.yml template exists"""
        self.info("\n=== Verifying offline.yml Template ===")
        
        # Check in kubespray-offline root
        offline_yml = self.outputs_dir.parent / "offline.yml"
        self.check(
            offline_yml.exists(),
            f"offline.yml template found at: {offline_yml}",
            "offline.yml template not found"
        )
        
        if offline_yml.exists():
            # Check file size
            size = offline_yml.stat().st_size
            self.check(
                size > 1000,
                f"  offline.yml has content ({size} bytes)",
                f"  offline.yml seems empty ({size} bytes)"
            )
        
        return len(self.errors) == 0
    
    def generate_summary(self) -> Dict:
        """Generate verification summary"""
        return {
            'checks_total': self.checks_total,
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_total - self.checks_passed,
            'errors': self.errors,
            'warnings': self.warnings,
            'success': len(self.errors) == 0
        }
    
    def print_summary(self):
        """Print verification summary"""
        print(f"\n{'='*60}")
        print(f"{BLUE}CHECKPOINT 5: ASSET COLLECTION VERIFICATION SUMMARY{RESET}")
        print(f"{'='*60}")
        
        summary = self.generate_summary()
        
        print(f"\nTotal Checks: {summary['checks_total']}")
        print(f"{GREEN}Passed: {summary['checks_passed']}{RESET}")
        print(f"{RED}Failed: {summary['checks_failed']}{RESET}")
        print(f"{YELLOW}Warnings: {len(summary['warnings'])}{RESET}")
        
        if summary['errors']:
            print(f"\n{RED}ERRORS:{RESET}")
            for error in summary['errors']:
                print(f"  • {error}")
        
        if summary['warnings']:
            print(f"\n{YELLOW}WARNINGS:{RESET}")
            for warning in summary['warnings']:
                print(f"  • {warning}")
        
        print(f"\n{'='*60}")
        if summary['success']:
            print(f"{GREEN}✓ CHECKPOINT PASSED: Asset collection is complete{RESET}")
            print(f"{GREEN}✓ Ready to proceed to Task 7: Asset organization for Zarf{RESET}")
        else:
            print(f"{RED}✗ CHECKPOINT FAILED: Asset collection has issues{RESET}")
            print(f"{RED}✗ Please resolve errors before proceeding{RESET}")
        print(f"{'='*60}\n")
        
        return summary['success']


def main():
    """Main verification function"""
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Checkpoint 5: Verify Asset Collection{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    # Determine outputs directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    outputs_dir = project_root / "build" / "kubespray-offline" / "outputs"
    
    if not outputs_dir.exists():
        print(f"{RED}ERROR: outputs directory not found at {outputs_dir}{RESET}")
        print(f"{RED}Please run kubespray-offline download-all.sh first{RESET}")
        sys.exit(1)
    
    print(f"\nOutputs directory: {outputs_dir}")
    print(f"Starting verification...\n")
    
    # Create verifier
    verifier = AssetVerifier(str(outputs_dir))
    
    # Run all verifications
    verifier.verify_kubernetes_binaries()
    verifier.verify_container_images()
    verifier.verify_deb_repository()
    verifier.verify_pypi_mirror()
    verifier.verify_playbook()
    verifier.verify_target_scripts()
    verifier.verify_offline_yml()
    
    # Print summary
    success = verifier.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
