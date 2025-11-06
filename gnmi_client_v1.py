import json
import os
from typing import Dict, Any, List
from pygnmi.client import gNMIclient
import logging

class gNMIClient:
    """
    A gNMI client for Nokia SR OS devices.
    """

    def __init__(self, router_name: str, endpoint_spec: Dict[str, Any], slice_spec: Dict[str, Any], logger: logging.Logger):
        self.router_name = router_name
        self.endpoint_spec = endpoint_spec
        self.slice_spec = slice_spec
        self.logger = logger
        self.customer_id = str(slice_spec.get('customer', 1))
        self.endpoint_name = endpoint_spec.get('interfaceName', 'N/A')
        self.service_type = slice_spec.get('serviceType')
        self.service_id = slice_spec.get('serviceId', 'N/A')
        self.service_name = slice_spec.get('serviceName', f"{self.service_type}_{self.service_id}")
        self.creds = self._get_creds_from_env(router_name)
        self.description = slice_spec.get('description', f"Service {self.service_type} {self.service_id}")
        
    

        if not self.service_type:
            self.logger.warning("Service type is missing in the NetworkSlice spec.")

    def _get_creds_from_env(self, router_name: str) -> Dict[str, Any]:
        """
        Retrieves credentials for a given router from environment variables.
        """
        creds = {
            "host": os.getenv(f"{router_name}_HOST"),
            "port": int(os.getenv(f"{router_name}_PORT", 57400)),
            "user": os.getenv(f"{router_name}_USER"),
            "pass": os.getenv(f"{router_name}_PASS"),
        }
        if not all(creds.values()):
            self.logger.error(f"Missing one or more environment variables for {router_name}. "
                              f"Required: {router_name}_HOST, {router_name}_USER, {router_name}_PASS.")
            raise ValueError(f"Missing credentials for {router_name}")
        return creds
    
    def _connect(self) -> gNMIclient:
        """
        Establishes a gNMI connection to the router.
        """
        host = (self.creds.get('host'), self.creds.get('port'))
        username=self.creds.get('user')
        password=self.creds.get('pass')

        try:
            self.logger.info(f"Connecting to gNMI target {self.router_name} at {host[0]}:{host[1]}...")

            client = gNMIclient(target=host,
                                  username=username,
                                  password=password,
                                  insecure=True)
            return client
        except Exception as e:
            self.logger.error(f"Failed to connect to gNMI target {self.router_name}: {e}")
            raise

    def _get_base_service_payload(self) -> Dict[str, Any]:
        """
        Builds the common structured JSON payload for any service.
        """
        return {
            "admin-state": f"{self.slice_spec.get('adminState', 'enable')}",
            "description": self.description,
            "customer": self.customer_id,
            "service-id": self.service_id,
        }

    def _get_service_update_path(self, service_type: str) -> str:
        """
        Generates the gNMI update path for a given service type.
        """
        return f"/configure/service/{service_type.lower()}[service-name={self.service_name}]"

    def _get_vpls_payload(self) -> Dict[str, Any]:
        """
        Builds the structured JSON payload for a VPLS service.
        """
        payload_data = self._get_base_service_payload()
        sdp_type = 'mesh-sdp' if self.slice_spec.get('vplsType', 'mesh-sdp') == 'mesh-sdp' else 'spoke-sdp'
        
        payload_data.update({
            sdp_type: [{
                "sdp-bind-id": f"{self.endpoint_spec.get('sdpId', 1000)}:{self.service_id}"
            }],
            "sap": [{
                "sap-id": f"{self.endpoint_spec.get('interfaceName')}:{self.endpoint_spec.get('vlanID')}",
                "admin-state": "enable"
            }]
        })
        
        update_path = self._get_service_update_path('VPLS')
        
        updates = [(update_path, payload_data)]
        
        return updates

    def _get_vprn_payload(self) -> Dict[str, Any]:
        """
        Builds the structured JSON payload for a VPRN service.
        """
        payload_data = self._get_base_service_payload()
        interface_name = self.endpoint_spec.get('interfaceName')
        vlan_id = self.endpoint_spec.get('vlanID')
        ip_address = self.endpoint_spec.get('ipAddress', '10.0.0.1/30')
        
        payload_data.update({
            "router-id": self.slice_spec.get('routerId'),
            "interface": [{
                "interface-name": f"{interface_name}{vlan_id}",
                "ipv4": {
                    "primary": {
                        "address": ip_address.split('/')[0],
                        "prefix-length": ip_address.split('/')[1]
                    }
                },
                "sap": [{
                    "sap-id": f"{interface_name}:{vlan_id}"
                }]
            }],
           "bgp-ipvpn": {
              "mpls": {
                "admin-state": "enable",
                "auto-bind-tunnel": {
                  "resolution": "any"
                },
                "route-distinguisher": f"64496:{self.service_id}",
                "vrf-target": {
                  "community": f"target:64496:{self.service_id}"
                }
              }
            }
        })
        
        update_path = self._get_service_update_path('VPRN')
        
        updates = [(update_path, payload_data)]
        
        return updates

    def _get_epipe_payload(self) -> Dict[str, Any]:
        """
        Builds the structured JSON payload for an EPIPE service.
        """
        payload_data = self._get_base_service_payload()
        payload_data.update({
            "sap": [
                {
                "sap-id": f"{self.endpoint_spec.get('interfaceName')}:{self.endpoint_spec.get('vlanID')}"
            }
            ],
            "spoke-sdp": {
                "sdp-bind-id": f"{self.endpoint_spec.get('sdpId', 1000)}:{self.service_id}"
            }
        })
        
        update_path = self._get_service_update_path('ePipe')
        
        updates = [(update_path, payload_data)]
        
        return updates

    def apply_config(self) -> None:
        """
        Applies the required configuration using gNMI.
        """

        updates = []
        if self.service_type == 'VPLS':
            updates = self._get_vpls_payload()
        elif self.service_type == 'VPRN':
            updates = self._get_vprn_payload()
        elif self.service_type == 'ePipe':
            updates = self._get_epipe_payload()
        else:
            raise NotImplementedError(f"Unsupported service type: {self.service_type}")

        with self._connect() as client:
            self.logger.info(f"🕖 Attempting gNMI Set Update on {self.router_name}...")
            response = client.set(update=updates)
            if "error" not in response:
                self.logger.info("✅ gNMI Set Update successful.")
            else:
                self.logger.error(f"❌ gNMI Set Update failed: {response}")
                raise Exception(f"❌ gNMI Set RPC failed to push config to {self.router_name}")

    def delete_config(self) -> None:
        """
        Deletes the service configuration using gNMI.
        """
        with self._connect() as client:
            delete_path = f"/configure/service/{self.service_type.lower()}[service-name={self.service_name}]"
            
            deletes = [delete_path]

            self.logger.warning(f"Deleting {self.service_type} ID:{self.service_id} on {self.router_name}...")

            response = client.set(delete=deletes)

            if "error" not in response:
                self.logger.info("✅ gNMI Set Delete successful.")
            else:
                self.logger.error(f"❌ gNMI Set Delete failed: {response}")
                raise Exception(f"❌ gNMI Set RPC failed to delete config on {self.router_name}")

    def get_config(self) -> str:
        """
        Retrieves the service configuration using gNMI.
        """
        with self._connect() as client:
            path = f"/configure/service/{self.service_type.lower()}[service-name={self.service_name}]"
            
            self.logger.info(f"🕗 Retrieving config for service {self.service_id} from {self.router_name}...")
            response = client.get(path=[path], encoding='JSON_IETF')
            if (response['notification'][0] and
                response['notification'][0]['update'][0]):
                
                return response['notification'][0]['update'][0]['val']
            else:
                self.logger.warning(f"⛔ No configuration found for service {self.service_id} on {self.router_name}.")
                return "{}"

    def check_for_drift(self, desired_spec: Dict[str, Any], observed_config: str) -> bool:
        """
        Compares the desired state (CRD spec) against the observed state (gNMI output).
        """
        self.logger.debug(f"🔄 Comparing desired vs observed state for {self.service_type}...")

        """"  
        try:
            observed_json = json.loads(observed_config)
        except json.JSONDecodeError:
            self.logger.warning(f"⛔ Could not decode observed config for service ID {self.service_id}.")
            return True
        """
        drift_detected = False
        
        # Check Description
        desired_description = self.description
        observed_description = observed_config.get("nokia-conf:description")
        if observed_description != desired_description:
            self.logger.warning(f"❌ Drift detected: Description mismatch for service ID {self.service_id}. Desired: '{desired_description}', Observed: '{observed_description}'")
            drift_detected = True
        
        # Check Admin State
        desired_admin_state = f"{self.slice_spec.get('adminState', 'enable')}"
        observed_admin_state = observed_config.get("nokia-conf:admin-state")
        if observed_admin_state != desired_admin_state:
            self.logger.warning(f"❌ Drift detected: Admin State mismatch for service ID {self.service_id}. Desired: '{desired_admin_state}', Observed: '{observed_admin_state}'")
            drift_detected = True

        # Check SAP
        desired_sap = f"{self.endpoint_spec.get('interfaceName')}:{self.endpoint_spec.get('vlanID')}"
        observed_saps = observed_config.get("nokia-conf:sap", [])
        
        sap_found = False
        for sap in observed_saps:
            if sap.get("sap-id") == desired_sap:
                sap_found = True
                break
        
        if not sap_found:
            self.logger.warning(f"❌ Drift detected: SAP mismatch for service ID {self.service_id}. Desired SAP not found: '{desired_sap}'")
            drift_detected = True
            
        return drift_detected

    def get_operational_status(self) -> str:
        """
        Retrieves the operational status of the service from the network device.
        Returns "UP", "DOWN", or "UNKNOWN".
        """
        with self._connect() as client:

            path = f"state/service/{self.service_type}[service-name={self.service_name}]/oper-state"
            
            values_key = f"state/service/{self.service_type.lower()}/oper-state"
            
            self.logger.info(f"Retrieving operational status for service {self.service_id} from {self.router_name}...")
            response = client.get(path=[path], encoding='JSON_IETF')
            
            try:
                oper_state = response["notification"][0]["update"][0]["val"]["nokia-state:oper-state"]
                return oper_state.upper()
            except (IndexError, KeyError):
                self.logger.warning(f"❌ Could not determine operational status for service {self.service_id} on {self.router_name}.")
                return "UNKNOWN"
