"""
Storage abstraction layer for Clinical RAG CDSS.
Provides dual-mode persistence:
- Local filesystem storage for development and local testing.
- S3-compatible cloud object storage (Cloudflare R2) for production.

Transparently normalizes legacy file paths and canonical object keys.
Protects against directory traversal and keeps cloud storage private.
"""

import io
import logging
import mimetypes
import os
import re
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Union

from app import config

logger = logging.getLogger("clinical_rag.storage")

LEGACY_HEX_PREFIX_PATTERN = re.compile(r"^[0-9a-fA-F]{8}_")


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageFileNotFoundError(StorageError, FileNotFoundError):
    """Raised when a requested file or object is not found in storage."""
    pass


class StorageProvider(ABC):
    """Abstract base class defining storage provider interface."""

    @abstractmethod
    def upload(
        self,
        key: str,
        data: Union[bytes, io.BytesIO],
        content_type: Optional[str] = None
    ) -> str:
        """Uploads binary data to storage under the given key.

        Returns:
            The canonical key or path where the file was stored.
        """
        pass

    @abstractmethod
    def get_stream(self, key: str) -> Tuple[io.BytesIO, str, int]:
        """Retrieves a file stream, its MIME content type, and size in bytes.

        Returns:
            Tuple of (BytesIO stream positioned at 0, content_type, size_in_bytes)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Deletes a file from storage. Returns True if deleted or already absent."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Checks if a file exists in storage."""
        pass

    @abstractmethod
    def normalize_key(self, key_or_path: str) -> str:
        """Normalizes any path or key to a canonical storage key (e.g. documents/{safe_filename})."""
        pass


def sanitize_filename(name: str) -> str:
    """Sanitizes filename against path traversal and dangerous characters."""
    if not name or not isinstance(name, str):
        raise ValueError("Invalid storage key: filename cannot be empty")
    
    # Normalize slashes and extract base name
    cleaned = name.replace("\\", "/").strip()
    base = os.path.basename(cleaned).strip()
    
    # Check for empty, '.', or '..'
    if not base or base in (".", "..") or "\x00" in base:
        raise ValueError(f"Invalid storage key: path traversal or invalid characters detected in '{name}'")
    
    return base


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider operating on UPLOAD_DIR."""

    def __init__(self, upload_dir: Optional[str] = None, seed_dir: Optional[str] = None):
        self.upload_dir = upload_dir or config.UPLOAD_DIR
        self.seed_dir = seed_dir or config.SEED_DIR
        os.makedirs(self.upload_dir, exist_ok=True)

    def normalize_key(self, key_or_path: str) -> str:
        safe_name = sanitize_filename(key_or_path)
        return f"documents/{safe_name}"

    def _resolve_local_path(self, key_or_path: str) -> str:
        """Resolves a key or path to an existing local filesystem path."""
        if not key_or_path:
            raise ValueError("File path or key cannot be empty")

        # If it's an absolute path that exists, verify and use it
        if os.path.isabs(key_or_path) and os.path.exists(key_or_path):
            return os.path.normpath(key_or_path)

        safe_name = sanitize_filename(key_or_path)
        
        # Check upload_dir first
        upload_path = os.path.normpath(os.path.join(self.upload_dir, safe_name))
        if os.path.exists(upload_path):
            return upload_path

        # Check seed_dir second
        seed_path = os.path.normpath(os.path.join(self.seed_dir, safe_name))
        if os.path.exists(seed_path):
            return seed_path

        # Return upload_path as default destination
        return upload_path

    def upload(
        self,
        key: str,
        data: Union[bytes, io.BytesIO],
        content_type: Optional[str] = None
    ) -> str:
        safe_name = sanitize_filename(key)
        target_path = os.path.join(self.upload_dir, safe_name)

        if isinstance(data, io.BytesIO):
            content = data.getvalue()
        elif isinstance(data, bytes):
            content = data
        else:
            raise TypeError(f"Unsupported data type for upload: {type(data)}")

        with open(target_path, "wb") as f:
            f.write(content)

        return target_path

    def get_stream(self, key: str) -> Tuple[io.BytesIO, str, int]:
        local_path = self._resolve_local_path(key)
        if not os.path.exists(local_path):
            raise StorageFileNotFoundError(f"Local file not found: {key} (resolved to {local_path})")

        with open(local_path, "rb") as f:
            content = f.read()

        stream = io.BytesIO(content)
        stream.seek(0)
        size = len(content)

        mime_type, _ = mimetypes.guess_type(local_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        return stream, mime_type, size

    def delete(self, key: str) -> bool:
        try:
            local_path = self._resolve_local_path(key)
            if os.path.exists(local_path):
                os.remove(local_path)
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete local file '{key}': {e}")
            return False

    def exists(self, key: str) -> bool:
        try:
            local_path = self._resolve_local_path(key)
            return os.path.exists(local_path)
        except Exception:
            return False


class S3StorageProvider(StorageProvider):
    """S3-compatible cloud object storage provider (e.g., Backblaze B2, AWS S3, Cloudflare R2)."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
        s3_client=None
    ):
        self.bucket_name = config.S3_BUCKET_NAME if bucket_name is None else bucket_name
        self.endpoint_url = config.S3_ENDPOINT_URL if endpoint_url is None else endpoint_url
        self.access_key_id = config.S3_ACCESS_KEY_ID if access_key_id is None else access_key_id
        self.secret_access_key = config.S3_SECRET_ACCESS_KEY if secret_access_key is None else secret_access_key
        self.region_name = (config.S3_REGION or "us-east-1") if region_name is None else region_name

        if s3_client is not None:
            self.client = s3_client
        else:
            import boto3
            from botocore.config import Config

            if not self.bucket_name:
                raise ValueError("S3_BUCKET_NAME must be configured for S3 storage backend")
            if not self.endpoint_url:
                raise ValueError("S3_ENDPOINT_URL must be configured for S3 storage backend")
            if not self.access_key_id or not self.secret_access_key:
                raise ValueError("S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be configured for S3 storage backend")

            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region_name,
                config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"})
            )

    def normalize_key(self, key_or_path: str) -> str:
        safe_name = sanitize_filename(key_or_path)
        return f"documents/{safe_name}"

    def get_canonical_key_candidate(self, key_or_path: str) -> Optional[str]:
        """
        Extracts the canonical stripped-prefix candidate if the filename matches
        the legacy pattern of exactly 8 hexadecimal characters followed by an underscore.

        Returns:
            'documents/{stripped_filename}' if matching, else None.
        """
        safe_name = sanitize_filename(key_or_path)
        match = LEGACY_HEX_PREFIX_PATTERN.match(safe_name)
        if match:
            stripped = safe_name[match.end():].strip()
            if stripped and stripped not in (".", ".."):
                return f"documents/{stripped}"
        return None

    def resolve_storage_key(self, key_or_path: str) -> str:
        """
        Deterministically resolves a storage key or path to an existing S3 object key.
        - Checks exact key first.
        - If exact key does not exist and a legacy stripped candidate exists, checks candidate.
        - Returns candidate if it exists; otherwise falls back to exact key.
        """
        exact_key = self.normalize_key(key_or_path)
        candidate_key = self.get_canonical_key_candidate(key_or_path)

        if not candidate_key or candidate_key == exact_key:
            return exact_key

        if self._head_object(exact_key):
            return exact_key

        if self._head_object(candidate_key):
            return candidate_key

        return exact_key

    def _head_object(self, target_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=target_key)
            return True
        except Exception:
            return False

    def _fetch_stream(self, target_key: str) -> Tuple[io.BytesIO, str, int]:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=target_key)
            raw_body = response["Body"].read()
            stream = io.BytesIO(raw_body)
            stream.seek(0)
            size = response.get("ContentLength", len(raw_body))
            content_type = response.get("ContentType")
            if not content_type:
                content_type, _ = mimetypes.guess_type(target_key)
                if not content_type:
                    content_type = "application/octet-stream"

            return stream, content_type, size
        except Exception as e:
            error_code = getattr(getattr(e, "response", {}), "get", lambda _: None)("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey"):
                raise StorageFileNotFoundError(f"Object '{target_key}' not found in S3 bucket '{self.bucket_name}'") from e
            logger.error(f"Failed to get stream for '{target_key}' from S3: {e}")
            raise StorageError(f"S3 get_stream failed: {e}") from e

    def upload(
        self,
        key: str,
        data: Union[bytes, io.BytesIO],
        content_type: Optional[str] = None
    ) -> str:
        canonical_key = self.normalize_key(key)

        if isinstance(data, io.BytesIO):
            body = data.getvalue()
        elif isinstance(data, bytes):
            body = data
        else:
            raise TypeError(f"Unsupported data type for upload: {type(data)}")

        if not content_type:
            content_type, _ = mimetypes.guess_type(canonical_key)
            if not content_type:
                content_type = "application/octet-stream"

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=canonical_key,
                Body=body,
                ContentType=content_type
            )
            return canonical_key
        except Exception as e:
            logger.error(f"Failed to upload '{canonical_key}' to S3 bucket '{self.bucket_name}': {e}")
            raise StorageError(f"S3 upload failed: {e}") from e

    def get_stream(self, key: str) -> Tuple[io.BytesIO, str, int]:
        exact_key = self.normalize_key(key)
        candidate_key = self.get_canonical_key_candidate(key)

        try:
            return self._fetch_stream(exact_key)
        except StorageFileNotFoundError as exact_err:
            if candidate_key and candidate_key != exact_key:
                try:
                    return self._fetch_stream(candidate_key)
                except StorageFileNotFoundError:
                    pass
            raise exact_err

    def delete(self, key: str) -> bool:
        target_key = self.resolve_storage_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=target_key)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete '{target_key}' from S3: {e}")
            return False

    def exists(self, key: str) -> bool:
        exact_key = self.normalize_key(key)
        if self._head_object(exact_key):
            return True

        candidate_key = self.get_canonical_key_candidate(key)
        if candidate_key and candidate_key != exact_key:
            if self._head_object(candidate_key):
                return True

        return False


_storage_instance: Optional[StorageProvider] = None


def get_storage() -> StorageProvider:
    """Returns the singleton storage provider configured for the application."""
    global _storage_instance
    if _storage_instance is None:
        if config.STORAGE_BACKEND == "s3":
            _storage_instance = S3StorageProvider()
        else:
            _storage_instance = LocalStorageProvider()
    return _storage_instance


def reset_storage():
    """Resets the singleton storage provider (primarily for unit testing)."""
    global _storage_instance
    _storage_instance = None