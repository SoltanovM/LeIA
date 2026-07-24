"""Cliente Bedrock (Converse API) - o "adapter" que fala com o LLM.

Mesmo espírito do `credit_ai_scratch/llm/bedrock.py`:
    - cria o client boto3 UMA vez (instanciar client é caro);
    - usa a Converse API, que é agnóstica de modelo (troca Nova <-> Claude só mudando
      a env var BEDROCK_MODEL_ID, sem tocar neste código);
    - credenciais vêm da cadeia padrão do boto3 (AWS_PROFILE local, role em prod).

A diferença é que aqui as mensagens carregam blocos `document`/`image` (multimodais),
não só texto.
"""

from __future__ import annotations

import boto3

from leia.config import get_settings
from leia.prompts import SYSTEM_PROMPT


class BedrockClient:
    """Envolve a Converse API do Bedrock para perguntas sobre documentos."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model_id = settings.bedrock_model_id
        self._max_tokens = settings.bedrock_max_tokens
        self._temperature = settings.bedrock_temperature
        self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    def converse(self, messages: list[dict]) -> str:
        """Envia o histórico (formato Converse) e devolve o texto da resposta.

        `messages` é a lista completa da conversa. A PRIMEIRA mensagem do usuário
        carrega o bloco do documento + a pergunta; as seguintes vão só com texto -
        o modelo mantém o documento em contexto ao longo do diálogo.
        """
        resp = self._client.converse(
            modelId=self._model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            inferenceConfig={
                "maxTokens": self._max_tokens,
                "temperature": self._temperature,
            },
        )
        return resp["output"]["message"]["content"][0]["text"]
