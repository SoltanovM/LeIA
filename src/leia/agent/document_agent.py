"""Agente do chat: LangGraph (ReAct) + Claude (Bedrock) consumindo o `leia-mcp`.

O agente NÃO fala com o núcleo direto - ele chama as **MCP tools** (search_pages,
list_documents, page_content) via HTTP (langchain-mcp-adapters). Isso demonstra a
integração agente ↔ MCP de verdade. É injetado como `answerer` no `ChatService`.

Lazy: conecta no MCP e monta o grafo só na 1ª pergunta (não quebra a UI se o MCP ainda não
subiu). Cada resposta é fundamentada no que as tools retornam (RAG sobre os documentos).
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from leia.config import get_settings
from leia.domain.models import ChatMessage

logger = logging.getLogger("leia.agent")

# Tools que trazem CONTEÚDO de documento (afirmação baseada nelas TEM que citar a fonte).
# Metadados (list_documents/total_pages/find_documents) e memória não exigem citação.
_GROUNDING_TOOLS = {"search_pages", "page_content"}

# Sinais de citação numa resposta: uma linha "Fontes:" (obrigatória no prompt) OU uma citação
# inline tipo [arquivo.pdf, p. 3] / (contrato, página 5).
_SOURCES_RE = re.compile(r"^\s*fontes?\s*:", re.IGNORECASE | re.MULTILINE)
_INLINE_CITE_RE = re.compile(r"[\[(][^\])]+,\s*(?:p\.?|p[áa]g\.?|p[áa]gina)\s*\d+", re.IGNORECASE)

# Instrução de correção quando a resposta veio sem citar (reescrita forçada, 1 tentativa).
_CITATION_FIX = (
    "Sua resposta anterior NÃO citou as fontes. Reescreva a MESMA resposta, sem mudar o "
    "conteúdo, adicionando após cada afirmação a citação no formato [arquivo.pdf, p. N] "
    "(use os campos filename e page_number que as tools retornaram) e terminando com uma "
    "linha que começa com 'Fontes:'. Não invente fontes; use só o que as tools trouxeram."
)

_SYSTEM_PROMPT = """Você é o LeIA, um assistente que responde perguntas sobre os documentos \
do usuário.

Use SEMPRE as ferramentas antes de responder:
- `search_pages(query)` para achar os trechos mais relevantes nos documentos (busca semântica);
- `list_documents()` para saber quais documentos existem;
- `page_content(document_id, page_number)` para ler uma página inteira quando precisar;
- `search_conversations(query)` para lembrar do que já foi conversado antes (memória entre conversas).

Sobre QUAL documento o usuário quer: se ele se referir de forma aproximada ou com o nome \
ligeiramente errado, ESCOLHA você mesmo o mais provável - as tools aceitam o nome aproximado no \
`document_id` (resolvem o id sozinhas), e você pode chamar `list_documents()` pra ver as opções. \
NUNCA peça o id nem o nome exato ao usuário. Se uma tool voltar vazia, tente `search_pages`. \
Se ainda assim não identificar o documento, chame `find_documents(nome)` e PERGUNTE confirmando \
o mais parecido ("Você quis dizer 'X.pdf'?") - nunca diga apenas que não encontrou.

Responda SOMENTE com base no que as ferramentas retornarem. Se a informação não estiver nos \
documentos, diga isso com clareza - não invente (e, nesse caso, não cite nada).

CITAÇÃO É OBRIGATÓRIA. Toda afirmação baseada nos documentos DEVE vir com a fonte, no formato \
`[arquivo.pdf, p. N]`, logo depois da frase. Use o campo `filename` e o `page_number` que as \
tools retornam - NUNCA o id/hash. Se uma frase se apoia em várias páginas, cite todas \
`[arquivo.pdf, p. 2; p. 5]`. Ao final, adicione uma linha começando com "Fontes:" listando os \
pares arquivo/página que você usou. Sem fonte, não afirme. Responda no mesmo idioma da pergunta."""


def _to_text(content: Any) -> str:
    """Normaliza o conteúdo de uma mensagem (string ou lista de blocos) para texto."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
    return str(content)


def _final_text(messages: list[Any]) -> str:
    """Texto da última mensagem COM conteúdo (ignora mensagens de tool/vazias)."""
    for message in reversed(messages):
        text = _to_text(getattr(message, "content", "")).strip()
        if text:
            return text
    return ""


def _has_citation(text: str) -> bool:
    """A resposta cita as fontes? (linha 'Fontes:' ou citação inline [arquivo, p. N])."""
    return bool(_SOURCES_RE.search(text) or _INLINE_CITE_RE.search(text))


def _used_grounding(messages: list[Any]) -> bool:
    """Alguma tool de CONTEÚDO (search_pages/page_content) retornou algo? Então tem que citar."""
    for message in messages:
        if type(message).__name__ != "ToolMessage":
            continue
        if getattr(message, "name", "") not in _GROUNDING_TOOLS:
            continue
        if _to_text(getattr(message, "content", "")).strip():
            return True
    return False


def _log_trace(messages: list[Any]) -> None:
    """Loga o passo a passo do agente em texto legível (aparece no docker logs leia)."""
    for message in messages:
        kind = type(message).__name__
        content = _to_text(getattr(message, "content", "")).strip()
        tool_calls = getattr(message, "tool_calls", None) or []
        if kind == "HumanMessage":
            logger.info("👤 pergunta: %s", content[:300])
        elif kind == "ToolMessage":
            logger.info("🔧 tool %s → %s", getattr(message, "name", "?"), content[:400])
        elif kind == "AIMessage":
            for call in tool_calls:
                logger.info("🤖 escolheu a tool %s(%s)", call.get("name"), call.get("args"))
            if content:
                logger.info("🤖 resposta: %s", content[:600])
        elif content:
            logger.info("… %s: %s", kind, content[:200])


class DocumentAgent:
    """`answerer` do ChatService - responde via agente ReAct sobre as MCP tools."""

    def __init__(self) -> None:
        self._agent: Any = None

    def _ensure(self) -> None:
        """Monta o agente uma vez (conecta no MCP, carrega as tools, cria o grafo)."""
        if self._agent is not None:
            return
        from langchain.agents import create_agent
        from langchain_aws import ChatBedrockConverse
        from langchain_mcp_adapters.client import MultiServerMCPClient

        settings = get_settings()
        model = ChatBedrockConverse(model=settings.agent_model_id, region_name=settings.aws_region)
        client = MultiServerMCPClient(
            {"leia": {"url": settings.mcp_url, "transport": "streamable_http"}}
        )
        tools = asyncio.run(client.get_tools())
        # API nova do LangChain 1.x (substitui langgraph.prebuilt.create_react_agent).
        self._agent = create_agent(model, tools, system_prompt=_SYSTEM_PROMPT)

    # Quantas mensagens passadas mandar pro agente (evita histórico explodindo).
    _HISTORY_LIMIT = 12

    def answer(self, question: str, history: list[ChatMessage]) -> str:
        self._ensure()
        recent = history[-self._HISTORY_LIMIT :]
        messages: list[dict[str, str]] = [{"role": m.role, "content": m.content} for m in recent]
        messages.append({"role": "user", "content": question})
        logger.info("agente: pergunta=%r (histórico=%d msgs)", question[:100], len(history))
        try:
            result = asyncio.run(self._agent.ainvoke({"messages": messages}))
        except Exception:
            logger.exception("agente falhou ao responder")
            return "⚠️ O agente falhou ao responder - veja os logs (make test-logs)."

        out = result.get("messages", []) if isinstance(result, dict) else []
        _log_trace(out)  # passo a passo legível no docker logs
        answer = _final_text(out)
        if not answer:
            logger.warning("agente devolveu resposta VAZIA (%d msgs no resultado)", len(out))
            return "🤔 Não consegui formular uma resposta agora. Tente reformular a pergunta."

        # Checagem de citação: se usou conteúdo de documento mas não citou, força a reescrita.
        if _used_grounding(out) and not _has_citation(answer):
            logger.warning("resposta baseada em documentos SEM citar fontes - forçando reescrita")
            answer = self._enforce_citations(messages, answer)
        return answer

    def _enforce_citations(self, base_messages: list[dict[str, str]], answer: str) -> str:
        """Uma reescrita corretiva pra obrigar a citação. Se ainda faltar, anexa um aviso."""
        convo = [
            *base_messages,
            {"role": "assistant", "content": answer},
            {"role": "user", "content": _CITATION_FIX},
        ]
        try:
            result = asyncio.run(self._agent.ainvoke({"messages": convo}))
        except Exception:
            logger.exception("falha ao forçar citações - devolvendo a resposta original")
            return answer
        fixed = _final_text(result.get("messages", []) if isinstance(result, dict) else [])
        if fixed and _has_citation(fixed):
            return fixed
        # Não citou nem na 2ª tentativa: devolve a melhor versão com um aviso honesto.
        best = fixed or answer
        return best.rstrip() + "\n\n_⚠️ Não consegui vincular as fontes automaticamente._"
