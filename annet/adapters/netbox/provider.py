from typing import Dict, Any, Optional

from dataclass_rest.exceptions import ClientError

from annet.storage import StorageProvider, Storage
from annet.connectors import AdapterWithName, AdapterWithConfig, T
from .common.status_client import NetboxStatusClient
from .common.storage_opts import NetboxStorageOpts
from .common.query import NetboxQuery
from .v37.storage import NetboxStorageV37
from .v41.storage import NetboxStorageV41

def storage_factory(opts: NetboxStorageOpts) -> Storage:
    client = NetboxStatusClient(opts.url, opts.token, opts.insecure)

    version_class_map = {
        "3.": NetboxStorageV37,
        "4.0": NetboxStorageV41,
        "4.1": NetboxStorageV41,
    }
    
    status = client.status()
    try:
        for version_prefix, storage_class in version_class_map.items():
            if status.netbox_version.startswith(version_prefix):
                return storage_class(opts)
    
    except ClientError as e:
        if e.status_code == 404:
            raise ValueError(f"Unsupported version: {status.netbox_version}")


class NetboxProvider(StorageProvider, AdapterWithName, AdapterWithConfig):
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None, insecure: bool = False,
                 exact_host_filter: bool = False):
        self.url = url
        self.token = token
        self.insecure = insecure
        self.exact_host_filter = exact_host_filter

    @classmethod
    def with_config(cls, **kwargs: Dict[str, Any]) -> T:
        return cls(**kwargs)

    def storage(self):
        return storage_factory

    def opts(self):
        return NetboxStorageOpts

    def query(self):
        return NetboxQuery

    @classmethod
    def name(cls) -> str:
        return "netbox"
