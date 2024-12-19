from dataclasses import dataclass
from typing import Optional

from annet.adapters.netbox.common.models import NetboxDevice, DeviceIp, IpFamily

@dataclass
class DeviceRole:
    id: int
    url: str


@dataclass
class DeviceIpV41(DeviceIp):
    id: int
    display: str
    address: str
    family: IpFamily


@dataclass
class NetboxDeviceV41(NetboxDevice):
    role: DeviceRole 
    primary_ip: Optional[DeviceIpV41]
    primary_ip4: Optional[DeviceIpV41]
    primary_ip6: Optional[DeviceIpV41]

    def __hash__(self):
        return hash((self.id, type(self)))
