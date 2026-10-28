"""
Azure Blob Storage backend (the original implementation, adapted to the
TestCaseStorage interface). Authenticates with a username/password AAD
credential; MFA-enabled accounts will not work with this flow.
"""
import logging
from azure.identity import UsernamePasswordCredential
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ClientAuthenticationError

from .base import TestCaseStorage

logger = logging.getLogger(__name__)


class AzureBlobStorage(TestCaseStorage):
    display_name = "Azure Blob Storage"

    def __init__(self, account_url, tenant_id, client_id, username, password, container_name):
        if not all([account_url, tenant_id, client_id, username, password, container_name]):
            raise ValueError("All AZURE_* storage variables must be set")
        self.container_name = container_name
        try:
            credential = UsernamePasswordCredential(
                tenant_id=tenant_id, client_id=client_id, username=username, password=password
            )
            self.blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        except ClientAuthenticationError:
            logger.warning("Azure authentication failed; check credentials (MFA accounts are unsupported).")
            raise
        self.container = self.blob_service_client.get_container_client(container_name)

    def upload_bytes(self, key, data):
        self.container.get_blob_client(key).upload_blob(data, overwrite=True)

    def list_keys(self, prefix):
        return [b.name for b in self.container.list_blobs(name_starts_with=prefix)]

    def delete_prefix(self, prefix):
        keys = self.list_keys(prefix)
        for key in keys:
            self.container.delete_blob(key)
        return len(keys)
