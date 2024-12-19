from logging import getLogger

from annetbox.v37 import models as api_models
from annetbox.v37.client_sync import NetboxV37

from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.adapters.netbox.v37.models import NetboxDeviceV37 

logger = getLogger(__name__)

class NetboxStorageV37(BaseNetboxStorage):
    netbox_class = NetboxV37
    api_models = api_models
    device_model = NetboxDeviceV37
