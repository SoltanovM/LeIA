"""Fábrica de clients boto3 — ponto único onde os clients AWS nascem.

Memoizados com `lru_cache` (criar client boto3 é caro; o client é reusável). Credenciais
vêm da cadeia padrão do boto3 (AWS_PROFILE/SSO local, role em prod). `aws_endpoint_url`
(opcional) aponta pra LocalStack/MinIO no dev.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3

from leia.config import get_settings


def _kwargs() -> dict[str, Any]:
    settings = get_settings()
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:  # só no dev (LocalStack/MinIO); em prod fica None
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    return kwargs


@lru_cache
def bedrock_runtime() -> Any:
    """Client do Bedrock runtime (Converse p/ extração, invoke_model p/ embeddings)."""
    return boto3.client("bedrock-runtime", **_kwargs())


@lru_cache
def s3() -> Any:
    """Client do S3 (blob store)."""
    return boto3.client("s3", **_kwargs())
