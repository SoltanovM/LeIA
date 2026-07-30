"""Configuração central do LeIA (pydantic-settings).

`BaseSettings` lê os valores nesta ordem: 1) variáveis de ambiente, 2) `.env`, 3) defaults
daqui. `get_settings()` é memoizado com `lru_cache` (lê env/.env uma vez por processo).

`BACKEND` é o interruptor híbrido, no espírito da "prova viva de ports/adapters":
    mock -> tudo offline (extractor fake, blob em disco, repo em memória, vetor fake)
    aws  -> Bedrock (extração + embeddings) + S3 (blob) + Postgres/pgvector (metadados+vetor)
Trocar de um pro outro NÃO muda o domínio/service — só qual adapter a `factory` injeta.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendName(StrEnum):
    """Conjunto de adapters a injetar (ver `factory`)."""

    MOCK = "mock"  # offline, sem AWS/Postgres — default de dev
    AWS = "aws"  # Bedrock + S3 + Postgres/pgvector


class Settings(BaseSettings):
    """Configurações do LeIA, carregadas do ambiente / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,  # LEIA_PORT == leia_port
    )

    # Porta em que a UI sobe (console script `leia`, Dockerfile, compose).
    leia_port: int = 8086

    # --- Login (usuário default) ----------------------------------------------
    # ⚠️ Simplificado p/ portfólio: senha em texto no .env (git-ignored). Em produção,
    # trocar por hash (bcrypt) + provedor de identidade. Senha vazia = login desabilitado.
    auth_user: str = "matt"
    auth_password: str = ""

    # Interruptor de adapters. MOCK por padrão: a UI sobe sem AWS/Postgres.
    backend: BackendName = BackendName.MOCK

    # --- AWS / Bedrock (usado no backend=aws) ---------------------------------
    aws_region: str = "us-east-1"
    # None = AWS real; local (LocalStack/MinIO) = "http://localhost:4566".
    aws_endpoint_url: str | None = None

    # Extração multimodal: Nova Lite = first-party (sem Marketplace), lê PDF e imagem.
    #   BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0  (Claude, via Marketplace)
    bedrock_model_id: str = "us.amazon.nova-lite-v1:0"
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.0  # 0.0 = determinístico (transcrição fiel)

    # Embeddings (Titan V2 first-party) — usados pelo Vectorizer pgvector.
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_dimensions: int = 1024

    # --- Blob store (S3 no backend=aws) ---------------------------------------
    s3_bucket: str = "leia-documents"
    # Diretório do blob em disco (backend=mock).
    blob_dir: str = ".leia-blobs"

    # --- Metadados + vetores (Postgres/pgvector no backend=aws) ---------------
    database_url: str = "postgresql://leia:leia@localhost:5432/leia"

    # --- Servidor MCP (Stage 2/3) ---------------------------------------------
    mcp_host: str = "0.0.0.0"  # bind do servidor MCP HTTP
    mcp_port: int = 8087
    # URL que o agente usa pra conectar no MCP. No compose: http://leia-mcp:8087/mcp.
    mcp_url: str = "http://localhost:8087/mcp"


@lru_cache
def get_settings() -> Settings:
    """Configurações memoizadas por processo (lê env/.env só uma vez)."""
    return Settings()
