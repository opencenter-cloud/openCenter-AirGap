#!/usr/bin/env python3
"""
OpenStack Air-Gap Deployment Integration Test

Provisions 3 controllers, 3 workers, 1 bastion via Terraform.
Simulates air-gap by restricting internet access to bastion only.
Validates full deployment workflow from package transfer to cluster health.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Test configuration
TEST_CONFIG = {
    "openstack": {
        "auth_url": os.getenv("OS_AUTH_URL"),
        "project_name": os.getenv("OS_PROJECT_NAME"),
        "username": os.getenv("OS_USERNAME"),
        "password": os.getenv("OS_PASSWORD"),
        "region": os.getenv("OS_REGION_NAME", "RegionOne"),
    },
    "topology": {
        "bastion": {"count": 1, "flavor": "m1.large", "internet": True},
        "controllers": {"count": 3, "flavor": "m1.xlarge", "internet": False},
        "workers": {"count": 3, "flavor": "m1.xlarge", "internet": False},
    },
    "network": {
        "external_network": os.getenv("OS_EXTERNAL_NETWORK", "public"),
        "internal_cidr": "192.168.100.0/24",
        "dns_servers": ["8.8.8.8", "8.8.4.4"],
    },
    "image": "ubuntu-24.04-amd64",
    "ssh_key_name": os.getenv("OS_SSH_KEY_NAME", "airgap-test-key"),
}


class AirGapDeploymentTest:
    def __init__(self, test_dir: Path):
        self.test_dir = test_dir
        # Use static Terraform files from tests/integration/terraform/
        self.terraform_dir = Path(__file__).parent / "terraform"
        self.inventory_file = test_dir / "inventory.json"
        self.log_file = test_dir / "test.log"
        self.bastion_ip: Optional[str] = None
        self.node_ips: Dict[str, List[str]] = {}

    def log(self, message: str):
        """Log message to stdout and file"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, "a") as f:
            f.write(log_msg + "\n")

    def run_command(self, cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
        """Execute command with logging"""
        self.log(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd or self.test_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.log(f"Command failed: {result.stderr}")
            raise RuntimeError(f"Command failed with exit code {result.returncode}")
        return result

    def generate_terraform_config(self):
        """Generate Terraform tfvars for air-gap topology"""
        self.log("Generating Terraform tfvars")
        
        # Use static Terraform files in tests/integration/terraform/
        # Only generate tfvars with test-specific values
        tfvars = f'''auth_url         = "{TEST_CONFIG["openstack"]["auth_url"]}"
region           = "{TEST_CONFIG["openstack"]["region"]}"
project_name     = "{TEST_CONFIG["openstack"]["project_name"]}"
username         = "{TEST_CONFIG["openstack"]["username"]}"
password         = "{TEST_CONFIG["openstack"]["password"]}"
ssh_key_name     = "{TEST_CONFIG["ssh_key_name"]}"
image            = "{TEST_CONFIG["image"]}"
external_network = "{TEST_CONFIG["network"]["external_network"]}"
internal_cidr    = "{TEST_CONFIG["network"]["internal_cidr"]}"
dns_servers      = {json.dumps(TEST_CONFIG["network"]["dns_servers"])}

bastion_flavor    = "{TEST_CONFIG["topology"]["bastion"]["flavor"]}"
controller_flavor = "{TEST_CONFIG["topology"]["controllers"]["flavor"]}"
controller_count  = {TEST_CONFIG["topology"]["controllers"]["count"]}
worker_flavor     = "{TEST_CONFIG["topology"]["workers"]["flavor"]}"
worker_count      = {TEST_CONFIG["topology"]["workers"]["count"]}
'''
        
        (self.terraform_dir / "terraform.tfvars").write_text(tfvars)
        self.log(f"Terraform tfvars written to {self.terraform_dir}")

    def provision_infrastructure(self):
        """Provision OpenStack infrastructure via Terraform"""
        self.log("Initializing Terraform")
        self.run_command(["terraform", "init"], cwd=self.terraform_dir)

        self.log("Planning Terraform deployment")
        self.run_command(["terraform", "plan", "-out=tfplan"], cwd=self.terraform_dir)

        self.log("Applying Terraform configuration")
        self.run_command(["terraform", "apply", "-auto-approve", "tfplan"], cwd=self.terraform_dir)

        self.log("Extracting outputs")
        result = self.run_command(["terraform", "output", "-json"], cwd=self.terraform_dir)
        outputs = json.loads(result.stdout)

        self.bastion_ip = outputs["bastion_public_ip"]["value"]
        self.node_ips["bastion"] = [outputs["bastion_private_ip"]["value"]]
        self.node_ips["controllers"] = outputs["controller_ips"]["value"]
        self.node_ips["workers"] = outputs["worker_ips"]["value"]

        self.log(f"Bastion public IP: {self.bastion_ip}")
        self.log(f"Controller IPs: {self.node_ips['controllers']}")
        self.log(f"Worker IPs: {self.node_ips['workers']}")

    def wait_for_ssh(self, host: str, timeout: int = 300):
        """Wait for SSH to become available"""
        self.log(f"Waiting for SSH on {host}")
        start = time.time()
        while time.time() - start < timeout:
            result = self.run_command(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 f"ubuntu@{host}", "echo", "ready"],
                check=False
            )
            if result.returncode == 0:
                self.log(f"SSH ready on {host}")
                return
            time.sleep(10)
        raise TimeoutError(f"SSH not available on {host} after {timeout}s")

    def verify_airgap_isolation(self):
        """Verify controllers/workers cannot reach internet"""
        self.log("Verifying air-gap isolation")
        
        # Test bastion has internet
        result = self.run_command(
            ["ssh", f"ubuntu@{self.bastion_ip}", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "https://google.com"],
            check=False
        )
        if result.stdout.strip() != "200":
            raise AssertionError("Bastion should have internet access")
        self.log("✓ Bastion has internet access")

        # Test controllers/workers are isolated (via bastion jump)
        for node_type in ["controllers", "workers"]:
            for ip in self.node_ips[node_type][:1]:  # Test first node of each type
                result = self.run_command(
                    ["ssh", "-J", f"ubuntu@{self.bastion_ip}", f"ubuntu@{ip}",
                     "timeout", "5", "curl", "-s", "https://google.com"],
                    check=False
                )
                if result.returncode == 0:
                    raise AssertionError(f"{node_type} node {ip} should NOT have internet access")
        self.log(f"✓ Controllers and workers are air-gapped")

    def transfer_package_to_bastion(self, package_path: Path):
        """Transfer Zarf package to bastion"""
        self.log(f"Transferring package {package_path} to bastion")
        self.run_command([
            "scp", "-o", "StrictHostKeyChecking=no",
            str(package_path),
            f"ubuntu@{self.bastion_ip}:/tmp/zarf-package.tar.zst"
        ])

    def deploy_cluster(self):
        """Deploy Kubernetes cluster from bastion"""
        self.log("Deploying Zarf package on bastion")
        
        # Generate nodes.json for bare-metal deployment
        nodes_config = {
            "all": {
                "hosts": {}
            }
        }
        
        for i, ip in enumerate(self.node_ips["controllers"], 1):
            nodes_config["all"]["hosts"][f"controller-{i}"] = {
                "ansible_host": ip,
                "ip": ip,
                "access_ip": ip,
                "ansible_user": "ubuntu"
            }
        
        for i, ip in enumerate(self.node_ips["workers"], 1):
            nodes_config["all"]["hosts"][f"worker-{i}"] = {
                "ansible_host": ip,
                "ip": ip,
                "access_ip": ip,
                "ansible_user": "ubuntu"
            }
        
        nodes_json = json.dumps(nodes_config, indent=2)
        
        # Deploy via SSH
        deploy_script = f'''
set -euo pipefail

# Extract package
cd /tmp
zarf package deploy zarf-package.tar.zst --confirm

# Create nodes configuration
cat > /opt/opencenter/nodes.json << 'EOF'
{nodes_json}
EOF

# Run deployment
cd /opt/opencenter
./scripts/deploy/deploy.sh --nodes-file nodes.json --deployment-type baremetal
'''
        
        self.run_command([
            "ssh", f"ubuntu@{self.bastion_ip}",
            "bash", "-c", deploy_script
        ])

    def verify_cluster_health(self):
        """Verify cluster is healthy"""
        self.log("Verifying cluster health")
        
        health_checks = [
            "kubectl get nodes -o wide",
            "kubectl get pods -A",
            "kubectl get svc -A",
        ]
        
        for check in health_checks:
            self.log(f"Running: {check}")
            result = self.run_command([
                "ssh", f"ubuntu@{self.bastion_ip}",
                f"export KUBECONFIG=/opt/opencenter/kubespray/inventory/mycluster/artifacts/admin.conf && {check}"
            ])
            self.log(result.stdout)

    def cleanup(self):
        """Destroy infrastructure"""
        self.log("Destroying infrastructure")
        self.run_command(["terraform", "destroy", "-auto-approve"], cwd=self.terraform_dir)

    def run(self, package_path: Path, cleanup_on_failure: bool = True):
        """Execute full test workflow"""
        try:
            self.generate_terraform_config()
            self.provision_infrastructure()
            self.wait_for_ssh(self.bastion_ip)
            self.verify_airgap_isolation()
            self.transfer_package_to_bastion(package_path)
            self.deploy_cluster()
            self.verify_cluster_health()
            self.log("✓ Test completed successfully")
            return True
        except Exception as e:
            self.log(f"✗ Test failed: {e}")
            if cleanup_on_failure:
                self.cleanup()
            raise
        finally:
            if os.getenv("AIRGAP_TEST_CLEANUP", "true").lower() == "true":
                self.cleanup()


def main():
    if len(sys.argv) < 2:
        print("Usage: test_airgap_deployment.py <zarf-package-path>")
        sys.exit(1)

    package_path = Path(sys.argv[1])
    if not package_path.exists():
        print(f"Package not found: {package_path}")
        sys.exit(1)

    test_dir = Path("build/integration-test-airgap")
    test_dir.mkdir(parents=True, exist_ok=True)

    test = AirGapDeploymentTest(test_dir)
    success = test.run(package_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
