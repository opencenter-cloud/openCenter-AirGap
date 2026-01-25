# Zarf Variables Reference

**doc_type**: reference

**Purpose**: Complete reference for all Zarf variables used in openCenter AirGap package configuration.

**Audience**: Platform engineers and field operators configuring deployments.

## Overview

Zarf variables allow runtime customization of the deployment without rebuilding the package. Variables are set during package deployment using the `--set` flag or via interactive prompts.

## Variable Syntax

Variables in Zarf manifests use the format:
```
###ZARF_VAR_VARIABLE_NAME###
```

Set variables during deployment:
```bash
zarf package deploy package.tar.zst \
  --set VARIABLE_NAME=value \
  --set ANOTHER_VAR=value
```

## Core Variables

### DEPLOYMENT_MODE

**Type**: String (enum)  
**Required**: No  
**Default**: `baremetal`  
**Valid Values**: `baremetal`, `openstack`

Determines the infrastructure provisioning method.

**Usage**:
```bash
--set DEPLOYMENT_MODE=baremetal
--set DEPLOYMENT_MODE=openstack
```

**Behavior**:
- `baremetal`: Skips Terraform provisioning, uses provided inventory
- `openstack`: Executes Terraform to provision VMs on OpenStack

**Example**:
```yaml
# In zarf.yaml
components:
  - name: terraform-provision
    required: false
    onlyIf: "###ZARF_VAR_DEPLOYMENT_MODE### == openstack"
```

### BASTION_IP

**Type**: String (IP address)  
**Required**: Yes  
**Default**: None

IP address of the bastion host where services are running.

**Usage**:
```bash
--set BASTION_IP=192.168.1.100
```

**Behavior**:
- Used to configure Kubespray offline.yml
- Nodes connect to this IP for registry (port 35000) and files (port 80)
- Must be reachable from all cluster nodes

**Validation**:
- Must be valid IPv4 address
- Must be reachable from target nodes

**Example**:
```yaml
# In offline.yml template
http_server: "http://###ZARF_VAR_BASTION_IP###"
registry_host: "###ZARF_VAR_BASTION_IP###:35000"
```

### SSH_USER

**Type**: String  
**Required**: No  
**Default**: `deployer`

SSH username for accessing target nodes.

**Usage**:
```bash
--set SSH_USER=ubuntu
--set SSH_USER=deployer
```

**Behavior**:
- Used by Ansible for node configuration
- User must have sudo privileges
- SSH key authentication must be configured

**Common Values**:
- `ubuntu`: Default for Ubuntu cloud images
- `deployer`: Custom deployment user
- `root`: Direct root access (not recommended)

**Example**:
```yaml
# In Ansible inventory
ansible_user: ###ZARF_VAR_SSH_USER###
```

### INSTALL_PATH

**Type**: String (filesystem path)  
**Required**: No  
**Default**: `/opt/opencenter`

Installation directory on bastion host.

**Usage**:
```bash
--set INSTALL_PATH=/opt/opencenter
--set INSTALL_PATH=/data/k8s-deploy
```

**Behavior**:
- All assets extracted to this location
- Scripts, binaries, and configurations stored here
- Must have sufficient disk space (100GB+)

**Requirements**:
- Directory must be writable
- Sufficient disk space available
- Absolute path required

**Example**:
```yaml
# In zarf.yaml
files:
  - source: kubespray/
    target: ###ZARF_VAR_INSTALL_PATH###/kubespray/
```

### REGISTRY_PORT

**Type**: Integer  
**Required**: No  
**Default**: `35000`

Port number for the container registry service.

**Usage**:
```bash
--set REGISTRY_PORT=35000
--set REGISTRY_PORT=5000
```

**Behavior**:
- Registry container listens on this port
- Nodes pull images from `BASTION_IP:REGISTRY_PORT`
- Port must be available on bastion

**Constraints**:
- Must be > 1024 (non-privileged)
- Must not conflict with other services
- Default 35000 matches kubespray-offline standard

**Example**:
```yaml
# In start-registry.sh
podman run -d -p ###ZARF_VAR_REGISTRY_PORT###:5000 registry:2
```

### NGINX_PORT

**Type**: Integer  
**Required**: No  
**Default**: `80`

Port number for the nginx file server.

**Usage**:
```bash
--set NGINX_PORT=80
--set NGINX_PORT=8080
```

**Behavior**:
- Nginx serves files, apt packages, and PyPI mirror
- Nodes download binaries from `http://BASTION_IP:NGINX_PORT/files/`
- Port must be available on bastion

**Constraints**:
- Port 80 requires root or CAP_NET_BIND_SERVICE
- Default 80 matches kubespray-offline standard
- If changed, update offline.yml accordingly

**Example**:
```yaml
# In start-nginx.sh
podman run -d -p ###ZARF_VAR_NGINX_PORT###:80 nginx:1.29.2
```

## OpenStack-Specific Variables

These variables are only used when `DEPLOYMENT_MODE=openstack`.

### OS_AUTH_URL

**Type**: String (URL)  
**Required**: Yes (OpenStack mode)  
**Default**: None

OpenStack authentication endpoint.

**Usage**:
```bash
--set OS_AUTH_URL=https://openstack.example.com:5000/v3
```

**Example**:
```
https://openstack.example.com:5000/v3
https://10.0.0.5:5000/v3
```

### OS_PROJECT_NAME

**Type**: String  
**Required**: Yes (OpenStack mode)  
**Default**: None

OpenStack project (tenant) name.

**Usage**:
```bash
--set OS_PROJECT_NAME=kubernetes-prod
```

### OS_USERNAME

**Type**: String  
**Required**: Yes (OpenStack mode)  
**Default**: None

OpenStack username for authentication.

**Usage**:
```bash
--set OS_USERNAME=k8s-deployer
```

### OS_PASSWORD

**Type**: String (sensitive)  
**Required**: Yes (OpenStack mode)  
**Default**: None

OpenStack password for authentication.

**Usage**:
```bash
--set OS_PASSWORD=secret-password
```

**Security Note**: Consider using environment variables or secure credential stores instead of command-line arguments.

### OS_REGION

**Type**: String  
**Required**: No  
**Default**: `RegionOne`

OpenStack region name.

**Usage**:
```bash
--set OS_REGION=RegionOne
--set OS_REGION=us-west-1
```

## Advanced Variables

### CLUSTER_NAME

**Type**: String  
**Required**: No  
**Default**: `mycluster`

Kubernetes cluster name.

**Usage**:
```bash
--set CLUSTER_NAME=production
--set CLUSTER_NAME=staging
```

**Behavior**:
- Used in Kubespray inventory directory name
- Used in kubeconfig context name
- Used in resource naming

### KUBE_VERSION

**Type**: String (semantic version)  
**Required**: No  
**Default**: Determined by Kubespray

Kubernetes version to install.

**Usage**:
```bash
--set KUBE_VERSION=v1.30.0
```

**Constraints**:
- Must match version in package
- Cannot upgrade to version not in package
- Must be compatible with Kubespray version

### POD_NETWORK_CIDR

**Type**: String (CIDR notation)  
**Required**: No  
**Default**: `10.233.64.0/18`

Pod network CIDR range.

**Usage**:
```bash
--set POD_NETWORK_CIDR=10.233.64.0/18
```

**Constraints**:
- Must not overlap with node network
- Must not overlap with service network
- Must be large enough for cluster size

### SERVICE_NETWORK_CIDR

**Type**: String (CIDR notation)  
**Required**: No  
**Default**: `10.233.0.0/18`

Service network CIDR range.

**Usage**:
```bash
--set SERVICE_NETWORK_CIDR=10.233.0.0/18
```

**Constraints**:
- Must not overlap with node network
- Must not overlap with pod network

## Variable Precedence

Variables are resolved in this order (highest to lowest priority):

1. Command-line `--set` flags
2. Interactive prompts during deployment
3. Environment variables (for OpenStack credentials)
4. Default values in zarf.yaml

## Variable Validation

Zarf validates variables during deployment:

- **Type checking**: Ensures correct data type
- **Required validation**: Fails if required variable missing
- **Pattern matching**: Validates format (e.g., IP addresses)

## Configuration File

Instead of command-line flags, use a configuration file:

Create `zarf-config.yaml`:
```yaml
package:
  deploy:
    set:
      DEPLOYMENT_MODE: baremetal
      BASTION_IP: 192.168.1.100
      SSH_USER: ubuntu
      INSTALL_PATH: /opt/opencenter
      REGISTRY_PORT: 35000
      NGINX_PORT: 80
```

Deploy with config:
```bash
zarf package deploy package.tar.zst --config zarf-config.yaml
```

## Environment Variables

OpenStack credentials can be sourced from environment:

```bash
export OS_AUTH_URL=https://openstack.example.com:5000/v3
export OS_PROJECT_NAME=kubernetes-prod
export OS_USERNAME=k8s-deployer
export OS_PASSWORD=secret-password

zarf package deploy package.tar.zst --set DEPLOYMENT_MODE=openstack
```

## Examples

### Bare-Metal Deployment

```bash
zarf package deploy zarf-package-*.tar.zst \
  --set DEPLOYMENT_MODE=baremetal \
  --set BASTION_IP=192.168.1.100 \
  --set SSH_USER=deployer \
  --confirm
```

### OpenStack Deployment

```bash
zarf package deploy zarf-package-*.tar.zst \
  --set DEPLOYMENT_MODE=openstack \
  --set BASTION_IP=10.0.0.10 \
  --set SSH_USER=ubuntu \
  --set OS_AUTH_URL=https://openstack.example.com:5000/v3 \
  --set OS_PROJECT_NAME=k8s-prod \
  --set OS_USERNAME=deployer \
  --set OS_PASSWORD=secret \
  --confirm
```

### Custom Ports

```bash
zarf package deploy zarf-package-*.tar.zst \
  --set BASTION_IP=192.168.1.100 \
  --set REGISTRY_PORT=5000 \
  --set NGINX_PORT=8080 \
  --confirm
```

### Custom Install Path

```bash
zarf package deploy zarf-package-*.tar.zst \
  --set BASTION_IP=192.168.1.100 \
  --set INSTALL_PATH=/data/kubernetes \
  --confirm
```

## Troubleshooting

### Variable Not Substituted

**Symptom**: Variable appears as `###ZARF_VAR_NAME###` in deployed files

**Cause**: Variable not set during deployment

**Solution**: Provide variable via `--set` flag or interactive prompt

### Invalid Variable Value

**Symptom**: Deployment fails with validation error

**Cause**: Variable value doesn't match expected format

**Solution**: Check variable type and constraints in this reference

### Missing Required Variable

**Symptom**: Deployment fails with "required variable not set"

**Cause**: Required variable not provided

**Solution**: Provide variable via `--set` flag

## Variable Reference Table

| Variable | Type | Required | Default | Description |
|:---------|:-----|:---------|:--------|:------------|
| DEPLOYMENT_MODE | enum | No | baremetal | Infrastructure provisioning mode |
| BASTION_IP | IP address | Yes | - | Bastion host IP address |
| SSH_USER | string | No | deployer | SSH username for nodes |
| INSTALL_PATH | path | No | /opt/opencenter | Installation directory |
| REGISTRY_PORT | integer | No | 35000 | Container registry port |
| NGINX_PORT | integer | No | 80 | File server port |
| OS_AUTH_URL | URL | Yes* | - | OpenStack auth endpoint |
| OS_PROJECT_NAME | string | Yes* | - | OpenStack project name |
| OS_USERNAME | string | Yes* | - | OpenStack username |
| OS_PASSWORD | string | Yes* | - | OpenStack password |
| OS_REGION | string | No | RegionOne | OpenStack region |
| CLUSTER_NAME | string | No | mycluster | Cluster name |
| KUBE_VERSION | version | No | auto | Kubernetes version |
| POD_NETWORK_CIDR | CIDR | No | 10.233.64.0/18 | Pod network range |
| SERVICE_NETWORK_CIDR | CIDR | No | 10.233.0.0/18 | Service network range |

\* Required only when DEPLOYMENT_MODE=openstack

## See Also

- Build Runbook: `docs/build-runbook.md`
- Deployment Runbook (Bare-Metal): `docs/deployment-runbook-baremetal.md`
- Deployment Runbook (OpenStack): `docs/deployment-runbook-openstack.md`
- Troubleshooting Guide: `docs/troubleshooting-guide.md`
