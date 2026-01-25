# Offline Repository Configuration

doc_type: how-to

## Purpose

Configure cluster nodes to use the bastion host as their package repository source. This ensures nodes can install system packages without internet access during Kubernetes deployment.

## Prerequisites

- Bastion host with offline repositories configured (nginx serving on port 80)
- Kubespray inventory generated (`hosts.yaml` and `offline.yml`)
- SSH access to all cluster nodes
- Ansible installed (available in `~/.venv/kubespray` after bastion setup)

## What Gets Configured

The offline-repo playbook configures each node with:

1. **APT offline configuration** (`/etc/apt/apt.conf.d/99offline`)
   - Disables automatic package updates
   - Configures apt to use local repository only

2. **Offline repository source** (`/etc/apt/sources.list.d/offline.list`)
   - Points to bastion's DEB repository
   - Format: `deb [trusted=yes] http://<bastion-ip>/debs/local/ ./`

3. **Backup of original sources** (`/etc/apt/sources.list.original`)
   - Original sources.list is backed up
   - Original file is removed to prevent internet access attempts

## Usage

### Automatic (Recommended)

Use the comprehensive configuration script:

```bash
/opt/opencenter/scripts/configure_nodes_offline.sh \
  --bastion-ip 192.168.1.5 \
  --inventory-path /opt/opencenter/kubespray/inventory/mycluster
```

This script:
- Validates prerequisites
- Tests node connectivity
- Runs the offline-repo playbook
- Verifies configuration on all nodes

### Manual

Run the playbook directly:

```bash
# Activate Python venv
source ~/.venv/kubespray/bin/activate

# Run playbook
ansible-playbook \
  -i /opt/opencenter/kubespray/inventory/mycluster/hosts.yaml \
  /opt/opencenter/outputs/playbook/offline-repo.yml \
  --become
```

## Verification

Check configuration on a specific node:

```bash
# Check offline.list exists
ansible -i inventory/mycluster/hosts.yaml worker-01 \
  -m shell -a "cat /etc/apt/sources.list.d/offline.list" --become

# Check apt can update from bastion
ansible -i inventory/mycluster/hosts.yaml worker-01 \
  -m shell -a "apt-get update" --become

# Verify no internet repositories
ansible -i inventory/mycluster/hosts.yaml worker-01 \
  -m shell -a "grep -r 'ubuntu.com' /etc/apt/ || echo 'No internet repos found'" --become
```

## Troubleshooting

### Playbook fails with "Connection refused"

**Cause**: Nodes cannot reach bastion nginx server.

**Fix**:
```bash
# On bastion, verify nginx is running
curl http://localhost/debs/

# Check firewall allows port 80
sudo ufw status

# Test from a node
ssh worker-01 "curl http://192.168.1.5/debs/"
```

### Playbook fails with "Permission denied"

**Cause**: SSH user lacks sudo privileges.

**Fix**:
```bash
# Add user to sudoers on each node
echo "deployer ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/deployer

# Or specify become password in Ansible
ansible-playbook ... --ask-become-pass
```

### apt-get update fails after configuration

**Cause**: Repository metadata is missing or corrupt.

**Fix**:
```bash
# On bastion, verify repository structure
ls -la /opt/opencenter/outputs/debs/local/
# Should contain: Packages.gz, Release, *.deb files

# Regenerate repository metadata if needed
cd /opt/opencenter/outputs/debs/local
dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz
```

### Some nodes show "MISSING" during verification

**Cause**: Playbook failed on specific nodes.

**Fix**:
```bash
# Check Ansible logs for errors
ansible-playbook ... -vvv

# Run playbook against failed nodes only
ansible-playbook -i inventory/mycluster/hosts.yaml \
  /opt/opencenter/outputs/playbook/offline-repo.yml \
  --become \
  --limit worker-02
```

## Next Steps

After offline repository configuration:

1. **Verify bastion services**: Ensure registry (port 35000) and nginx (port 80) are running
2. **Deploy Kubernetes**: Run Kubespray cluster.yml playbook
3. **Monitor deployment**: Check that nodes pull packages from bastion, not internet

## Files Modified

On each cluster node:
- `/etc/apt/sources.list` - Removed (backed up to `.original`)
- `/etc/apt/sources.list.d/offline.list` - Created
- `/etc/apt/apt.conf.d/99offline` - Created

## Rollback

To restore internet repository access:

```bash
ansible -i inventory/mycluster/hosts.yaml all \
  -m shell \
  -a "mv /etc/apt/sources.list.original /etc/apt/sources.list && rm /etc/apt/sources.list.d/offline.list /etc/apt/apt.conf.d/99offline" \
  --become
```
