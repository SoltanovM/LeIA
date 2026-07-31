"""ADAPTER driven - blob store no Amazon S3. Resultado por página vira presigned URL."""

from __future__ import annotations

from leia.adapters.aws_clients import s3
from leia.config import get_settings


class S3BlobStore:
    """Guarda os objetos no bucket configurado (`s3_bucket`)."""

    def __init__(self) -> None:
        self._bucket = get_settings().s3_bucket
        self._client = s3()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()  # type: ignore[no-any-return]

    def url(self, key: str) -> str:
        """URL temporária (1h) pra baixar o objeto sem credenciais."""
        return self._client.generate_presigned_url(  # type: ignore[no-any-return]
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=3600
        )
