---
type: how-to
audience: field-operator
difficulty: beginner
version: 1.0.0
last_updated: 2026-01-25
doc_type: how-to
---

# Verify Cluster Health

Check that Kubernetes cluster is fully operational after deployment.

## Quick Check

```bash
export KUBECONFIG=/opt/opencenter/kubespray-master/inventory/mycluster/artifacts/admin.conf

# Run verification script
./scripts/deploy/verify_cluster_health.sh
```

Exit code 0 = healthy, 1 = unhealthy.

## Manual Verification

### Check Nodes

```bash
kubectl get nodes
```

Expected: All nodes `Ready`, no pressure conditions.

```
NAME    STATUS   ROLES           AGE   VERSION
node1   Ready    control-plane   10m   v1.30.0
node2   Ready    control-plane   10m   v1.30.0
node3   Ready    <none>          9m    v1.30.0
```

### Check Control Plane

```bash
kubectl get pods -n kube-system -l tier=control-plane
```

Expected: All pods `Running`.

```
NAME                            READY   STATUS    RESTARTS   AGE
kube-apiserver-node1            1/1     Running   0          10m
kube-controller-manager-node1   1/1     Running   0          10m
kube-scheduler-node1            1/1     Running   0          10m
```

### Check System Pods

```bash
kubectl get pods -n kube-system
```

Expected: All pods `Running` or `Completed`, none `Failed` or `Pending`.

### Check DNS

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

Expected: CoreDNS pods running.

Test resolution:
```bash
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default
```

Expected: Resolves to service ClusterIP.

### Check Core Services

```bash
kubectl get pods -n flux-system
kubectl get pods -n gitea
kubectl get pods -n cert-manager
kubectl get pods -n ingress-nginx
kubectl get pods -n monitoring
```

Expected: All pods running.

## Troubleshooting

### Nodes Not Ready

```bash
kubectl describe node <node-name>
```

Check conditions: MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable.

**Fix**:
```bash
# Check kubelet
ssh deployer@<node-ip> "systemctl status kubelet"

# Check containerd
ssh deployer@<node-ip> "systemctl status containerd"

# Check logs
ssh deployer@<node-ip> "journalctl -u kubelet -n 50"
```

### Control Plane Pods Not Running

```bash
kubectl describe pod -n kube-system kube-apiserver-<node>
```

**Fix**:
```bash
# Check static pod manifests
ssh deployer@<node-ip> "ls -l /etc/kubernetes/manifests/"

# Check kubelet logs
ssh deployer@<node-ip> "journalctl -u kubelet | grep apiserver"
```

### DNS Not Working

```bash
kubectl logs -n kube-system -l k8s-app=kube-dns
```

**Fix**:
```bash
# Restart CoreDNS
kubectl rollout restart deployment -n kube-system coredns

# Check ConfigMap
kubectl get cm -n kube-system coredns -o yaml
```

### Image Pull Failures

```bash
kubectl describe pod <pod-name> -n <namespace>
```

Look for `ErrImagePull` or `ImagePullBackOff`.

**Fix**:
```bash
# Check registry from node
ssh deployer@<node-ip> "curl http://<bastion-ip>:35000/v2/_catalog"

# Check containerd config
ssh deployer@<node-ip> "cat /etc/containerd/config.toml | grep registry"

# Re-run offline-repo playbook
cd /opt/opencenter/kubespray-master
ansible-playbook -i inventory/mycluster/hosts.yaml ../playbook/offline-repo.yml
```

## Automated Monitoring

### Periodic Health Checks

```bash
# Cron job (every 5 minutes)
*/5 * * * * /opt/opencenter/scripts/verify_cluster_health.sh || /usr/local/bin/alert.sh
```

### Wait for Healthy

```bash
#!/bin/bash
TIMEOUT=600
INTERVAL=30
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    if ./scripts/deploy/verify_cluster_health.sh; then
        echo "Cluster healthy after ${ELAPSED}s"
        exit 0
    fi
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo "Timeout waiting for cluster"
exit 1
```

## Next Steps

- [Troubleshooting guide](../operate/troubleshoot-deployment.md)
- [Add custom services](../extend/add-custom-services.md)
