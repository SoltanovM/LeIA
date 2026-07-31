"""ADAPTER driven - extração multimodal por página via Amazon Bedrock (Converse API).

O Bedrock lê PDF e imagem NATIVAMENTE (sem OCR à parte). Pra ter resultado POR PÁGINA:
- PDF: quebramos em PDFs de 1 página (pypdf) e mandamos cada um como bloco `document`.
- Imagem (PNG/JPG): 1 página, bloco `image`.
Cada página vira uma chamada `converse` que transcreve o conteúdo (prompt em `prompts.py`).

Custo: ~1 chamada de LLM por página. É o detalhe de tecnologia - o núcleo não sabe disso.

Como cada página é uma chamada de REDE independente (I/O-bound), transcrevemos várias EM
PARALELO com um `ThreadPoolExecutor` (o cliente boto3 é thread-safe). O limite de threads
vem do config (`extraction_max_workers`) por causa da quota de TPS do Bedrock. A ordem das
páginas é preservada; o progresso conta as CONCLUÍDAS (monotônico, mesmo terminando fora de ordem).
"""

from __future__ import annotations

import io
import logging
import random
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from botocore.exceptions import ClientError
from pypdf import PdfReader, PdfWriter

from leia.adapters.aws_clients import bedrock_runtime
from leia.config import get_settings
from leia.domain.models import RawUpload
from leia.prompts import EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Extensão -> `format` que a Converse espera.
_IMAGE_FORMATS = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg"}

# Erros do Bedrock que valem RETENTAR (transitórios do lado do serviço). A própria API pede
# "try your request again". Erros de input (validação, doc inválido) NÃO entram aqui - retry
# neles só gastaria tempo/custo repetindo a mesma falha.
_RETRYABLE_ERRORS = frozenset(
    {
        "ModelErrorException",  # "unexpected error during processing" - transitório
        "ThrottlingException",  # quota de TPS estourada (comum com muitos workers)
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelTimeoutException",
    }
)


def _safe_name(filename: str) -> str:
    """Nome de documento aceito pela Converse ([a-zA-Z0-9], espaço, - () [])."""
    stem = filename.rsplit(".", 1)[0]
    cleaned = re.sub(r"[^a-zA-Z0-9 \-\(\)\[\]]", "-", stem)
    return re.sub(r"\s+", " ", cleaned).strip() or "pagina"


def _split_pdf_pages(data: bytes) -> list[bytes]:
    """Quebra um PDF em uma lista de PDFs de 1 página cada."""
    reader = PdfReader(io.BytesIO(data))
    pages: list[bytes] = []
    for page in reader.pages:
        writer = PdfWriter()
        writer.add_page(page)
        buffer = io.BytesIO()
        writer.write(buffer)
        pages.append(buffer.getvalue())
    return pages


class BedrockExtractor:
    """Implementação de `DocumentExtractor` sobre a Converse API do Bedrock."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model_id = settings.bedrock_model_id
        self._max_tokens = settings.bedrock_max_tokens
        self._temperature = settings.bedrock_temperature
        self._max_workers = max(1, settings.extraction_max_workers)
        self._max_retries = max(1, settings.extraction_max_retries)
        self._client = bedrock_runtime()

    def extract(
        self, upload: RawUpload, on_page: Callable[[int, int], None] | None = None
    ) -> list[str]:
        blocks = self._page_blocks(upload)
        total = len(blocks)
        workers = min(self._max_workers, total)
        # 1 página (ou paralelismo desligado): sequencial, sem overhead de threads.
        if workers <= 1:
            texts = []
            for i, block in enumerate(blocks, start=1):
                texts.append(self._transcribe(block))
                if on_page is not None:
                    on_page(i, total)
            return texts

        # Várias páginas em paralelo. Resultado indexado pela posição -> ordem preservada;
        # o progresso conta as concluídas (as_completed pode terminar fora de ordem).
        results: list[str] = [""] * total
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._transcribe, block): idx for idx, block in enumerate(blocks)
            }
            for future in as_completed(futures):
                results[futures[future]] = future.result()  # exceção propaga -> extract falha
                done += 1
                if on_page is not None:
                    on_page(done, total)
        return results

    def _page_blocks(self, upload: RawUpload) -> list[dict]:
        """Traduz o upload em blocos de content-block da Converse, um por página."""
        ext = upload.extension
        if ext in _IMAGE_FORMATS:
            return [{"image": {"format": _IMAGE_FORMATS[ext], "source": {"bytes": upload.data}}}]
        if ext == "pdf":
            name = _safe_name(upload.filename)
            return [
                {"document": {"format": "pdf", "name": f"{name} p{i}", "source": {"bytes": page}}}
                for i, page in enumerate(_split_pdf_pages(upload.data), start=1)
            ]
        raise ValueError(f"Extensão não suportada: {ext!r} (use PDF, PNG ou JPG).")

    def _transcribe(self, block: dict) -> str:
        """Transcreve uma página, retentando em erros TRANSITÓRIOS do Bedrock (backoff exp.)."""
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._client.converse(
                    modelId=self._model_id,
                    system=[{"text": EXTRACTION_SYSTEM_PROMPT}],
                    messages=[
                        {
                            "role": "user",
                            "content": [block, {"text": "Transcreva o conteúdo desta página."}],
                        }
                    ],
                    inferenceConfig={
                        "maxTokens": self._max_tokens,
                        "temperature": self._temperature,
                    },
                )
                return resp["output"]["message"]["content"][0]["text"].strip()
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                # Erro não-transitório OU acabou o orçamento de tentativas -> propaga (falha a página).
                if code not in _RETRYABLE_ERRORS or attempt == self._max_retries:
                    raise
                # Backoff exponencial com jitter (evita todos os workers baterem juntos de novo).
                delay = min(2.0**attempt, 20.0) + random.uniform(0, 0.5)
                logger.warning(
                    "Bedrock %s (tentativa %d/%d) - retentando em %.1fs",
                    code,
                    attempt,
                    self._max_retries,
                    delay,
                )
                time.sleep(delay)
        # Inalcançável (o loop retorna ou levanta), mas satisfaz o type checker.
        raise RuntimeError("retry esgotado sem resultado nem exceção")
