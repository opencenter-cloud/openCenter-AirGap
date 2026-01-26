---
type: reference
audience: field-operator, platform-engineer
version: 1.0.0
last_updated: 2026-01-25
doc_type: reference
---

# Service Endpoints Reference

Network endpoints for openCenter services.

## Bastion Services

| Service | Port | Protocol | Endpoint | Purpose |
|---------|------|----------|----------|---------|
| Nginx | 80 | HTTP | http://bastion/files/ | Binary files |
| Nginx | 80 | HTTP | http://bastion/debs/ | APT repository |
| Nginx | 80 | HTTP | http://bastion/pypi/ | PyPI mirror |
| Registry | 35000 | HTTP | http://bastion:35000/v2/_catalog | Container registry |

### Nginx Endpoints

**Binary files**:
```
http://bastion/files/kubernetes/v1.30.0/kubelet
http://bastion/files/kubernetes/v1.30.0/kubectl
http://bastion/files/kubernetes/v1.30.0/kubeadm
http://bastion/files/runc/v1.3.4/runc.amd64
http://bastion/files/containerd-2.1.5-linux-amd64.tar.gz
```

**APT repository**:
```
http://bastion/debs/local/Packages.gz
http://bastion/debs/local/Release
```

**PyPI mirror**:
```
http://bastion/pypi/simple/
http://bastion/pypi/ansible/
http://bastion/pypi/jinja2/
```

### Registry Endpoints

**Catalog**:
```
GET http://bastion:35000/v2/_catalog
```

**Image tags**:
```
GET http://bastion:35000/v2/<image>/tags/list
```

**Image manifest**:
```
GET http://bastion:35000/v2/<image>/manifests/<tag>
```

## Kubernetes API

| Service | Port | Protocol | Endpoint | Purpose |
|---------|------|----------|----------|---------|
| API Server | 6443 | HTTPS | https://control-plane:6443 | Kubernetes API |
| Kubelet | 10250 | HTTPS | https://node:10250 | Node API |
| Kubelet | 10255 | HTTP | http://node:10255 | Read-only API |

### API Server

**Health**:
```
GET https://control-plane:6443/healthz
GET https://control-plane:6443/readyz
GET https://control-plane:6443/livez
```

**Version**:
```
GET https://control-plane:6443/version
```

## Core Services

| Service | Namespace | Port | Protocol | Endpoint | Purpose |
|---------|-----------|------|----------|----------|---------|
| CoreDNS | kube-system | 53 | UDP/TCP | 10.233.0.3 | DNS |
| Metrics Server | kube-system | 443 | HTTPS | metrics-server.kube-system | Metrics API |

### CoreDNS

**Service IP**: `10.233.0.3` (default)

**Cluster domain**: `cluster.local`

**Resolution**:
```
<service>.<namespace>.svc.cluster.local
```

## Platform Services

| Service | Namespace | Type | Port | Purpose |
|---------|-----------|------|------|---------|
| Gitea | gitea | ClusterIP | 3000 | Git server |
| Gitea SSH | gitea | NodePort | 30022 | Git SSH |
| Grafana | monitoring | ClusterIP | 80 | Monitoring UI |
| Prometheus | monitoring | ClusterIP | 9090 | Metrics |
| Alertmanager | monitoring | ClusterIP | 9093 | Alerts |
| Keycloak | keycloak | ClusterIP | 8080 | Identity |

### Gitea

**HTTP**:
```
http://gitea.gitea.svc.cluster.local:3000
```

**SSH**:
```
ssh://git@<node-ip>:30022
```

**Ingress** (if configured):
```
https://gitea.example.com
```

### Grafana

**Service**:
```
http://grafana.monitoring.svc.cluster.local:80
```

**Port-forward**:
```bash
kubectl port-forward -n monitoring svc/grafana 3000:80
# Access: http://localhost:3000
```

**Ingress** (if configured):
```
https://grafana.example.com
```

### Prometheus

**Service**:
```
http://prometheus-operated.monitoring.svc.cluster.local:9090
```

**Port-forward**:
```bash
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090
# Access: http://localhost:9090
```

### Keycloak

**Service**:
```
http://keycloak.keycloak.svc.cluster.local:8080
```

**Admin console**:
```
http://keycloak.keycloak.svc.cluster.local:8080/admin
```

## Ingress

| Service | Namespace | Port | Protocol | Purpose |
|---------|-----------|------|----------|---------|
| Ingress NGINX | ingress-nginx | 80 | HTTP | HTTP ingress |
| Ingress NGINX | ingress-nginx | 443 | HTTPS | HTTPS ingress |

### Ingress Controller

**HTTP**:
```
http://<node-ip>:80
```

**HTTPS**:
```
https://<node-ip>:443
```

**Admission webhook**:
```
https://ingress-nginx-controller-admission.ingress-nginx.svc.cluster.local:443
```

## FluxCD

| Service | Namespace | Port | Purpose |
|---------|-----------|------|---------|
| source-controller | flux-system | 9090 | Metrics |
| kustomize-controller | flux-system | 9090 | Metrics |
| helm-controller | flux-system | 9090 | Metrics |
| notification-controller | flux-system | 9090 | Metrics |

### Webhook Receiver

**Service**:
```
http://webhook-receiver.flux-system.svc.cluster.local:80
```

## Network Policies

Default policies allow:
- Intra-namespace communication
- DNS queries to kube-system
- Ingress from ingress-nginx
- Metrics scraping from monitoring

Blocked by default:
- Cross-namespace communication (except allowed)
- External egress (air-gap)

## Firewall Requirements

### Bastion

**Inbound**:
- 22/tcp (SSH)
- 80/tcp (Nginx)
- 35000/tcp (Registry)

**Outbound**:
- 22/tcp to nodes (SSH)

### Control Plane Nodes

**Inbound**:
- 22/tcp (SSH)
- 6443/tcp (API server)
- 2379-2380/tcp (etcd)
- 10250/tcp (Kubelet)
- 10257/tcp (kube-controller-manager)
- 10259/tcp (kube-scheduler)

**Outbound**:
- 80/tcp to bastion (Nginx)
- 35000/tcp to bastion (Registry)
- 6443/tcp to other control planes (API)
- 2379-2380/tcp to other control planes (etcd)

### Worker Nodes

**Inbound**:
- 22/tcp (SSH)
- 10250/tcp (Kubelet)
- 30000-32767/tcp (NodePort services)

**Outbound**:
- 80/tcp to bastion (Nginx)
- 35000/tcp to bastion (Registry)
- 6443/tcp to control planes (API)

## Service Discovery

### DNS

Services resolve via CoreDNS:
```
<service>.<namespace>.svc.cluster.local
```

### Environment Variables

Kubernetes injects service endpoints:
```
<SERVICE>_SERVICE_HOST
<SERVICE>_SERVICE_PORT
```

### Endpoints API

```bash
kubectl get endpoints -n <namespace>
```

## Health Checks

### Bastion

```bash
curl http://localhost/files/
curl http://localhost:35000/v2/_catalog
```

### Kubernetes

```bash
kubectl get --raw /healthz
kubectl get --raw /readyz
```

### Services

```bash
kubectl get pods -A
kubectl get svc -A
kubectl get endpoints -A
```

## Port Conflicts

Avoid these ports on bastion:
- 80 (Nginx)
- 35000 (Registry)
- 6443 (if bastion is also a node)

Avoid these ports on nodes:
- 6443 (API server)
- 2379-2380 (etcd)
- 10250 (Kubelet)
- 10257 (kube-controller-manager)
- 10259 (kube-scheduler)
- 30000-32767 (NodePort range)

## Troubleshooting

**Service not accessible**:
```bash
kubectl get svc -n <namespace>
kubectl get endpoints -n <namespace>
kubectl describe svc <service> -n <namespace>
```

**DNS not resolving**:
```bash
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup <service>.<namespace>
```

**Port not listening**:
```bash
ssh deployer@<node-ip> "netstat -tlnp | grep <port>"
```
