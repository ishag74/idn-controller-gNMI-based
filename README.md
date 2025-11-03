# idn-gnmi

A Python-based gNMI client for network device automation.

## Description

This project provides a framework for interacting with network devices using the gNMI protocol. It includes a gNMI client and can be extended to create network automation workflows. The project is set up to be run as a Kubernetes operator using the `kopf` framework.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd idn-gnmi
   ```

2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

To run the main application:
```bash
python main.py
```

## Docker

To build and run the application as a Docker container:

1.  Build the Docker image:
    ```bash
    docker build -t idn-gnmi .
    ```

2.  Run the Docker container:
    ```bash
    docker run idn-gnmi
    ```

## Dependencies

The project relies on the following Python libraries:

*   `kopf`: A framework to build Kubernetes operators in Python.
*   `pygnmi`: A Python library for gNMI clients.
*   `typing`: Provides runtime support for type hints.

## Kubernetes Manifests

The following Kubernetes manifest files are included in this project:

*   `controller-crd.yaml`: Defines the Custom Resource Definition for the controller.
*   `controller-deploy.yaml`: Deployment configuration for the Kubernetes controller.
*   `epipe.yaml`: Example manifest for an ePipe resource.
*   `rback.yaml`: Role-Based Access Control (RBAC) configuration.
*   `vpls.yaml`: Example manifest for a VPLS resource.
*   `vprn.yaml`: Example manifest for a VPRN resource.
