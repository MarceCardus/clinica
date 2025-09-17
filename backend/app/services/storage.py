import hashlib
import io
from pathlib import Path

from minio import Minio

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self.fallback_dir = Path("/tmp/proofs")
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

    def ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MinIO no disponible, usando almacenamiento local", error=str(exc))

    def upload(self, *, content: bytes, filename: str, content_type: str) -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        object_name = f"{digest}/{filename}"
        try:
            self.ensure_bucket()
            data_stream = io.BytesIO(content)
            self.client.put_object(
                self.bucket,
                object_name,
                data=data_stream,
                length=len(content),
                content_type=content_type,
            )
            url = f"s3://{self.bucket}/{object_name}"
            return url, digest
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fallo al subir a MinIO, guardando localmente", error=str(exc))
            local_path = self.fallback_dir / object_name.replace("/", "_")
            local_path.write_bytes(content)
            return str(local_path), digest


storage_service = StorageService()
