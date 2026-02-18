"""Local filesystem storage provider for file uploads."""

import os
import re
import uuid
from pathlib import Path

from modules.ecommerce.interfaces.storage_provider import StorageProvider, StorageResult


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem under /app/uploads/."""

    def __init__(self, upload_root: str = "/app/uploads", base_url: str = "/uploads"):
        self.upload_root = Path(upload_root)
        self.base_url = base_url

    async def upload(
        self, file_bytes: bytes, filename: str, content_type: str
    ) -> StorageResult:
        # Sanitize filename: keep only alphanumeric, dots, hyphens, underscores
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
        relative_path = f"images/{unique_name}"

        full_path = self.upload_root / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(file_bytes)

        public_url = f"{self.base_url}/{relative_path}"
        return StorageResult(storage_path=relative_path, public_url=public_url)

    async def delete(self, storage_path: str) -> None:
        full_path = self.upload_root / storage_path
        if full_path.exists():
            os.remove(full_path)
