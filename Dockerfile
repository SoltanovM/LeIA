# LeIA - imagem do app. Instala o pacote com uv (mesmo tooling do projeto, learning 01/03).
FROM python:3.12-slim

# uv: gerenciador de pacotes rápido, copiado do binário oficial.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copia o necessário pra buildar o pacote e instala (traz streamlit/boto3/pydantic-settings
# + o console script `leia`). `--system` = instala no Python do container, sem venv.
COPY pyproject.toml README.md ./
COPY src ./src
COPY .streamlit ./.streamlit
COPY assets ./assets
RUN uv pip install --system .

# Porta padrão (sobrescrita pelo .env / compose via LEIA_PORT).
ENV LEIA_PORT=8086
EXPOSE 8086

# O console script `leia` lê LEIA_PORT e sobe o Streamlit em 0.0.0.0 (headless).
CMD ["leia"]
