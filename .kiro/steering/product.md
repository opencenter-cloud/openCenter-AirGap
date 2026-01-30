# Product Overview

openCenter AirGap is a turnkey solution for deploying High Availability Kubernetes clusters in completely air-gapped (disconnected) environments.

## Purpose

Package all dependencies into a single cryptographically verifiable artifact.

## Mission

Eliminate internet connectivity as a deployment constraint. A single Zarf package contains everything needed to provision infrastructure, bootstrap Kubernetes, and deploy core platform services—no external downloads required.

## Vision

"Disconnected-First" design philosophy where air-gap isolation is the baseline constraint, not an exception. Enable field operators to deploy identical, reproducible Kubernetes environments at edge sites with the same confidence as cloud deployments.

## Target Outcomes

- Platform engineers build once, deploy anywhere (bare-metal, OpenStack)
- Security officers verify SBOM and artifact integrity before deployment
- Field operators deploy without network troubleshooting or dependency hunting
- Platform architects standardize operating environments across disconnected sites

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
