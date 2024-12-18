from logging import getLogger
from typing import Any, Optional, List, Union, Dict
from ipaddress import ip_interface
from collections import defaultdict
import ssl

from adaptix import P
from adaptix.conversion import impl_converter, link, link_constant


from annetbox.v37 import models as api_models 
from annetbox.v37.client_sync import NetboxV37 

from annet.adapters.netbox.common import models
from annet.adapters.netbox.common.manufacturer import (
    get_hw, get_breed,
)
from annet.adapters.netbox.common.query import NetboxQuery
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage, Device, Interface

logger = getLogger(__name__)


class BaseNetboxStorage(Storage):
    netbox = NetboxV37 
    device_model = models.NetboxDevice
    api_models = api_models 
    prefix_model = models.Prefix
    interface_model = models.Interface
    ipaddress_model = models.IpAddress

    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        ctx: Optional[ssl.SSLContext] = None
        url = ""
        token = ""
        self.exact_host_filter = False
        if opts:
            if opts.insecure:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            url = opts.url
            token = opts.token
            self.exact_host_filter = opts.exact_host_filter
        self.netbox = self.netbox(url=url, token=token, ssl_context=ctx)
        self._all_fqdns: Optional[list[str]] = None
        self._initialize_decorators()

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        pass

    def _initialize_decorators(self):
        if self.device_model and self.api_models and self.prefix_model and self.interface_model and self.ipaddress_model:
            self._apply_converter_decorators()

    def _apply_converter_decorators(self):
        @impl_converter(recipe=[
            link(P[self.api_models.Device].name, P[self.device_model].hostname),
            link(P[self.api_models.Device].name, P[self.device_model].fqdn),
            link_constant(P[self.device_model].neighbours, value=None),
        ])
        def extend_device_base(
            device: self.api_models.Device,
            interfaces: List[self.interface_model],
            hw: Optional[HardwareView],
            breed: str,
            storage: Storage,
        ) -> self.device_model:
            ...

        def extend_device(
                device: self.api_models.Device,
                interfaces: List[self.interface_model],
                neighbours: Optional[List[self.device_model]],
                storage: Storage,
        ) -> self.device_model:
            platform_name: str = ""
            breed: str = ""
            hw = HardwareView("", "")
            if device.platform:
                platform_name = device.platform.name
            if device.device_type and device.device_type.manufacturer:
                breed = get_breed(
                    device.device_type.manufacturer.name,
                    device.device_type.model,
                )
                hw = get_hw(
                    device.device_type.manufacturer.name,
                    device.device_type.model,
                    platform_name,
                )
            res = extend_device_base(
                device=device,
                interfaces=interfaces,
                breed=breed,
                hw=hw,
                storage=storage,
            )
            res.neighbours = neighbours
            return res

        @impl_converter(
            recipe=[link_constant(P[self.interface_model].lag_min_links, value=None)],
        )
        def extend_interface(
            interface: self.interface_model,
            ip_addresses: List[self.ipaddress_model],
        ) -> self.interface_model:
            ...

        @impl_converter
        def extend_ip_address(
            ip_address: self.ipaddress_model,
            prefix: Optional[self.prefix_model],
        ) -> self.ipaddress_model:
            ...

        self.extend_device_base = extend_device_base
        self.extend_device = extend_device
        self.extend_interface = extend_interface
        self.extend_ip_address = extend_ip_address

    def resolve_object_ids_by_query(self, query: NetboxQuery):
        return [
            d.id for d in self._load_devices(query)
        ]

    def resolve_fdnds_by_query(self, query: NetboxQuery):
        return [
            d.name for d in self._load_devices(query)
        ]

    def resolve_all_fdnds(self) -> list[str]:
        if self._all_fqdns is None:
            self._all_fqdns = [
                d.name
                for d in self.netbox.dcim_all_devices().results
            ]
        return self._all_fqdns

    def make_devices(
            self,
            query: Union[NetboxQuery, list],
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ) -> List[device_model]:
        if isinstance(query, list):
            query = NetboxQuery.new(query)
        device_ids = {
            device.id: self.extend_device(
                device=device,
                interfaces=[],
                neighbours=[],
                storage=self,
            )
            for device in self._load_devices(query)
        }
        print(device_ids)
        if not device_ids:
            return []

        interfaces = self._load_interfaces(list(device_ids))
        neighbours = {x.id: x for x in self._load_neighbours(interfaces)}
        neighbours_seen: dict[str, set] = defaultdict(set)

        for interface in interfaces:
            device_ids[interface.device.id].interfaces.append(interface)
            for e in interface.connected_endpoints or []:
                neighbour = neighbours[e.device.id]
                if neighbour.id not in neighbours_seen[interface.device.id]:
                    neighbours_seen[interface.device.id].add(neighbour.id)
                    device_ids[interface.device.id].neighbours.append(neighbour)

        return list(device_ids.values())

    def _load_devices(self, query: NetboxQuery) -> List[api_models.Device]:
        if not query.globs:
            return []
        if self.exact_host_filter:
            devices = self.netbox.dcim_all_devices(name__ie=query.globs).results
        else:
            query = self._hostname_dot_hack(query)
            devices = [
                device
                for device in self.netbox.dcim_all_devices(
                    name__ic=query.globs,
                ).results
                if self._match_query(query, device)
            ]
        return devices

    def _load_interfaces(self, device_ids: List[int]) -> List[
        interface_model]:
        interfaces = self.netbox.dcim_all_interfaces(device_id=device_ids)
        return self._extend_interfaces(interfaces.results)

    def _load_interfaces_by_id(self, ids: List[int]) -> List[interface_model]:
        interfaces = self.netbox.dcim_all_interfaces_by_id(id=ids)
        return self._extend_interfaces(interfaces.results)

    def _extend_interfaces(self, interfaces: List[interface_model]) -> List[interface_model]:
        extended_ifaces = {
            interface.id: self.extend_interface(interface, [])
            for interface in interfaces
        }

        ips = self.netbox.ipam_all_ip_addresses(interface_id=list(extended_ifaces))
        ip_to_cidrs: Dict[str, str] = {ip.address: str(ip_interface(ip.address).network) for ip in ips.results}
        prefixes = self.netbox.ipam_all_prefixes(prefix=list(ip_to_cidrs.values()))
        cidr_to_prefix: Dict[str, self.prefix_model] = {x.prefix: x for x in prefixes.results}

        for ip in ips.results:
            cidr = ip_to_cidrs[ip.address]
            ip = self.extend_ip_address(ip, prefix=cidr_to_prefix.get(cidr))
            extended_ifaces[ip.assigned_object_id].ip_addresses.append(ip)
        return list(extended_ifaces.values())

    def _load_neighbours(self, interfaces: List[interface_model]) -> List[device_model]:
        endpoints = [e for i in interfaces for e in i.connected_endpoints or []]
        remote_interfaces_ids = [e.id for e in endpoints]
        neighbours_ids = [e.device.id for e in endpoints]
        neighbours_ifaces_dics = defaultdict(list)
        # load only the connected interface to speed things up
        for iface in self._load_interfaces_by_id(remote_interfaces_ids):
            neighbours_ifaces_dics[iface.device.id].append(iface)
        neighbours = []
        for neighbour in self.netbox.dcim_all_devices_by_id(id=neighbours_ids).results:
            extended_neighbour = self.extend_device(
                device=neighbour,
                storage=self,
                interfaces=neighbours_ifaces_dics[neighbour.id],
                neighbours=None,  # do not load recursively
            )
            neighbours.append(extended_neighbour)
        return neighbours

    def get_device(
            self, obj_id, preload_neighbors=False, use_mesh=None,
            **kwargs,
    ) -> device_model:
        device = self.netbox.dcim_device(obj_id)
        interfaces = self._load_interfaces([device.id])
        neighbours = self._load_neighbours(interfaces)

        res = self.extend_device(
            device=device,
            storage=self,
            interfaces=interfaces,
            neighbours=neighbours,
        )
        return res

    def flush_perf(self):
        pass

    def search_connections(self, device: Device, neighbor: Device) -> list[tuple[Interface, Interface]]:
        if device.storage is not self:
            raise ValueError("device does not belong to this storage")
        if neighbor.storage is not self:
            raise ValueError("neighbor does not belong to this storage")
        # both devices are NetboxDevice if they are loaded from this storage
        res = []
        for local_port in device.interfaces:
            if not local_port.connected_endpoints:
                continue
            for endpoint in local_port.connected_endpoints:
                if endpoint.device.id == neighbor.id:
                    for remote_port in neighbor.interfaces:
                        if remote_port.name == endpoint.name:
                            res.append((local_port, remote_port))
                            break
        return res
    
    def _hostname_dot_hack(self, netbox_query: NetboxQuery) -> NetboxQuery:
    # there is no proper way to lookup host by its hostname
    # ie find "host" with fqdn "host.example.com"
    # besides using name__ic (ie startswith)
    # since there is no direct analogue for this field in netbox
    # so we need to add a dot to hostnames (top-level fqdn part)
    # so we would not receive devices with a common name prefix
        def add_dot(raw_query: Any) -> Any:
            if isinstance(raw_query, str) and "." not in raw_query:
                raw_query = raw_query + "."
            return raw_query

        raw_query = netbox_query.query
        if isinstance(raw_query, list):
            for i, name in enumerate(raw_query):
                raw_query[i] = add_dot(name)

        return NetboxQuery(raw_query)

    def _match_query(self, query: NetboxQuery, device_data: api_models.Device) -> bool:
        for subquery in query.globs:
            if subquery.strip() in device_data.name:
                return True
        return False
