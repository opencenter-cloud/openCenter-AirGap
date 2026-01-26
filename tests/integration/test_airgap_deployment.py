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
        self.terraform_dir = test_dir / "terraform"
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
        """Generate Terraform configuration for air-gap topology"""
        self.log("Generating Terraform configuration")
        
        terraform_main = f'''
terraform {{
  required_version = ">= 1.6.0"
  required_providers {{
    openstack = {{
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.54.0"
    }}
  }}
}}

provider "openstack" {{
  auth_url    = "{TEST_CONFIG["openstack"]["auth_url"]}"
  region      = "{TEST_CONFIG["openstack"]["region"]}"
  tenant_name = "{TEST_CONFIG["openstack"]["project_name"]}"
  user_name   = "{TEST_CONFIG["openstack"]["username"]}"
  password    = "{TEST_CONFIG["openstack"]["password"]}"
}}

# Network resources
resource "openstack_networking_network_v2" "airgap_network" {{
  name           = "airgap-test-network"
  admin_state_up = true
}}

resource "openstack_networking_subnet_v2" "airgap_subnet" {{
  name       = "airgap-test-subnet"
  network_id = openstack_networking_network_v2.airgap_network.id
  cidr       = "{TEST_CONFIG["network"]["internal_cidr"]}"
  ip_version = 4
  dns_nameservers = {json.dumps(TEST_CONFIG["network"]["dns_servers"])}
}}

resource "openstack_networking_router_v2" "airgap_router" {{
  name                = "airgap-test-router"
  external_network_id = data.openstack_networking_network_v2.external.id
}}

resource "openstack_networking_router_interface_v2" "airgap_router_interface" {{
  router_id = openstack_networking_router_v2.airgap_router.id
  subnet_id = openstack_networking_subnet_v2.airgap_subnet.id
}}

data "openstack_networking_network_v2" "external" {{
  name = "{TEST_CONFIG["network"]["external_network"]}"
}}

# Security groups
resource "openstack_networking_secgroup_v2" "bastion_sg" {{
  name        = "airgap-bastion-sg"
  description = "Bastion security group - internet access allowed"
}}

resource "openstack_networking_secgroup_rule_v2" "bastion_ssh" {{
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.bastion_sg.id
}}

resource "openstack_networking_secgroup_rule_v2" "bastion_egress" {{
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.bastion_sg.id
}}

resource "openstack_networking_secgroup_v2" "airgap_sg" {{
  name        = "airgap-nodes-sg"
  description = "Air-gapped nodes - no internet access"
}}

resource "openstack_networking_secgroup_rule_v2" "airgap_internal" {{
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "{TEST_CONFIG["network"]["internal_cidr"]}"
  security_group_id = openstack_networking_secgroup_v2.airgap_sg.id
}}

resource "openstack_networking_secgroup_rule_v2" "airgap_egress_internal" {{
  direction         = "egress"
  ethertype         = "IPv4"
  remote_ip_prefix  = "{TEST_CONFIG["network"]["internal_cidr"]}"
  security_group_id = openstack_networking_secgroup_v2.airgap_sg.id
}}

# Bastion instance
resource "openstack_compute_instance_v2" "bastion" {{
  name            = "airgap-bastion"
  flavor_name     = "{TEST_CONFIG["topology"]["bastion"]["flavor"]}"
  image_name      = "{TEST_CONFIG["image"]}"
  key_pair        = "{TEST_CONFIG["ssh_key_name"]}"
  security_groups = [openstack_networking_secgroup_v2.bastion_sg.name]

  network {{
    uuid = openstack_networking_network_v2.airgap_network.id
  }}
}}

resource "openstack_networking_floatingip_v2" "bastion_fip" {{
  pool = "{TEST_CONFIG["network"]["external_network"]}"
}}

resource "openstack_compute_floatingip_associate_v2" "bastion_fip_assoc" {{
  floating_ip = openstack_networking_floatingip_v2.bastion_fip.address
  instance_id = openstack_compute_instance_v2.bastion.id
}}

# Controller instances
resource "openstack_compute_instance_v2" "controllers" {{
  count           = {TEST_CONFIG["topology"]["controllers"]["count"]}
  name            = "airgap-controller-${{count.index + 1}}"
  flavor_name     = "{TEST_CONFIG["topology"]["controllers"]["flavor"]}"
  image_name      = "{TEST_CONFIG["image"]}"
  key_pair        = "{TEST_CONFIG["ssh_key_name"]}"
  security_groups = [openstack_networking_secgroup_v2.airgap_sg.name]

  network {{
    uuid = openstack_networking_network_v2.airgap_network.id
  }}
}}

# Worker instances
resource "openstack_compute_instance_v2" "workers" {{
  count           = {TEST_CONFIG["topology"]["workers"]["count"]}
  name            = "airgap-worker-${{count.index + 1}}"
  flavor_name     = "{TEST_CONFIG["topology"]["workers"]["flavor"]}"
  image_name      = "{TEST_CONFIG["image"]}"
  key_pair        = "{TEST_CONFIG["ssh_key_name"]}"
  security_groups = [openstack_networking_secgroup_v2.airgap_sg.name]

  network {{
    uuid = openstack_networking_network_v2.airgap_network.id
  }}
}}

# Outputs
output "bastion_public_ip" {{
  value = openstack_networking_floatingip_v2.bastion_fip.address
}}

output "bastion_private_ip" {{
  value = openstack_compute_instance_v2.bastion.access_ip_v4
}}

output "controller_ips" {{
  value = openstack_compute_instance_v2.controllers[*].access_ip_v4
}}

output "worker_ips" {{
  value = openstack_compute_instance_v2.workers[*].access_ip_v4
}}
'''
        
        self.terraform_dir.mkdir(parents=True, exist_ok=True)
        (self.terraform_dir / "main.tf").write_text(terraform_main)

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
