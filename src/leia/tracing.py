"""Observabilidade do agente com OpenTelemetry.

`OpenInference` instrumenta o LangChain/LangGraph automaticamente (cada chamada de LLM, tool
e passo do agente vira um *span*); os spans são exportados via OTLP pro **Langfuse** (UI de
LLM: prompts, tokens, custo, latência). Como é OTLP puro (vendor-neutral), daria pra apontar
pra qualquer outro backend OTLP sem mudar o código. Liga com `OTEL_ENABLED=true`.

Langfuse autentica o endpoint OTLP: se `langfuse_public_key`/`langfuse_secret_key` estiverem
setados, mandamos o header `Authorization: Basic base64(public:secret)`. Sem chaves, vai sem
auth. O app não depende do SDK do Langfuse.
"""

from __future__ import annotations

import base64
import logging

from leia.config import get_settings

logger = logging.getLogger("leia.tracing")
_configured = False


def setup_tracing() -> None:
    """Configura o tracing OTel + instrumenta o LangChain (idempotente, no-op se desligado)."""
    global _configured
    settings = get_settings()
    if _configured or not settings.otel_enabled:
        return
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Auth Basic do Langfuse (pula se as chaves não estiverem setadas).
        headers: dict[str, str] = {}
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            token = base64.b64encode(
                f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"

        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.otel_service_name})
        )
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.otel_endpoint}/v1/traces", headers=headers or None
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        LangChainInstrumentor().instrument()
        _configured = True
        logger.info(
            "OTel tracing ligado -> %s (service=%s, auth=%s)",
            settings.otel_endpoint,
            settings.otel_service_name,
            "langfuse" if headers else "none",
        )
    except Exception:
        logger.exception("falha ao configurar o OpenTelemetry (seguindo sem tracing)")
