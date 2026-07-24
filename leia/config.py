"""Configuração central do LeIA (pydantic-settings).

Mesmo padrão do projeto `credit_ai_scratch`: `BaseSettings` lê os valores nesta ordem
de prioridade:
    1. variáveis de ambiente   (ex.: LEIA_PORT=8086)
    2. arquivo `.env` na raiz
    3. os defaults definidos aqui

`get_settings()` é memoizado com `lru_cache` - lê o ambiente/.env uma única vez por
processo e devolve sempre o mesmo objeto.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações do LeIA, carregadas do ambiente / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora env vars que não mapeamos aqui
        case_sensitive=False,  # LEIA_PORT == leia_port
    )

    # Porta em que o Streamlit sobe. Usada também no Dockerfile e no docker-compose.
    leia_port: int = 8086

    # --- AWS / Bedrock --------------------------------------------------------
    aws_region: str = "us-east-1"

    # Modelo do Bedrock (Converse API, agnóstica de provider).
    # Default = Amazon Nova Lite (first-party: NÃO passa pelo AWS Marketplace, então
    # não exige assinatura/cartão) e já entende PDF e imagem.
    # Para usar Claude (via Marketplace, exige cartão), troque por env var:
    #   BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
    bedrock_model_id: str = "us.amazon.nova-lite-v1:0"
    bedrock_max_tokens: int = 2048
    bedrock_temperature: float = 0.0  # 0.0 = respostas determinísticas


@lru_cache
def get_settings() -> Settings:
    """Configurações memoizadas por processo (lê env/.env só uma vez)."""
    return Settings()
