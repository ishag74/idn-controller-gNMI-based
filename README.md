# Intent Driven Network Automation Controller

This project implements a Kubernetes operator to declaratively manage network services on Nokia SR OS routers using the gNMI protocol. It brings cloud-native automation principles to network infrastructure, enabling you to manage network configurations the same way you manage Kubernetes applications.

## Overview

The controller watches for `NetworkSlice` custom resources within a Kubernetes cluster. Each `NetworkSlice` resource defines a desired network service (such as VPLS, VPRN, or ePipe). The controller translates these definitions into gNMI commands to configure the specified routers.

It operates on a continuous reconciliation loop, ensuring that the live network configuration on the routers always matches the state defined in the `NetworkSlice` resources.

## Features

- **Declarative Configuration**: Define complex network services using simple YAML manifests.
- **Service Provisioning**: Supports VPLS, VPRN, and ePipe services on Nokia SR OS.
- **Drift Detection**: Periodically checks for any configuration drift on the network devices.
- **Self-Healing**: Automatically re-applies the correct configuration if drift is detected.
- **Status Reporting**: Updates the `NetworkSlice` resource with the current provisioning and operational status.
- **Secure Credential Management**: Integrates with Kubernetes Secrets to avoid hardcoding device credentials.

## Prerequisites

- A running Kubernetes cluster.
- `kubectl` installed and configured to communicate with your cluster.
- Access to one or more Nokia SR OS routers that are reachable from the cluster and have gNMI enabled.
- Enable YANG Model on the router

## Deployment Guide

Follow these steps to deploy the controller to your Kubernetes cluster. All commands should be run from the root of this project directory.

### 1. Create the Kubernetes Secret

First, you must create a secret to hold the credentials for your routers.

1.  **Edit the manifest**: Open the `router-credentials.yaml` file.
2.  **Update credentials**: Replace the placeholder values (`your_admin_user`, `your_admin_password`) with the actual login details for your routers. Add or remove router sections as needed.
3.  **Apply the secret**:
    ```bash
    kubectl apply -f router-credentials.yaml
    ```

### 2. Deploy the Controller and Custom Resources

Apply the remaining manifests to set up the Custom Resource Definition (CRD), Role-Based Access Control (RBAC), and the controller deployment itself.

```bash
# Apply the Custom Resource Definition (CRD) for NetworkSlice
kubectl apply -f controler-crd.yaml

# Apply the RBAC roles and bindings required by the controller
kubectl apply -f rback.yaml

# Deploy the controller
kubectl apply -f controller-deploy.yaml
```

### 3. Verify the Deployment

Check that the controller pod is running in the `kube-system` namespace.

```bash
kubectl get pods -n kube-system -l app=multi-service-controller
```

You should see a pod with a status of `Running`.

## Usage: Provisioning a Network Service

To provision a network service, you create a `NetworkSlice` manifest and apply it to the cluster.

### Example: Creating a VPLS Service

Here is an example manifest for a VPLS service.

1.  Create a file named `my-vpls-slice.yaml`:
    ```yaml
    apiVersion: network.automation.io/v1
    kind: NetworkSlice
    metadata:
      name: vpls-finance-department
      namespace: default # Or any namespace you prefer
      labels:
        app: network-automation
    spec:
      serviceName: "VPLS-Finance"
      serviceType: VPLS
      serviceId: 7001
      description: "VPLS for the finance department"
      customer: 100
      adminState: "enable"
      priorityClass: "High"
      bandwidthGuarantee: "500Mbps"
      endpoints:
        - routerName: "SR1" # Must match a name in your router-credentials secret
          interfaceName: "1/1/c1/1" # Must match your port naming
          vlanID: 701
          sdpId: 7001
        - routerName: "SR2" # Must match a name in your router-credentials secret
          interfaceName: "1/1/c2/1"
          vlanID: 702
          sdpId: 7002
    ```

2.  Apply the manifest to your cluster:
    ```bash
    kubectl apply -f my-vpls-slice.yaml
    ```

### Checking the Status

The controller will now attempt to provision the service. You can check its progress by inspecting the `NetworkSlice` resource.

```bash
kubectl get networkslice vpls-finance-department -o yaml
```
or 
```bash
kubectl get nets
```

Look at the `status` section at the bottom of the output. It will contain information about the provisioning status, operational status, and any errors.

## Building the Docker Image from Source

If you make changes to the controller code, you can build and push your own Docker image.

1.  Build the image:
    ```bash
    docker build -t your-docker-repo/idn-gnmi:latest .
    ```

2.  Push the image to your registry:
    ```bash
    docker push your-docker-repo/idn-gnmi:latest
    ```

3.  Update `controller-deploy.yaml` to use your new image name before deploying.
