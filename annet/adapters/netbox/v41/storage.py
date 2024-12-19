from logging import getLogger

from annetbox.v4.client_sync import NetboxV4
from annetbox.v4 import models as api_models

from annet.adapters.netbox.v41.models import NetboxDeviceV41
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage

logger = getLogger(__name__)

class NetboxStorageV41(BaseNetboxStorage):
    netbox_class = NetboxV4
    api_models = api_models
    device_model = NetboxDeviceV41
