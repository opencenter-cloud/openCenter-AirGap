# Product Overview

openCenter AirGap is a turnkey solution for deploying High Availability Kubernetes clusters in completely air-gapped (disconnected) environments.

## Core Purpose

Deploy production-grade Kubernetes infrastructure without internet connectivity by packaging all dependencies into a single cryptographically verifiable artifact.

## Key Innovation

"Disconnected-First" design philosophy: internet isolation is the baseline constraint, not an exception. A single Zarf package contains everything needed to provision infrastructure, bootstrap Kubernetes, and deploy core platform services.

## Target Users

- Platform Engineers: Build and maintain air-gap artifacts
- Field Operators: Deploy clusters in disconnected environments
- Security Officers: Validate SBOM and artifact integrity
- Platform Architects: Design standard operating environments for edge sites

## Deployment Targets

- **Primary**: Bare-metal or pre-provisioned hardware with Ubuntu 24.04
- **Secondary**: OpenStack VM provisioning via Terraform

## Core Components

- **Kubespray**: Kubernetes cluster bootstrapping
- **Zarf**: Packaging and delivery framework
- **Terraform**: Infrastructure provisioning (OpenStack only)
- **FluxCD + Gitea**: In-cluster GitOps
- **Core Services**: cert-manager, ingress-nginx, Keycloak, kube-prometheus-stack

## Three-Zone Architecture

1. **Zone A (Factory)**: Connected build environment - download and package all dependencies
2. **Zone B (Airlock)**: Single artifact transport via secure media
3. **Zone C (Field)**: Disconnected deployment - bastion serves as local registry/repository
