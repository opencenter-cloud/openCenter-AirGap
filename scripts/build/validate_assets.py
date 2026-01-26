#!/usr/bin/env python3
"""
Asset Organization Validation Script

Validates that kubespray-offline outputs have been correctly organized into
Zarf-compatible asset structure. Verifies all directories, files, and images
are in place for Zarf packaging.

Requirements: 2.3
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class AssetValidator:
    def __init__(self, assets_dir: str):
        self.assets_dir = Path(assets_dir)
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
    
    def verify_directory_structure(self) -> bool:
        """Verify all required directories exist"""
        self.info("\n=== Verifying Directory Structure ===")
        
        required_dirs = [
            'k8s-binaries',
            'python-wheels',
            'repos/apt',
            'target-scripts',
            'kubespray',
            'playbook',
        ]
        
        for dir_name in required_dirs:
            dir_path = self.assets_dir / dir_name
            self.check(
                dir_path.exists() and dir_path.is_dir(),
                f"Directory exists: {dir_name}",
                f"Missing directory: {dir_name}"
            )
        
        return len(self.errors) == 0
    
    def verify_k8s_binaries(self) -> bool:
        """Verify Kubernetes binaries are present"""
        self.info("\n=== Verifying Kubernetes Binaries ===")
        
        k8s_dir = self.assets_dir / "k8s-binaries"
        
        if not k8s_dir.exists():
            self.check(False, "", "k8s-binaries directory not found")
            return False
        
        # Check for kubernetes version directory
        k8s_subdir = k8s_dir / "kubernetes"
        self.check(
            k8s_subdir.exists(),
            "kubernetes/ subdirectory exists",
            "kubernetes/ subdirectory not found"
        )
        
        if k8s_subdir.exists():
            version_dirs = [d for d in k8s_subdir.iterdir() if d.is_dir() and d.name.startswith('v')]
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
            else:
                self.check(False, "", "No Kubernetes version directory found")
        
        # Check for container runtime components
        self.check(
            (k8s_dir / "runc").exists(),
            "runc directory exists",
            "runc directory not found"
        )
        
        # Check for containerd
        containerd_files = list(k8s_dir.glob("containerd-*.tar.gz"))
        self.check(
            len(containerd_files) > 0,
            f"containerd archive found: {containerd_files[0].name if containerd_files else 'none'}",
            "containerd archive not found"
        )
        
        # Check for nerdctl
        nerdctl_files = list(k8s_dir.glob("nerdctl-*.tar.gz"))
        self.check(
            len(nerdctl_files) > 0,
            f"nerdctl archive found: {nerdctl_files[0].name if nerdctl_files else 'none'}",
            "nerdctl archive not found"
        )
        
        # Check for helm
        helm_files = list(k8s_dir.glob("helm-*.tar.gz"))
        self.check(
            len(helm_files) > 0,
            f"helm archive found: {helm_files[0].name if helm_files else 'none'}",
            "helm archive not found"
        )
        
        # Check for kubespray tarball
        kubespray_files = list(k8s_dir.glob("kubespray-*.tar.gz"))
        self.check(
            len(kubespray_files) > 0,
            f"kubespray tarball found: {kubespray_files[0].name if kubespray_files else 'none'}",
            "kubespray tarball not found"
        )
        
        return len(self.errors) == 0
    
    def verify_python_wheels(self) -> bool:
        """Verify Python wheels are present"""
        self.info("\n=== Verifying Python Wheels ===")
        
        wheels_dir = self.assets_dir / "python-wheels"
        
        if not wheels_dir.exists():
            self.check(False, "", "python-wheels directory not found")
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
            package_dir = wheels_dir / package
            self.check(
                package_dir.exists(),
                f"  Package directory: {package}",
                f"  Missing package directory: {package}"
            )
        
        # Count total package directories
        package_dirs = [d for d in wheels_dir.iterdir() if d.is_dir() and d.name != 'files']
        self.info(f"  Total package directories: {len(package_dirs)}")
        
        # Check for wheel files
        files_dir = wheels_dir / "files"
        if files_dir.exists():
            wheel_files = list(files_dir.glob("*.whl"))
            self.info(f"  Total wheel files: {len(wheel_files)}")
            self.check(
                len(wheel_files) > 10,
                f"  Sufficient wheels ({len(wheel_files)} files)",
                f"  Too few wheels ({len(wheel_files)} files, expected > 10)"
            )
        else:
            self.warn("  files/ subdirectory not found in python-wheels")
        
        return len(self.errors) == 0
    
    def verify_apt_repository(self) -> bool:
        """Verify apt repository is present"""
        self.info("\n=== Verifying Apt Repository ===")
        
        apt_dir = self.assets_dir / "repos" / "apt"
        
        if not apt_dir.exists():
            self.check(False, "", "repos/apt directory not found")
            return False
        
        # Check for local repository
        local_dir = apt_dir / "local"
        self.check(
            local_dir.exists(),
            "local/ subdirectory exists",
            "local/ subdirectory not found"
        )
        
        if local_dir.exists():
            # Check for repository metadata
            self.check(
                (local_dir / "Packages.gz").exists(),
                "  Packages.gz present",
                "  Packages.gz not found"
            )
            
            self.check(
                (local_dir / "Release").exists(),
                "  Release file present",
                "  Release file not found"
            )
            
            # Check for packages directory
            pkgs_dir = local_dir / "pkgs"
            if pkgs_dir.exists():
                deb_files = list(pkgs_dir.glob("*.deb"))
                self.info(f"  Total DEB packages: {len(deb_files)}")
                self.check(
                    len(deb_files) > 50,
                    f"  Sufficient packages ({len(deb_files)} packages)",
                    f"  Too few packages ({len(deb_files)} packages, expected > 50)"
                )
            else:
                self.warn("  pkgs/ subdirectory not found")
        
        return len(self.errors) == 0
    
    def verify_target_scripts(self) -> bool:
        """Verify target scripts are present"""
        self.info("\n=== Verifying Target Scripts ===")
        
        scripts_dir = self.assets_dir / "target-scripts"
        
        if not scripts_dir.exists():
            self.check(False, "", "target-scripts directory not found")
            return False
        
        # Check for required scripts
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
            script_path = scripts_dir / script
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
    
    def verify_kubespray_extraction(self) -> bool:
        """Verify Kubespray tarball was extracted correctly"""
        self.info("\n=== Verifying Kubespray Extraction ===")
        
        kubespray_dir = self.assets_dir / "kubespray"
        
        if not kubespray_dir.exists():
            self.check(False, "", "kubespray directory not found")
            return False
        
        # Check for kubespray-master directory
        master_dir = kubespray_dir / "kubespray-master"
        self.check(
            master_dir.exists(),
            "kubespray-master/ directory exists",
            "kubespray-master/ directory not found"
        )
        
        if master_dir.exists():
            # Check for key Kubespray files
            key_files = [
                'cluster.yml',
                'requirements.txt',
                'ansible.cfg',
            ]
            
            for file_name in key_files:
                file_path = master_dir / file_name
                self.check(
                    file_path.exists(),
                    f"  File present: {file_name}",
                    f"  Missing file: {file_name}"
                )
            
            # Check for roles directory
            roles_dir = master_dir / "roles"
            self.check(
                roles_dir.exists() and roles_dir.is_dir(),
                "  roles/ directory exists",
                "  roles/ directory not found"
            )
            
            # Check for inventory directory
            inventory_dir = master_dir / "inventory"
            self.check(
                inventory_dir.exists() and inventory_dir.is_dir(),
                "  inventory/ directory exists",
                "  inventory/ directory not found"
            )
        
        return len(self.errors) == 0
    
    def verify_playbook(self) -> bool:
        """Verify playbook directory is present"""
        self.info("\n=== Verifying Playbook ===")
        
        playbook_dir = self.assets_dir / "playbook"
        
        if not playbook_dir.exists():
            self.check(False, "", "playbook directory not found")
            return False
        
        # Check for offline-repo.yml
        self.check(
            (playbook_dir / "offline-repo.yml").exists(),
            "offline-repo.yml present",
            "offline-repo.yml not found"
        )
        
        # Check for roles directory
        roles_dir = playbook_dir / "roles"
        self.check(
            roles_dir.exists() and roles_dir.is_dir(),
            "roles/ directory exists",
            "roles/ directory not found"
        )
        
        return len(self.errors) == 0
    
    def verify_images_in_podman(self) -> bool:
        """Verify container images are loaded in podman (optional check)"""
        self.info("\n=== Verifying Container Images in Podman ===")
        
        # Check if podman is available
        try:
            result = subprocess.run(
                ['podman', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.warn("podman not available, skipping image verification")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.warn("podman not available, skipping image verification")
            return True
        
        # List images in podman
        try:
            result = subprocess.run(
                ['podman', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                images = result.stdout.strip().split('\n')
                images = [img for img in images if img and img != '<none>:<none>']
                self.info(f"  Total images in podman: {len(images)}")
                
                # Check for critical images
                critical_images = [
                    'registry',
                    'nginx',
                    'kube-apiserver',
                    'kube-controller-manager',
                    'etcd',
                ]
                
                for critical in critical_images:
                    matching = [img for img in images if critical in img]
                    if matching:
                        self.check(True, f"  Image loaded: {critical}", "")
                    else:
                        self.warn(f"  Image not found in podman: {critical}")
                
                # Note: Image loading is optional for Zarf packaging
                self.info("  Note: Zarf can package images directly from tar.gz files")
            else:
                self.warn("Could not list podman images")
        
        except subprocess.TimeoutExpired:
            self.warn("podman images command timed out")
        
        return True  # This is an optional check
    
    def calculate_total_size(self) -> Tuple[float, Dict[str, float]]:
        """Calculate total size of organized assets"""
        self.info("\n=== Calculating Asset Sizes ===")
        
        sizes = {}
        
        for subdir in ['k8s-binaries', 'python-wheels', 'repos/apt', 'target-scripts', 'kubespray', 'playbook']:
            dir_path = self.assets_dir / subdir
            if dir_path.exists():
                total = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                sizes[subdir] = total / (1024**3)  # Convert to GB
                self.info(f"  {subdir}: {sizes[subdir]:.2f} GB")
        
        total_size = sum(sizes.values())
        self.info(f"  Total: {total_size:.2f} GB")
        
        # Check if size is reasonable
        if total_size < 1.0:
            self.warn(f"Total size seems low ({total_size:.2f} GB), expected > 2 GB")
        elif total_size > 20.0:
            self.warn(f"Total size is very large ({total_size:.2f} GB), expected < 15 GB")
        
        return total_size, sizes
    
    def generate_summary(self) -> Dict:
        """Generate validation summary"""
        return {
            'checks_total': self.checks_total,
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_total - self.checks_passed,
            'errors': self.errors,
            'warnings': self.warnings,
            'success': len(self.errors) == 0
        }
    
    def print_summary(self):
        """Print validation summary"""
        print(f"\n{'='*60}")
        print(f"{BLUE}ASSET ORGANIZATION VALIDATION SUMMARY{RESET}")
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
            print(f"{GREEN}✓ VALIDATION PASSED: Assets organized correctly{RESET}")
            print(f"{GREEN}✓ Ready for Zarf packaging{RESET}")
        else:
            print(f"{RED}✗ VALIDATION FAILED: Asset organization has issues{RESET}")
            print(f"{RED}✗ Please resolve errors before proceeding{RESET}")
        print(f"{'='*60}\n")
        
        return summary['success']


def main():
    """Main validation function"""
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Asset Organization Validation{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    # Determine assets directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    assets_dir = project_root / "assets"
    
    if not assets_dir.exists():
        print(f"{RED}ERROR: assets directory not found at {assets_dir}{RESET}")
        print(f"{RED}Please run organize_assets_for_zarf.sh first{RESET}")
        sys.exit(1)
    
    print(f"\nAssets directory: {assets_dir}")
    print(f"Starting validation...\n")
    
    # Create validator
    validator = AssetValidator(str(assets_dir))
    
    # Run all validations
    validator.verify_directory_structure()
    validator.verify_k8s_binaries()
    validator.verify_python_wheels()
    validator.verify_apt_repository()
    validator.verify_target_scripts()
    validator.verify_kubespray_extraction()
    validator.verify_playbook()
    validator.verify_images_in_podman()
    validator.calculate_total_size()
    
    # Print summary
    success = validator.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
