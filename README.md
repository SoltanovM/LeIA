# 📄 LeIA

App de **perguntas sobre documentos**: envie um PDF, PNG ou JPG e converse com o
conteúdo. O arquivo vai *nativamente* pro modelo no **Amazon Bedrock** (Converse API) -
sem OCR e sem extrair texto na mão.

> **Nome:** *LeIA* = "leia!" (imperativo de ler) + **IA**. 🙂

## Estrutura

```
app.py                     # entrypoint Streamlit (UI + estado da conversa)
leia/
  config.py                # pydantic-settings (LEIA_PORT, região, modelo...)
  documents.py             # arquivo -> bloco `document`/`image` da Converse API
  bedrock.py               # cliente Bedrock (Converse) - o "adapter" do LLM
  prompts.py               # prompt de sistema
requirements.txt           # streamlit, boto3, pydantic-settings
Dockerfile                 # imagem do app (usa uv)
docker-compose.leia.yml    # sobe o app isolado, na porta do .env
.env / .env.example        # LEIA_PORT=8086, região, modelo, credenciais AWS
```

## Rodar com Docker (recomendado)

```bash
cp .env.example .env      # ajuste região/credenciais se precisar
docker compose -f docker-compose.leia.yml up --build
```

Abra <http://localhost:8086>.

## Rodar local (sem Docker)

```bash
uv pip install -r requirements.txt
streamlit run app.py --server.port 8086
```

## Pré-requisitos AWS

O boto3 usa a **cadeia padrão de credenciais**: `aws configure`, `AWS_PROFILE`, SSO ou
as env vars do `.env`. A conta precisa de acesso ao Bedrock e ao modelo em
`BEDROCK_MODEL_ID` (o default *Nova Lite* é first-party - não exige assinatura no
Marketplace; Claude exige).

### Próximos passos (evoluções naturais)
- RAG com **pgvector** (reaproveitar o Postgres do `docker-compose.yml`) para documentos
  grandes, em vez de mandar o arquivo inteiro a cada pergunta.
- Guardar uploads no **S3** e histórico no banco.
- Adicionar um `LLMProvider` mock pra testar a UI offline (como no `credit_ai_scratch`).
