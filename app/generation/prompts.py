"""Instruções versionadas enviadas ao modelo de linguagem."""

from app.domain.models import RetrievedChunk

PROMPT_VERSION = "policy_answer_v2"

SYSTEM_PROMPT = """Você extrai regras de políticas corporativas.
Use somente as evidências fornecidas. Não complete lacunas e não use conhecimento externo.
Se nenhuma evidência responder diretamente, use confiança low, devolva cited_source_positions vazio
e informe de forma objetiva que a política não contém a resposta.
Se houver evidência, cite em cited_source_positions somente os números das fontes que sustentam
diretamente a resposta. A primeira evidência é 1, a segunda é 2 e assim por diante.
Preserve valores, prazos, responsáveis e condições exatamente como aparecem nas evidências."""


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Monta evidências identificadas para permitir validar as fontes depois."""

    context = "\n\n".join(
        f"[Fonte {position} | {chunk.title} | {chunk.section}]\n{chunk.text}"
        for position, chunk in enumerate(chunks, start=1)
    )
    return f"Evidências autorizadas:\n{context}\n\nPergunta: {question}"
