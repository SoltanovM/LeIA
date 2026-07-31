"""Titulador de conversas (Stage 4): nomeia a conversa a partir da 1ª pergunta, via Bedrock.

É um "agente" especializado bem simples - uma única chamada a um modelo barato (Nova Lite),
sem tools. Injetado como `titler` no ChatService; se falhar, o service cai numa heurística.
"""

from __future__ import annotations

from typing import Any

from leia.agent.document_agent import _to_text
from leia.config import get_settings

_PROMPT = (
    "Gere um título curto (3 a 6 palavras, sem aspas e sem ponto final) para uma conversa, "
    "a partir desta primeira pergunta do usuário. Responda apenas o título.\n\n"
    "Pergunta: {question}\nTítulo:"
)


class BedrockTitler:
    """`titler` do ChatService. Modelo criado lazy (só na 1ª titulação)."""

    def __init__(self) -> None:
        self._model: Any = None

    def __call__(self, question: str) -> str:
        if self._model is None:
            from langchain_aws import ChatBedrockConverse

            settings = get_settings()
            self._model = ChatBedrockConverse(
                model=settings.bedrock_model_id,  # Nova Lite (barato) basta pra titular
                region_name=settings.aws_region,
                max_tokens=30,
                temperature=0.2,
            )
        response = self._model.invoke(_PROMPT.format(question=question))
        return _to_text(response.content).strip().strip('"').strip()
