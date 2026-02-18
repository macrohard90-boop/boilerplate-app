"""E-commerce adapter factories."""

from modules.ecommerce.interfaces.storage_provider import StorageProvider
from modules.ecommerce.adapters.local_storage import LocalStorageProvider


def get_storage_provider() -> StorageProvider:
    """Return the configured storage provider.

    Currently always returns LocalStorageProvider.
    Swap to S3StorageProvider etc. by adding config-based selection.
    """
    return LocalStorageProvider()
