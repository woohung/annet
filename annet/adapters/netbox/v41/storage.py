from logging import getLogger

from annetbox.v4.client_sync import NetboxV4
from annetbox.v4 import models as api_models

from annet.adapters.netbox.v41 import models
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage

logger = getLogger(__name__)


class NetboxStorageV41(BaseNetboxStorage):
    netbox = NetboxV4
    device_model = models.NetboxDevice
    api_models = api_models
    prefix_model = models.Prefix
    interface_model = models.Interface
    ipaddress_model = models.IpAddress

