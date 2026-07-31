"""LeIA - perguntas sobre documentos (PDF/PNG/JPG) via Amazon Bedrock.

Organizado em arquitetura hexagonal (ports & adapters):
    domain/  -> dados puros (o QUÊ)          ports.py  -> interfaces (contratos)
    service  -> caso de uso (depende só dos ports)
    adapters/-> tecnologia (o COMO: Bedrock, mock)
    factory  -> composition root (escolhe o adapter)
    ui/      -> driving adapter (Streamlit)
"""
