"""Abstract interface for file storage providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StorageResult:
    """Result of a file upload operation."""

    storage_path: str  # Relative path within storage (e.g. "images/uuid_file.jpg")
    public_url: (
        str  # Full URL to access the file (e.g. "/uploads/images/uuid_file.jpg")
    )


class StorageProvider(ABC):
    """Abstract base class for file storage."""

    @abstractmethod
    async def upload(
        self, file_bytes: bytes, filename: str, content_type: str
    ) -> StorageResult:
        """Upload a file and return its storage path and public URL."""
        ...

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete a file by its storage path."""
        ...
