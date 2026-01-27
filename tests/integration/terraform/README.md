# Air-Gap Integration Test Topology

Terraform configuration for provisioning air-gap test environment on OpenStack.

## Topology

- **Bastion**: Internet access, hosts registry/repos
- **Controllers**: Air-gapped, K8s control plane (default: 3)
- **Workers**: Air-gapped, K8s workers (default: 2)

## Security

- Bastion: SSH ingress, full egress
- Air-gapped nodes: Internal network only (no internet)

## Usage

```bash
# Create tfvars from example
cp terraform.tfvars.example terraform.tfvars
# Edit with your OpenStack credentials

# Deploy
terraform init
terraform apply

# Get outputs
terraform output -json > outputs.json

# Destroy
terraform destroy
```

## Integration with test_airgap_deployment.py

Test reads `terraform.tfvars` or environment variables, runs `terraform apply`, parses outputs for node IPs.
