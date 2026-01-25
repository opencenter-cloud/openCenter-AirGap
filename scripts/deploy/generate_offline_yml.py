#!/usr/bin/env python3
"""
Generate Kubespray offline.yml configuration from template.

This script creates the offline.yml file that configures Kubespray to use
the bastion host as the source for all container images, binaries, and packages.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any


def generate_offline_yml(bastion_ip: str, registry_port: int = 35000, nginx_port: int = 80) -> str:
    """
    Generate offline.yml content with bastion IP substituted.
    
    Args:
        bastion_ip: IP address of the bastion host
        registry_port: Port for the container registry (default: 35000)
        nginx_port: Port for the nginx file server (default: 80)
    
    Returns:
        String content of the offline.yml file
    """
    
    # Build the configuration URLs
    registry_host = f"{bastion_ip}:{registry_port}"
    http_server = f"http://{bastion_ip}" if nginx_port == 80 else f"http://{bastion_ip}:{nginx_port}"
    
    offline_yml = f"""---
## Global Offline settings
### Private Container Image Registry
registry_host: "{registry_host}"
files_repo: "{http_server}/files"

### Ubuntu repository
ubuntu_repo: "{http_server}/debs"

## Container Registry overrides
kube_image_repo: "{{{{ registry_host }}}}"
gcr_image_repo: "{{{{ registry_host }}}}"
github_image_repo: "{{{{ registry_host }}}}"
docker_image_repo: "{{{{ registry_host }}}}"
quay_image_repo: "{{{{ registry_host }}}}"

## Containerd registry configuration
containerd_registries_mirrors:
  - prefix: "{{{{ registry_host }}}}"
    mirrors:
      - host: "http://{{{{ registry_host }}}}"
        capabilities: ["pull", "resolve"]
        skip_verify: true
  - prefix: "registry.k8s.io"
    mirrors:
      - host: "http://{{{{ registry_host }}}}"
        capabilities: ["pull", "resolve"]
        skip_verify: true
  - prefix: "docker.io"
    mirrors:
      - host: "http://{{{{ registry_host }}}}"
        capabilities: ["pull", "resolve"]
        skip_verify: true
  - prefix: "gcr.io"
    mirrors:
      - host: "http://{{{{ registry_host }}}}"
        capabilities: ["pull", "resolve"]
        skip_verify: true
  - prefix: "ghcr.io"
    mirrors:
      - host: "http://{{{{ registry_host }}}}"
        capabilities: ["pull", "resolve"]
        skip_verify: true
  - prefix: "quay.io"
    mirrors:
      - host: "http://{{{{ registry_host }}}}"
        capabilities: ["pull", "resolve"]
        skip_verify: true

## Kubernetes components
kubeadm_download_url: "{{{{ files_repo }}}}/kubernetes/v{{{{ kube_version }}}}/kubeadm"
kubectl_download_url: "{{{{ files_repo }}}}/kubernetes/v{{{{ kube_version }}}}/kubectl"
kubelet_download_url: "{{{{ files_repo }}}}/kubernetes/v{{{{ kube_version }}}}/kubelet"

## CNI Plugins
cni_download_url: "{{{{ files_repo }}}}/cni/cni-plugins-linux-{{{{ image_arch }}}}-v{{{{ cni_version }}}}.tgz"

## cri-tools
crictl_download_url: "{{{{ files_repo }}}}/cri-tools/crictl-v{{{{ crictl_version }}}}-{{{{ ansible_system | lower }}}}-{{{{ image_arch }}}}.tar.gz"

## etcd
etcd_download_url: "{{{{ files_repo }}}}/etcd/etcd-v{{{{ etcd_version }}}}-linux-{{{{ image_arch }}}}.tar.gz"

## Calico
calicoctl_download_url: "{{{{ files_repo }}}}/calico/calicoctl-linux-{{{{ image_arch }}}}"
calico_crds_download_url: "{{{{ files_repo }}}}/calico/calico-v{{{{ calico_version }}}}.tar.gz"

## Cilium
ciliumcli_download_url: "{{{{ files_repo }}}}/cilium/cilium-linux-{{{{ image_arch }}}}.tar.gz"

## Helm
helm_download_url: "{{{{ files_repo }}}}/helm/helm-v{{{{ helm_version }}}}-linux-{{{{ image_arch }}}}.tar.gz"

## crun
crun_download_url: "{{{{ files_repo }}}}/crun/crun-{{{{ crun_version }}}}-linux-{{{{ image_arch }}}}"

## kata-containers
kata_containers_download_url: "{{{{ files_repo }}}}/kata-containers/kata-static-{{{{ kata_containers_version }}}}-{{{{ image_arch }}}}.tar.xz"

## cri-dockerd
cri_dockerd_download_url: "{{{{ files_repo }}}}/cri-dockerd/cri-dockerd-{{{{ cri_dockerd_version }}}}.{{{{ image_arch }}}}.tgz"

## runc
runc_download_url: "{{{{ files_repo }}}}/runc/runc.{{{{ image_arch }}}}"

## cri-o
crio_download_url: "{{{{ files_repo }}}}/cri-o/cri-o.{{{{ image_arch }}}}.v{{{{ crio_version }}}}.tar.gz"
skopeo_download_url: "{{{{ files_repo }}}}/skopeo/skopeo-linux-{{{{ image_arch }}}}"

## containerd
containerd_download_url: "{{{{ files_repo }}}}/containerd/containerd-{{{{ containerd_version }}}}-linux-{{{{ image_arch }}}}.tar.gz"
nerdctl_download_url: "{{{{ files_repo }}}}/nerdctl/nerdctl-{{{{ nerdctl_version }}}}-{{{{ ansible_system | lower }}}}-{{{{ image_arch }}}}.tar.gz"

## gvisor
gvisor_runsc_download_url: "{{{{ files_repo }}}}/gvisor/runsc"
gvisor_containerd_shim_runsc_download_url: "{{{{ files_repo }}}}/gvisor/containerd-shim-runsc-v1"

## Download configuration
download_run_once: true
download_localhost: false
"""
    
    return offline_yml


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate Kubespray offline.yml configuration"
    )
    parser.add_argument(
        "--bastion-ip",
        required=True,
        help="IP address of the bastion host"
    )
    parser.add_argument(
        "--registry-port",
        type=int,
        default=35000,
        help="Port for the container registry (default: 35000)"
    )
    parser.add_argument(
        "--nginx-port",
        type=int,
        default=80,
        help="Port for the nginx file server (default: 80)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: stdout)"
    )
    
    args = parser.parse_args()
    
    # Generate the offline.yml content
    offline_yml = generate_offline_yml(
        bastion_ip=args.bastion_ip,
        registry_port=args.registry_port,
        nginx_port=args.nginx_port
    )
    
    # Write to file or stdout
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(offline_yml)
        print(f"Generated offline.yml at: {args.output}", file=sys.stderr)
    else:
        print(offline_yml)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
