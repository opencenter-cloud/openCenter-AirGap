# Cluster Health Verification Guide

## Overview

The cluster health verification script validates that a Kubernetes cluster is fully operational after deployment. It checks control plane components, node status, system pods, and DNS services.

## Quick Start

```bash
# Basic health check (uses ~/.kube/config)
./scripts/deploy/verify_cluster_health.sh

# Check with custom kubeconfig
./scripts/deploy/verify_cluster_health.sh --kubeconfig /path/to/kubeconfig

# Verbose output for troubleshooting
./scripts/deploy/verify_cluster_health.sh --verbose
```

## What Gets Checked

### 1. Cluster Connectivity
- API server reachability
- kubectl configuration validity
- Cluster info retrieval

### 2. Control Plane Components
- **kube-apiserver**: API server pods running
- **kube-controller-manager**: Controller manager pods running
- **kube-scheduler**: Scheduler pods running
- **etcd**: etcd pods running
- **Health endpoints**: /healthz and /readyz responding

### 3. Node Status
- All nodes in Ready state
- No pressure conditions (Memory, Disk, PID, Network)
- Node version and role information

### 4. System Pods
- All pods in kube-system namespace running
- No pods in Failed or Pending state
- Pod resource allocation

### 5. DNS Service
- CoreDNS pods running
- DNS service exists and has ClusterIP
- DNS resolution capability

## Exit Codes

- **0**: Cluster is healthy - all checks passed
- **1**: Cluster is unhealthy - one or more checks failed
- **2**: Invalid arguments or configuration error

## Usage in Scripts

```bash
#!/bin/bash

# Wait for cluster to become healthy
if ./scripts/deploy/verify_cluster_health.sh; then
    echo "Cluster is healthy, proceeding with deployment"
    # Deploy applications
else
    echo "Cluster is unhealthy, aborting"
    exit 1
fi
```

## Troubleshooting

### Cluster Unreachable

**Symptom**: "Unable to connect to cluster"

**Solutions**:
1. Verify kubeconfig path: `echo $KUBECONFIG`
2. Check API server is running: `kubectl cluster-info`
3. Verify network connectivity to control plane
4. Check firewall rules allow access to API server port (6443)

### Control Plane Components Unhealthy

**Symptom**: "kube-apiserver: 0/3 pods running"

**Solutions**:
1. Check pod logs: `kubectl logs -n kube-system kube-apiserver-<node>`
2. Check pod events: `kubectl describe pod -n kube-system kube-apiserver-<node>`
3. Verify container images are available in local registry
4. Check node resources (CPU, memory, disk)

### Nodes Not Ready

**Symptom**: "Node status: 3/6 Ready"

**Solutions**:
1. Check node conditions: `kubectl describe node <node-name>`
2. Verify kubelet is running: `systemctl status kubelet`
3. Check kubelet logs: `journalctl -u kubelet -f`
4. Verify network connectivity between nodes
5. Check containerd is running: `systemctl status containerd`

### System Pods Not Running

**Symptom**: "Found non-running pods in kube-system"

**Solutions**:
1. Check pod status: `kubectl get pods -n kube-system`
2. Check pod logs: `kubectl logs -n kube-system <pod-name>`
3. Check pod events: `kubectl describe pod -n kube-system <pod-name>`
4. Verify images can be pulled from registry
5. Check node resources and scheduling constraints

### DNS Service Unhealthy

**Symptom**: "CoreDNS: 0/2 pods running"

**Solutions**:
1. Check CoreDNS logs: `kubectl logs -n kube-system -l k8s-app=kube-dns`
2. Verify DNS service exists: `kubectl get svc -n kube-system kube-dns`
3. Check CoreDNS ConfigMap: `kubectl get cm -n kube-system coredns -o yaml`
4. Test DNS resolution: `kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default`

## Integration with Deployment

The health verification script is automatically called by the main deployment script:

```bash
# In scripts/deploy/deploy.sh
./scripts/deploy/deploy_kubespray.sh
./scripts/deploy/verify_cluster_health.sh

if [ $? -eq 0 ]; then
    echo "Cluster deployment successful"
else
    echo "Cluster deployment failed health check"
    exit 1
fi
```

## Monitoring and Alerting

For production environments, integrate this script with monitoring:

```bash
# Cron job for periodic health checks
*/5 * * * * /opt/opencenter/scripts/verify_cluster_health.sh || /usr/local/bin/alert-ops.sh

# Prometheus exporter
while true; do
    if ./verify_cluster_health.sh; then
        echo "cluster_health 1" | curl --data-binary @- http://pushgateway:9091/metrics/job/cluster_health
    else
        echo "cluster_health 0" | curl --data-binary @- http://pushgateway:9091/metrics/job/cluster_health
    fi
    sleep 300
done
```

## Advanced Usage

### Wait for Cluster to Become Healthy

```bash
#!/bin/bash
TIMEOUT=600
INTERVAL=30
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    if ./scripts/deploy/verify_cluster_health.sh; then
        echo "Cluster is healthy after ${ELAPSED}s"
        exit 0
    fi
    
    echo "Cluster not healthy yet, waiting ${INTERVAL}s..."
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo "Timeout waiting for cluster to become healthy"
exit 1
```

### Continuous Health Monitoring

```bash
#!/bin/bash
# Monitor cluster health continuously

while true; do
    echo "=== Health Check at $(date) ==="
    
    if ./scripts/deploy/verify_cluster_health.sh; then
        echo "Status: HEALTHY"
    else
        echo "Status: UNHEALTHY"
        # Send alert
        /usr/local/bin/send-alert.sh "Cluster health check failed"
    fi
    
    echo ""
    sleep 300  # Check every 5 minutes
done
```

### Export Health Metrics

```bash
#!/bin/bash
# Export health check results to file

OUTPUT_FILE="/var/log/cluster-health.json"

if ./scripts/deploy/verify_cluster_health.sh > /tmp/health.log 2>&1; then
    STATUS="healthy"
    EXIT_CODE=0
else
    STATUS="unhealthy"
    EXIT_CODE=1
fi

cat > "$OUTPUT_FILE" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$STATUS",
  "exit_code": $EXIT_CODE,
  "log": "$(cat /tmp/health.log | base64 -w0)"
}
EOF

echo "Health check results exported to $OUTPUT_FILE"
```

## Best Practices

1. **Run After Deployment**: Always verify cluster health immediately after deployment
2. **Periodic Checks**: Schedule regular health checks (every 5-15 minutes)
3. **Alert on Failures**: Integrate with alerting system for production clusters
4. **Verbose Mode**: Use `--verbose` when troubleshooting issues
5. **Log Results**: Capture output for audit and troubleshooting
6. **Timeout Configuration**: Adjust timeout based on cluster size and network latency
7. **Automation**: Include in CI/CD pipelines for deployment validation

## Related Documentation

- [Deployment Guide](deployment-guide.md)
- [Troubleshooting Guide](troubleshooting-guide.md)
- [Kubespray Documentation](https://kubespray.io/)
- [Kubernetes Health Checks](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

