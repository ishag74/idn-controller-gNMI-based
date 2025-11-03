import json
from typing import Dict, Any, List
from pygnmi.client import gNMIclient
import logging

class gNMIClient:
    """
    A gNMI client for Nokia SR OS devices.
    """

    ROUTER_CREDS = {
        "SR1": {"host": "192.168.18.111", "port": 57400, "user": "admin", "pass": "admin"},
        "SR2": {"host": "192.168.18.121", "port": 57400, "user": "admin", "pass": "admin"},
        "SR3": {"host": "192.168.18.133", "port": 57400, "user": "admin", "pass": "admin"},
        "SR4": {"host": "192.168.18.144", "port": 57400, "user": "admin", "pass": "admin"},
    }

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
        self.creds = self.ROUTER_CREDS.get(router_name)
        self.description = slice_spec.get('description', f"Service {self.service_type} {self.service_id}")
        
    

        if not self.service_type:
            self.logger.warning("Service type is missing in the NetworkSlice spec.")

    def _get_vpls_payload(self) -> Dict[str, Any]:
        """
        Builds the structured JSON payload for a VPLS service.
        """
        sdp_type = 'mesh-sdp' if self.slice_spec.get('vplsType', 'mesh-sdp') == 'mesh-sdp' else 'spoke-sdp'
        
        payload_data = {
            "admin-state": f"{self.slice_spec.get('adminState', 'enable')}",
            "description": self.description,
            "customer": self.customer_id,
            "service-id": self.service_id,
            sdp_type: [{
                "sdp-bind-id": f"{self.endpoint_spec.get('sdpId', 1000)}:{self.service_id}"
            }],
            "sap": [{
                "sap-id": f"{self.endpoint_spec.get('interfaceName')}:{self.endpoint_spec.get('vlanID')}",
                "admin-state": "enable"
            }]
        }
        
        update_path = f"/configure/service/vpls[service-name={self.service_name}]"
        
        updates = [(update_path, payload_data)]
        
        return updates

    def _get_vprn_payload(self) -> Dict[str, Any]:
        """
        Builds the structured JSON payload for a VPRN service.
        """
        interface_name = self.endpoint_spec.get('interfaceName')
        vlan_id = self.endpoint_spec.get('vlanID')
        ip_address = self.endpoint_spec.get('ipAddress', '10.0.0.1/30')
        
        payload_data = {
            "customer": self.customer_id,
            "description": self.description,
            "service-id": self.service_id,
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
        }
        
        update_path = f"/configure/service/vprn[service-id={self.service_name}]"
        
        updates = [(update_path, payload_data)]
        
        return updates

    def _get_epipe_payload(self) -> Dict[str, Any]:
        """
        Builds the structured JSON payload for an EPIPE service.
        """
        sdp_id = self.endpoint_spec.get('sdpId', 1000)
        
        payload_data = {
            "admin-state": "enable",
            "customer": self.customer_id,
            "service-id": self.service_id,
            "description": self.description,
            "sap": [
                {
                "sap-id": f"{self.endpoint_spec.get('interfaceName')}:{self.endpoint_spec.get('vlanID')}"
            }
            ],
            "spoke-sdp": {
                "sdp-bind-id": f"{self.endpoint_spec.get('sdpId', 1000)}:{self.service_id}"
            }
        }
        
        update_path = f"/configure/service/epipe[service-name={self.service_name}]"
        
        updates = [(update_path, payload_data)]
        
        return updates

    def apply_config(self) -> None:
        """
        Applies the required configuration using gNMI.
        """
        # Connection parameters
        host = (self.creds.get('host'), self.creds.get('port'))
        username=self.creds.get('user')
        password=self.creds.get('pass')

        updates = []
        if self.service_type == 'VPLS':
            updates = self._get_vpls_payload()
        elif self.service_type == 'VPRN':
            updates = self._get_vprn_payload()
        elif self.service_type == 'ePipe':
            updates = self._get_epipe_payload()
        else:
            raise NotImplementedError(f"Unsupported service type: {self.service_type}")

        with gNMIclient(target=host,
                        username=username,
                        password=password,
                        insecure=True) as client:
            self.logger.info(f"Attempting gNMI Set Update on {self.router_name}...")
            response = client.set(update=updates)
            if "error" not in response:
                self.logger.info("gNMI Set Update successful.")
            else:
                self.logger.error(f"gNMI Set Update failed: {response}")
                raise Exception(f"gNMI Set RPC failed to push config to {self.router_name}")

    def delete_config(self) -> None:
        """
        Deletes the service configuration using gNMI.
        """
        # Connection parameters
        host = (self.creds.get('host'), self.creds.get('port'))
        username=self.creds.get('user')
        password=self.creds.get('pass')
        insecure=True
        timeout=10

        delete_path = f"/configure/service/{self.service_type.lower()}[service-name={self.service_name}]"
        
        deletes = [delete_path]

        with gNMIclient(target=host,
                        username=username,
                        password=password,
                        insecure=True) as client:
            self.logger.warning(f"Deleting {self.service_type} ID:{self.service_id} on {self.router_name}...")
            response = client.set(delete=deletes)
            if "error" not in response:
                self.logger.info("gNMI Set Delete successful.")
            else:
                self.logger.error(f"gNMI Set Delete failed: {response}")
                raise Exception(f"gNMI Set RPC failed to delete config on {self.router_name}")

    def get_config(self) -> str:
        """
        Retrieves the service configuration using gNMI.
        """
        # Connection parameters
        host = (self.creds.get('host'), self.creds.get('port'))
        username=self.creds.get('user')
        password=self.creds.get('pass')
        insecure=True
        timeout=10

        path = f"/configure/service/{self.service_type.lower()}[service-name={self.service_name}]"
        
        with gNMIclient(target=host,
                        username=username,
                        password=password,
                        insecure=True) as client:
            self.logger.info(f"Retrieving config for service {self.service_id} from {self.router_name}...")
            response = client.get(path=[path], encoding='JSON_IETF')
            if (response[0]["updates"][0] and
                response[0]["updates"][0]["values"]):
                
                return response[0]["updates"][0]["values"][path]
            else:
                self.logger.warning(f"No configuration found for service {self.service_id} on {self.router_name}.")
                return "{}"

    def check_for_drift(self, desired_spec: Dict[str, Any], observed_config: str) -> bool:
        """
        Compares the desired state (CRD spec) against the observed state (gNMI output).
        """
        self.logger.debug(f"Comparing desired vs observed state for {self.service_type}...")
        
        try:
            observed_json = json.loads(observed_config)
        except json.JSONDecodeError:
            self.logger.warning(f"Could not decode observed config for service ID {self.service_id}.")
            return True

        drift_detected = False
        
        # Check Description
        desired_description = self.description
        observed_description = observed_json.get("description")
        if observed_description != desired_description:
            self.logger.warning(f"Drift detected: Description mismatch for service ID {self.service_id}. Desired: '{desired_description}', Observed: '{observed_description}'")
            drift_detected = True
        
        # Check Admin State
        desired_admin_state = f"{self.slice_spec.get('adminState', 'enable')}"
        observed_admin_state = observed_json.get("admin-state")
        if observed_admin_state != desired_admin_state:
            self.logger.warning(f"Drift detected: Admin State mismatch for service ID {self.service_id}. Desired: '{desired_admin_state}', Observed: '{observed_admin_state}'")
            drift_detected = True

        # Check SAP
        desired_sap = f"{self.endpoint_spec.get('interfaceName')}:{self.endpoint_spec.get('vlanID')}"
        observed_saps = observed_json.get("sap", [])
        
        sap_found = False
        for sap in observed_saps:
            if sap.get("sap-id") == desired_sap:
                sap_found = True
                break
        
        if not sap_found:
            self.logger.warning(f"Drift detected: SAP mismatch for service ID {self.service_id}. Desired SAP not found: '{desired_sap}'")
            drift_detected = True
            
        return drift_detected

    def get_operational_status(self) -> str:
        """
        Retrieves the operational status of the service from the network device.
        Returns "UP", "DOWN", or "UNKNOWN".
        """
        # Connection parameters
        host = (self.creds.get('host'), self.creds.get('port'))
        username=self.creds.get('user')
        password=self.creds.get('pass')

        path = f"/state/service/id[service-id={self.service_id}]/oper-state"
        
        with gNMIclient(target=host,
                        username=username,
                        password=password,
                        insecure=True) as client:
            self.logger.info(f"Retrieving operational status for service {self.service_id} from {self.router_name}...")
            response = client.get(path=[path], encoding='JSON_IETF')
            
            if (response[0]["updates"][0] and
                response[0]["updates"][0]["values"]):
                
                oper_state = response[0]["updates"][0]["values"][path]
                return oper_state.upper()
            else:
                self.logger.warning(f"Could not determine operational status for service {self.service_id} on {self.router_name}.")
                return "UNKNOWN"
