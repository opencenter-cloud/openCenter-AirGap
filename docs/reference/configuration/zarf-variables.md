---
type: reference
audience: platform-engineer, field-operator
version: 1.0.0
last_updated: 2026-01-25
doc_type: reference
---

# Zarf Variables Reference

Runtime configuration variables for openCenter deployment.

## Syntax

Variables use format: `###ZARF_VAR_NAME###`

Set during deployment:
```bash
zarf package deploy package.tar.zst --set VAR=value
```

## Core Variables

### DEPLOYMENT_MODE

- **Type**: enum
- **Required**: No
- **Default**: `baremetal`
- **Values**: `baremetal`, `openstack`

Infrastructure provisioning method.

```bash
--set DEPLOYMENT_MODE=baremetal
--set DEPLOYMENT_MODE=openstack
```

### BASTION_IP

- **Type**: IPv4 address
- **Required**: Yes
- **Default**: None

Bastion host IP address.

```bash
--set BASTION_IP=192.168.1.100
```

Nodes connect to `BASTION_IP:35000` (registry) and `BASTION_IP:80` (files).

### SSH_USER

- **Type**: string
- **Required**: No
- **Default**: `deployer`

SSH username for node access.

```bash
--set SSH_USER=ubuntu
```

User must have sudo privileges and SSH key authentication.

### INSTALL_PATH

- **Type**: absolute path
- **Required**: No
- **Default**: `/opt/opencenter`

Installation directory on bastion.

```bash
--set INSTALL_PATH=/opt/opencenter
```

Requires 100GB+ free space.

### REGISTRY_PORT

- **Type**: integer
- **Required**: No
- **Default**: `35000`

Container registry port.

```bash
--set REGISTRY_PORT=35000
```

Must be >1024 and available on bastion.

### NGINX_PORT

- **Type**: integer
- **Required**: No
- **Default**: `80`

File server port.

```bash
--set NGINX_PORT=80
```

Port 80 requires root or CAP_NET_BIND_SERVICE.

## OpenStack Variables

Required when `DEPLOYMENT_MODE=openstack`.

### OS_AUTH_URL

- **Type**: URL
- **Required**: Yes (OpenStack)
- **Default**: None

```bash
--set OS_AUTH_URL=https://openstack.example.com:5000/v3
```

### OS_PROJECT_NAME

- **Type**: string
- **Required**: Yes (OpenStack)
- **Default**: None

```bash
--set OS_PROJECT_NAME=kubernetes-prod
```

### OS_USERNAME

- **Type**: string
- **Required**: Yes (OpenStack)
- **Default**: None

```bash
--set OS_USERNAME=k8s-deployer
```

### OS_PASSWORD

- **Type**: string (sensitive)
- **Required**: Yes (OpenStack)
- **Default**: None

```bash
--set OS_PASSWORD=secret
```

Use environment variables instead of CLI for security.

### OS_REGION

- **Type**: string
- **Required**: No
- **Default**: `RegionOne`

```bash
--set OS_REGION=us-west-1
```

## Advanced Variables

### CLUSTER_NAME

- **Type**: string
- **Required**: No
- **Default**: `mycluster`

```bash
--set CLUSTER_NAME=production
```

### POD_NETWORK_CIDR

- **Type**: CIDR
- **Required**: No
- **Default**: `10.233.64.0/18`

```bash
--set POD_NETWORK_CIDR=10.233.64.0/18
```

Must not overlap with node or service networks.

### SERVICE_NETWORK_CIDR

- **Type**: CIDR
- **Required**: No
- **Default**: `10.233.0.0/18`

```bash
--set SERVICE_NETWORK_CIDR=10.233.0.0/18
```

## Configuration File

Create `zarf-config.yaml`:

```yaml
package:
  deploy:
    set:
      DEPLOYMENT_MODE: baremetal
      BASTION_IP: 192.168.1.100
      SSH_USER: ubuntu
      REGISTRY_PORT: 35000
```

Deploy:
```bash
zarf package deploy package.tar.zst --config zarf-config.yaml
```

## Environment Variables

```bash
export OS_AUTH_URL=https://openstack.example.com:5000/v3
export OS_PROJECT_NAME=kubernetes-prod
export OS_USERNAME=k8s-deployer
export OS_PASSWORD=secret

zarf package deploy package.tar.zst --set DEPLOYMENT_MODE=openstack
```

## Variable Precedence

1. CLI `--set` flags
2. Interactive prompts
3. Environment variables
4. Default values

## Examples

**Bare-metal**:
```bash
zarf package deploy zarf-package-*.tar.zst \
  --set DEPLOYMENT_MODE=baremetal \
  --set BASTION_IP=192.168.1.100 \
  --set SSH_USER=deployer \
  --confirm
```

**OpenStack**:
```bash
zarf package deploy zarf-package-*.tar.zst \
  --set DEPLOYMENT_MODE=openstack \
  --set BASTION_IP=10.0.0.10 \
  --set OS_AUTH_URL=https://openstack.example.com:5000/v3 \
  --set OS_PROJECT_NAME=k8s-prod \
  --set OS_USERNAME=deployer \
  --set OS_PASSWORD=secret \
  --confirm
```

**Custom ports**:
```bash
zarf package deploy zarf-package-*.tar.zst \
  --set BASTION_IP=192.168.1.100 \
  --set REGISTRY_PORT=5000 \
  --set NGINX_PORT=8080 \
  --confirm
```

## Variable Table

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| DEPLOYMENT_MODE | enum | No | baremetal | Provisioning mode |
| BASTION_IP | IPv4 | Yes | - | Bastion IP |
| SSH_USER | string | No | deployer | SSH username |
| INSTALL_PATH | path | No | /opt/opencenter | Install directory |
| REGISTRY_PORT | int | No | 35000 | Registry port |
| NGINX_PORT | int | No | 80 | File server port |
| OS_AUTH_URL | URL | Yes* | - | OpenStack auth |
| OS_PROJECT_NAME | string | Yes* | - | OpenStack project |
| OS_USERNAME | string | Yes* | - | OpenStack user |
| OS_PASSWORD | string | Yes* | - | OpenStack password |
| OS_REGION | string | No | RegionOne | OpenStack region |
| CLUSTER_NAME | string | No | mycluster | Cluster name |
| POD_NETWORK_CIDR | CIDR | No | 10.233.64.0/18 | Pod network |
| SERVICE_NETWORK_CIDR | CIDR | No | 10.233.0.0/18 | Service network |

\* Required when DEPLOYMENT_MODE=openstack
