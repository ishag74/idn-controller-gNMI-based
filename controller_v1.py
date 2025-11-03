import kopf
import logging
import time
from typing import Dict, Any, Tuple
# Import the client that now handles multiple service types (VPLS, VPRN, ePip)
from gnmi_client_v1 import gNMIClient

# Set up logging for the controller
log = logging.getLogger(__name__)

# --- 1. Primary Reconciliation Loop (CREATE/UPDATE) ---
@kopf.on.update('networkslices', labels={'app': 'network-automation'}, field='spec')
@kopf.on.create('networkslices', labels={'app': 'network-automation'})
def provision_or_update_slice(name: str, spec: Dict[str, Any], logger: kopf.Logger, **kwargs: Any) -> Dict[str, Any]:
    """
    Handles NetworkSlice creation and user-driven updates to the spec.
    It provisions the service and returns the initial status.
    """
    logger.info(f"Starting provisioning/update reconciliation for NetworkSlice '{name}'.")
    
    # Pre-check for required serviceType field
    service_type = spec.get('serviceType')
    if service_type not in ['VPLS', 'VPRN', 'ePipe']:
        error_message = f"Invalid or missing 'serviceType' in spec. Must be VPLS, VPRN, or ePipe. Found: {service_type}"
        logger.error(error_message)
        return {'status': {'Status': 'Error', 'Message': error_message}}
        
    provisioned_endpoints = {}
    endpoints = spec.get('endpoints', [])

    # The logic for VPLS/VPRN and ePipe is merged here, focusing on initial enforcement.

    # --- EPIPE Logic (Requires pairing) ---
    if service_type == 'ePipe':
        if len(endpoints) != 2:
            error_message = f"ePipe service requires exactly two endpoints. Found: {len(endpoints)}"
            logger.error(error_message)
            return {'status': {'Status': 'Error', 'Message': error_message}}

        endpoints_to_process = [
            {'local': endpoints[0], 'remote': endpoints[1]},
            {'local': endpoints[1], 'remote': endpoints[0]}
        ]

        for pair in endpoints_to_process:
            local_endpoint = pair['local']
            remote_endpoint = pair['remote']
            router_name = local_endpoint.get('routerName')
            
            # Pass remote_sdpId for the remote side of the ePipe
            epipe_spec = dict(spec)
            epipe_spec['remote_sdpId'] = remote_endpoint.get('sdpId')
            
            client = gNMIClient(router_name, local_endpoint, epipe_spec, logger)
            
            try:
                # Always enforce configuration on CREATE/UPDATE to match intent
                client.apply_config()
                provisioned_endpoints[router_name] = f"{service_type} Provisioned"
            except Exception as e:
                error_message = f"Error during provisioning for {service_type} on {router_name}: {e}"
                logger.error(error_message)
                provisioned_endpoints[router_name] = f"Error: {str(e)}"
                return {'status': {'Status': 'Error', 'Message': error_message, 'ProvisionedEndpoints': provisioned_endpoints}}

    # --- VPLS/VPRN Logic (Independent endpoints) ---
    else: 
        for endpoint in endpoints:
            router_name = endpoint.get('routerName')
            if not router_name: continue
                
            client = gNMIClient(router_name, endpoint, spec, logger)

            try:
                # Always enforce configuration on CREATE/UPDATE to match intent
                client.apply_config()
                provisioned_endpoints[router_name] = f"{service_type} Provisioned"

            except Exception as e:
                error_message = f"Error during provisioning for {service_type} on {router_name}: {e}"
                logger.error(error_message)
                provisioned_endpoints[router_name] = f"Error: {str(e)}"
                return {'status': {'Status': 'Error', 'Message': error_message, 'ProvisionedEndpoints': provisioned_endpoints}}


    logger.info(f"NetworkSlice '{name}' provisioning finished. Status updated to Ready.")
    
    # Kopf automatically patches the status with the returned dictionary.
    return {
        'status': {
            'Status': 'Ready',
            'ServiceType': service_type,
            'Message': f"Initial provisioning complete at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            'ProvisionedEndpoints': provisioned_endpoints
        }
    }


# --- 2. Periodic Drift Detection Check (TIMER) ---
# NOTE: This uses the injected 'patch' argument for explicit status updates.
@kopf.timer('networkslices', interval=300, labels={'app': 'network-automation'}) 
def drift_detection_check(name: str, spec: Dict[str, Any], patch: kopf.Patch, logger: kopf.Logger, **kwargs: Any):
    """
    Performs a periodic check (drift detection, operational status) without
    re-running the full provisioning logic if nothing has changed.
    """
    logger.info(f"--- Running drift detection cycle for {name} (Service: {spec.get('serviceType')}) ---")
    
    service_type = spec.get('serviceType')
    endpoints = spec.get('endpoints', [])
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. Check Sync and Enforce Drift
    provisioned_endpoints = {}
    overall_operational_status = "UP"
    
    # Use the provisioning logic to check for drift and self-heal
    for endpoint in endpoints:
        router_name = endpoint.get('routerName')
        if not router_name: continue
            
        client = gNMIClient(router_name, endpoint, spec, logger)

        try:
            # Check for drift
            observed_config = client.get_config()
            is_drift_detected = client.check_for_drift(spec, observed_config)
            
            if is_drift_detected:
                logger.warning(f"Drift detected for {service_type} on {router_name}. Enforcing config...")
                client.apply_config() # Self-heal
                provisioned_endpoints[router_name] = f"{service_type} Reconciled"
            else:
                provisioned_endpoints[router_name] = f"{service_type} InSync"

            # Check Operational Status
            op_status = client.get_operational_status()
            if op_status != "UP":
                overall_operational_status = "DOWN"

        except Exception as e:
            logger.error(f"Error during drift check for {service_type} on {router_name}: {e}")
            provisioned_endpoints[router_name] = f"Error during drift check: {str(e)}"
            # If any endpoint fails the check, mark overall status as down/error
            overall_operational_status = "ERROR"
            
    # 2. Patch the Status
    new_status = {
        'Status': 'Ready' if overall_operational_status != 'ERROR' else 'Error',
        'OperationalStatus': overall_operational_status,
        'Message': f"Periodic drift check completed. Status: {overall_operational_status} at {current_time}",
        'ProvisionedEndpoints': provisioned_endpoints
    }
    
    # Use the injected 'patch' object as a dictionary to queue the status update
    patch['status'] = new_status
    logger.info(f"Periodic status update for {name} finished. Operational Status: {overall_operational_status}.")

# --- Cleanup Handler (Finalizer Equivalent) ---
@kopf.on.delete('networkslices', optional=True)
def cleanup_network_slice(name: str, spec: Dict[str, Any], logger: kopf.Logger, **kwargs: Any) -> Tuple[bool, str]:
    """
    Handles deletion of the NetworkSlice CRD, performing necessary network cleanup.
    """
    logger.warning(f"Starting cleanup for NetworkSlice '{name}'.")
    
    service_type = spec.get('serviceType', 'Unknown')
    success = True
    
    # Iterate over endpoints for de-provisioning
    for endpoint in spec.get('endpoints', []):
        router_name = endpoint.get('routerName')
        if not router_name:
            continue
            
        logger.info(f"Attempting de-provisioning of {service_type} on router: {router_name}")
        
        try:
            # Initialize client for deletion logic
            client = gNMIClient(router_name, endpoint, spec, logger)
            client.delete_config()
            logger.info(f"Successfully cleaned up {service_type} on {router_name}")
            
        except Exception as e:
            logger.error(f"Failed to clean up {service_type} configuration on {router_name}: {e}")
            success = False
            
    if success:
        return True, f"{service_type} service successfully de-provisioned."
    else:
        return False, f"Cleanup of {service_type} completed with errors on some devices."