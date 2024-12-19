from dataclasses import dataclass

from annet.adapters.netbox.common.models import NetboxDevice, Entity

@dataclass
class NetboxDeviceV37(NetboxDevice):
    device_role: Entity 

    def __hash__(self):
        return hash((self.id, type(self)))
