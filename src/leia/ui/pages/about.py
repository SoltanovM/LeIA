"""Página "Sobre mim" - perfil + CV. Dados a partir do CV; ajuste à vontade.

CV: fica em `assets/cv.pdf` (git-ignored; o app lê do working tree/imagem).
"""

from __future__ import annotations

import streamlit as st

_NAME = "Merdan Soltanov"
_ROLE = "Data & AI Engineer"
_PITCH = "4+ anos construindo pipelines de dados e sistemas de IA em produção."

_BIO = """
Data & AI Engineer com base forte em **matemática** (medalhista de Olimpíada Internacional).
Experiência em **arquiteturas de dados escaláveis**, **inferência em GPU** e **aplicações com
LLM** pra casos reais - de OCR + LLM em documentos jurídicos a workflows agênticos.
"""

# Como este projeto (LeIA) conecta com a minha experiência real.
_TIE_IN = """
O **LeIA** não é teoria: é a mesma stack que já entreguei em produção, montada de forma limpa
como show-case.

- **OCR + LLM em documentos** → na DOMUS construí um motor de OCR com inferência de LLM (vLLM)
  e processamento assíncrono de documentos jurídicos em larga escala.
- **Agentes / agentic workflows** → lá usei **CrewAI** pra geração automática de pareceres; aqui
  o agente é **LangGraph** consumindo **MCP tools**.
- **Embeddings / RAG** → troquei uma solução paga de embeddings por um stack open-source em GPU;
  aqui é **pgvector + Titan**.
- **Backend & Cloud** → FastAPI, Redis, Docker, Kubernetes, **AWS** (Lambda, S3, API Gateway).
"""

_SKILLS = {
    "Linguagens": ["Python", "SQL", "Bash"],
    "Data Engineering": [
        "Airflow",
        "PySpark",
        "Spark SQL",
        "ETL/ELT",
        "Data Modeling",
        "Lakehouse",
        "Databricks",
    ],
    "IA / ML": ["LLMs", "Agentic Workflows", "RAG / Embeddings", "vLLM", "Hugging Face", "NLP"],
    "Cloud & DevOps": ["AWS", "Docker", "Kubernetes", "Terraform"],
    "Plataformas & Backend": [
        "dbt",
        "Airbyte",
        "BigQuery",
        "Snowflake",
        "FastAPI",
        "Redis",
        "ElasticSearch",
    ],
}

_EXPERIENCE = [
    ("DOMUS Capital", "Data Engineer", "abr 2023 – abr 2026"),
    ("Dolomites Consultoria", "Data Engineer (estágio)", "nov 2022 – abr 2023"),
    ("Laguz Opportunities", "Data Engineer (estágio)", "mar 2022 – nov 2022"),
]

_EDU = [
    ("USP", "Bacharelado em Matemática", "2017 – 2023"),
    ("Faculdade Facint", "Pós - Engenharia de Dados", "2024 – 2026"),
]

_AWARDS = [
    "🥉 2x Bronze - Olimpíada Internacional de Matemática",
    "🥈 2x Prata - Olimpíada Nacional de Matemática",
    "Certificações: IBM Data Engineering, AWS Cloud Practitioner",
]

_CONTACT = {
    "E-mail": "contact@soltanov.io",
    "LinkedIn": "https://www.linkedin.com/in/merdan-soltanov/",
    "GitHub": "https://github.com/SoltanovM",
    "Local": "São Paulo, Brasil",
}

# CV parado: reative o import (from pathlib import Path) + o bloco de download no render().
# _CV_PATH = Path("assets/cv.pdf")


def render() -> None:
    st.title("🧑‍💻 Sobre mim")

    col_info, _col_cv = st.columns([2, 1])
    with col_info:
        st.header(_NAME)
        st.caption(f"{_ROLE} · {_PITCH}")
        st.markdown(_BIO)
    # with _col_cv:
    #     if _CV_PATH.exists():
    #         st.download_button(
    #             "📄 Baixar meu CV",
    #             data=_CV_PATH.read_bytes(),
    #             file_name="Merdan-Soltanov-CV.pdf",
    #             mime="application/pdf",
    #             type="primary",
    #             width="stretch",
    #         )
    #     else:
    #         st.info("Coloque o CV em `assets/cv.pdf` para o download aparecer aqui.")

    st.subheader("🔗 Este projeto & minha experiência")
    st.markdown(_TIE_IN)

    st.subheader("🛠️ Skills")
    for group, items in _SKILLS.items():
        st.markdown(f"**{group}:** " + " · ".join(items))

    col_exp, col_edu = st.columns(2)
    with col_exp:
        st.subheader("💼 Experiência")
        for company, role, period in _EXPERIENCE:
            st.markdown(f"**{company}** - {role}  \n:gray[{period}]")
    with col_edu:
        st.subheader("🎓 Formação & conquistas")
        for school, course, period in _EDU:
            st.markdown(f"**{school}** - {course}  \n:gray[{period}]")
        for award in _AWARDS:
            st.markdown(f"- {award}")

    st.subheader("📬 Contato")
    for label, value in _CONTACT.items():
        st.markdown(f"- **{label}:** {value}")
