#!/usr/bin/env python3
"""
Generate Kubespray inventory for bare-metal deployments.

This script accepts a node list (JSON or YAML) and generates an Ansible
inventory file compatible with Kubespray, along with the offline.yml
configuration.
"""

import argparse
import json
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any


def load_node_list(input_file: Path) -> Dict[str, Any]:
    """
    Load node list from JSON or YAML file.
    
    Args:
        input_file: Path to the input file
    
    Returns:
        Dictionary containing node configuration
    
    Raises:
        ValueError: If file format is not supported or invalid
    """
    content = input_file.read_text()
    
    # Try JSON first
    if input_file.suffix.lower() == '.json':
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    # Try YAML
    elif input_file.suffix.lower() in ['.yaml', '.yml']:
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")
    
    else:
        raise ValueError(f"Unsupported file format: {input_file.suffix}")


def validate_node_list(nodes: Dict[str, Any]) -> None:
    """
    Validate the node list structure.
    
    Args:
        nodes: Dictionary containing node configuration
    
    Raises:
        ValueError: If node list is invalid
    """
    required_keys = ['control_plane', 'workers']
    for key in required_keys:
        if key not in nodes:
            raise ValueError(f"Missing required key: {key}")
        
        if not isinstance(nodes[key], list):
            raise ValueError(f"Key '{key}' must be a list")
        
        if not nodes[key]:
            raise ValueError(f"Key '{key}' cannot be empty")
    
    # Validate each node has required fields
    all_nodes = nodes['control_plane'] + nodes['workers']
    if 'etcd' in nodes:
        all_nodes.extend(nodes['etcd'])
    
    for i, node in enumerate(all_nodes):
        if not isinstance(node, dict):
            raise ValueError(f"Node {i} must be a dictionary")
        
        if 'hostname' not in node:
            raise ValueError(f"Node {i} missing 'hostname'")
        
        if 'ip' not in node:
            raise ValueError(f"Node {i} missing 'ip'")


def generate_inventory(nodes: Dict[str, Any], cluster_name: str = "mycluster") -> str:
    """
    Generate Kubespray inventory in YAML format.
    
    Args:
        nodes: Dictionary containing node configuration
        cluster_name: Name of the cluster (default: mycluster)
    
    Returns:
        String content of the inventory file
    """
    
    # Build the inventory structure
    inventory = {
        'all': {
            'hosts': {},
            'children': {
                'kube_control_plane': {
                    'hosts': {}
                },
                'kube_node': {
                    'hosts': {}
                },
                'etcd': {
                    'hosts': {}
                },
                'k8s_cluster': {
                    'children': {
                        'kube_control_plane': {},
                        'kube_node': {}
                    }
                },
                'calico_rr': {
                    'hosts': {}
                }
            }
        }
    }
    
    # Add control plane nodes
    for node in nodes['control_plane']:
        hostname = node['hostname']
        ip = node['ip']
        ansible_host = node.get('ansible_host', ip)
        ssh_port = node.get('ssh_port', 22)
        
        # Add to all hosts
        inventory['all']['hosts'][hostname] = {
            'ansible_host': ansible_host,
            'ip': ip,
            'access_ip': ip
        }
        
        if ssh_port != 22:
            inventory['all']['hosts'][hostname]['ansible_port'] = ssh_port
        
        # Add to control plane group
        inventory['all']['children']['kube_control_plane']['hosts'][hostname] = {}
        
        # Add to etcd group (control plane nodes run etcd by default)
        inventory['all']['children']['etcd']['hosts'][hostname] = {}
    
    # Add worker nodes
    for node in nodes['workers']:
        hostname = node['hostname']
        ip = node['ip']
        ansible_host = node.get('ansible_host', ip)
        ssh_port = node.get('ssh_port', 22)
        
        # Add to all hosts
        inventory['all']['hosts'][hostname] = {
            'ansible_host': ansible_host,
            'ip': ip,
            'access_ip': ip
        }
        
        if ssh_port != 22:
            inventory['all']['hosts'][hostname]['ansible_port'] = ssh_port
        
        # Add to node group
        inventory['all']['children']['kube_node']['hosts'][hostname] = {}
    
    # Add dedicated etcd nodes if specified
    if 'etcd' in nodes:
        for node in nodes['etcd']:
            hostname = node['hostname']
            ip = node['ip']
            ansible_host = node.get('ansible_host', ip)
            ssh_port = node.get('ssh_port', 22)
            
            # Add to all hosts if not already present
            if hostname not in inventory['all']['hosts']:
                inventory['all']['hosts'][hostname] = {
                    'ansible_host': ansible_host,
                    'ip': ip,
                    'access_ip': ip
                }
                
                if ssh_port != 22:
                    inventory['all']['hosts'][hostname]['ansible_port'] = ssh_port
            
            # Add to etcd group
            inventory['all']['children']['etcd']['hosts'][hostname] = {}
    
    # Convert to YAML
    return yaml.dump(inventory, default_flow_style=False, sort_keys=False)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate Kubespray inventory for bare-metal deployments"
    )
    parser.add_argument(
        "--nodes",
        type=Path,
        required=True,
        help="Path to node list file (JSON or YAML)"
    )
    parser.add_argument(
        "--bastion-ip",
        required=True,
        help="IP address of the bastion host"
    )
    parser.add_argument(
        "--cluster-name",
        default="mycluster",
        help="Name of the cluster (default: mycluster)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for inventory files"
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
    
    args = parser.parse_args()
    
    # Load and validate node list
    try:
        nodes = load_node_list(args.nodes)
        validate_node_list(nodes)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error loading node list: {e}", file=sys.stderr)
        return 1
    
    # Create output directory structure
    inventory_dir = args.output_dir / args.cluster_name
    group_vars_dir = inventory_dir / "group_vars" / "all"
    group_vars_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate inventory
    inventory_content = generate_inventory(nodes, args.cluster_name)
    inventory_file = inventory_dir / "hosts.yaml"
    inventory_file.write_text(inventory_content)
    print(f"Generated inventory at: {inventory_file}", file=sys.stderr)
    
    # Generate offline.yml
    from generate_offline_yml import generate_offline_yml
    offline_yml = generate_offline_yml(
        bastion_ip=args.bastion_ip,
        registry_port=args.registry_port,
        nginx_port=args.nginx_port
    )
    offline_file = group_vars_dir / "offline.yml"
    offline_file.write_text(offline_yml)
    print(f"Generated offline.yml at: {offline_file}", file=sys.stderr)
    
    print(f"\nInventory structure created at: {inventory_dir}", file=sys.stderr)
    print(f"  - {inventory_file.relative_to(args.output_dir)}", file=sys.stderr)
    print(f"  - {offline_file.relative_to(args.output_dir)}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
