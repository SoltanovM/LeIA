"""Página "Sobre o app" - documentação/showcase: arquitetura, stack, infra, observabilidade."""

from __future__ import annotations

import streamlit as st

_REPO_URL = "https://github.com/SoltanovM/LeIA"
_OBS_URL = "https://obs.leia.lab.soltanov.io"

_OVERVIEW = """
**LeIA** é uma plataforma de documentos com IA, construída como *show-case* de engenharia de
plataforma de IA. O fluxo de ponta a ponta:

**`upload`** → **extração por página** (Amazon Bedrock multimodal, sem OCR à parte) →
**persistência** → **vetorização (RAG)** → **busca semântica** e um **chat com agente** que
consome ferramentas via **MCP** pra responder fundamentado nos seus documentos.
"""

_ARCH = """
A base é **arquitetura hexagonal (Ports & Adapters)**: a dependência aponta sempre *para
dentro* - UI, MCP e infra (Bedrock/S3/Postgres) dependem do **núcleo**, nunca o contrário.
Trocar de tecnologia = escrever outro **adapter**, sem tocar no domínio.

| Papel | O quê |
|---|---|
| **Núcleo** | `domain` (tipos puros) + `ports` (Protocols) + `service`/`chat` (casos de uso) |
| **Ports** | DocumentExtractor · BlobStore · DocumentRepository · Vectorizer · ConversationStore · ConversationMemory |
| **Adapters driven** | mock (offline) · Bedrock · S3 · Postgres/pgvector |
| **Adapters driving** | Streamlit (UI) · MCP server · agente LangGraph |
| **Composition root** | `factory` - escolhe os adapters por `BACKEND` (mock \\| aws) |

O interruptor `BACKEND=mock` roda tudo offline; `BACKEND=aws` liga Bedrock + S3 + Postgres.
O swap é a "prova viva" de ports/adapters - o núcleo não muda uma linha.
"""

_STACK = """
- **UI:** Streamlit (multipage, estilo ChatGPT).
- **IA / LLM:** Amazon Bedrock - **Nova** (extração multimodal + agente) e **Titan V2**
  (embeddings). Agente com **LangChain + LangGraph** (`create_agent`, ReAct + tool-calling).
- **MCP:** servidor de *tools* (FastMCP) em **HTTP**; o agente consome via
  **langchain-mcp-adapters**. Tools: `search_pages`, `list_documents`, `page_content`,
  `find_documents`, `search_conversations`.
- **Dados:** **Postgres + pgvector** (metadados, páginas, vetores do RAG e memória entre
  conversas) e **S3** (arquivo cru + resultado por página).
- **Observabilidade:** **OpenTelemetry** (OpenInference) → **Langfuse** self-hosted (UI de LLM:
  prompts, tool-calls, tokens, custo, raciocínio do agente); + logging estruturado (`docker logs`).
- **DevX:** `uv` (packaging), `ruff` + `mypy` + `pytest` (qualidade), **Docker Compose**.
"""

_INFRA = """
**Docker Compose** sobe o ecossistema:

- `leia` - a UI (Streamlit) + o agente (in-process).
- `leia-mcp` - o servidor MCP (mesma imagem, transporte HTTP).
- `postgres` - Postgres com **pgvector**.
- `langfuse` - recebe os *traces* OpenTelemetry do agente (UI de LLM em `:3000`).

**Networking / acesso externo:** a máquina local não tem IP público. Um cliente de **túnel
reverso (frp)** disca *pra fora*, até um **relay na AWS** (frps + Caddy), que publica o app com
HTTPS - sem abrir porta na rede local.
"""

_OBS = f"""
Num sistema com **agente de IA**, a resposta final esconde o mais interessante: *como* o agente
chegou nela. Qual ferramenta ele decidiu chamar? Com quais argumentos? Quantos tokens custou?
Onde demorou? **Observabilidade** é enxergar tudo isso - essencial pra depurar, otimizar custo
e confiar no que o agente faz.

**Como funciona aqui.** Cada pergunta no chat vira um **trace** (uma "linha do tempo" da
requisição). O código é instrumentado com **OpenTelemetry** (padrão aberto, *vendor-neutral*) via
**OpenInference**, que envolve automaticamente cada chamada de LLM, cada *tool* e cada passo do
agente num *span*. Esses spans são exportados por **OTLP** para o **Langfuse** (uma UI de
observabilidade feita sob medida pra LLMs) - self-hosted, roda na sua própria infra.

**O que dá pra ver no trace:**

- 🧠 o **raciocínio do agente** passo a passo (ReAct: pensa → age → observa);
- 🔧 **qual tool** ele escolheu (`search_pages`, `page_content`, …), com **args e resultado**;
- 🔢 **tokens** de entrada/saída, **custo** estimado e **latência** de cada etapa;
- 🧵 tudo aninhado numa árvore - dá pra abrir um passo específico e inspecionar.

**👀 Veja ao vivo:** o painel do Langfuse deste ambiente fica em
**[{_OBS_URL}]({_OBS_URL})** - abra e acompanhe os *traces* dos agentes/tools em tempo real.

> 💡 *Rodando localmente?* O Langfuse é um stack pesado (~6 containers), então sobe sob demanda:
> **`make obs`** liga o painel (UI em `:3000`) e depois é só setar `OTEL_ENABLED=true` no `.env`
> e reiniciar o `leia`. Detalhes no `Makefile` (`make help`).

Como bônus, um **log estruturado** (`docker logs`) narra os mesmos passos em texto legível:
`👤 pergunta` → `🤖 escolheu a tool …` → `🔧 tool → …` → `🤖 resposta`.
"""


def render() -> None:
    st.title("📚 Sobre o app")
    st.markdown(f"🔗 **Código-fonte:** [{_REPO_URL}]({_REPO_URL})")
    st.markdown(_OVERVIEW)

    st.subheader("🏗️ Arquitetura (hexagonal)")
    st.markdown(_ARCH)

    st.subheader("🧰 Stack & bibliotecas")
    st.markdown(_STACK)

    st.subheader("🐳 Infra & networking")
    st.markdown(_INFRA)

    st.subheader("🔭 Observabilidade")
    st.markdown(_OBS)

    st.subheader("✅ Qualidade")
    st.markdown("Núcleo testável sem AWS (adapters mock) - `ruff` + `mypy` + `pytest` no CI local.")
