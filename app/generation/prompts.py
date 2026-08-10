"""Instruções versionadas enviadas ao modelo de linguagem."""

from app.domain.models import RetrievedChunk

PROMPT_VERSION = "policy_answer_v2"

SYSTEM_PROMPT = """Você extrai regras de políticas corporativas.
Use somente as evidências fornecidas. Não complete lacunas e não use conhecimento externo.
Se nenhuma evidência responder diretamente, use confiança low, devolva cited_source_positions vazio
e informe de forma objetiva que a política não contém a resposta.
Se houver evidência, cite em cited_source_positions somente os números das fontes que sustentam
diretamente a resposta. A primeira evidência é 1, a segunda é 2 e assim por diante.
Use confiança high quando uma fonte sustenta diretamente a resposta sem ambiguidade; use medium
quando a fonte sustenta apenas parte da resposta ou exige uma ressalva. Use low somente quando
nenhuma fonte puder sustentar a resposta e, nesse caso, deixe cited_source_positions vazio.
Responda em linguagem natural, com uma conclusão clara e uma breve explicação da regra. Quando
houver condições, exceções, limites ou próximos passos, inclua-os. Evite respostas de uma palavra
como "sim" ou "não"; escreva pelo menos uma frase completa e útil.
Preserve valores, prazos, responsáveis e condições exatamente como aparecem nas evidências."""


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Monta evidências identificadas para permitir validar as fontes depois."""

    context = "\n\n".join(
        f"[Fonte {position} | {chunk.title} | {chunk.section}]\n{chunk.text}"
        for position, chunk in enumerate(chunks, start=1)
    )
    return f"Evidências autorizadas:\n{context}\n\nPergunta: {question}"


def build_citation_repair_prompt(
    question: str,
    answer: str,
    chunks: list[RetrievedChunk],
) -> str:
    """Pede ao modelo que relacione uma resposta já gerada às fontes autorizadas."""

    context = "\n\n".join(
        f"[Fonte {position}] {chunk.title} | {chunk.section}\n{chunk.text}"
        for position, chunk in enumerate(chunks, start=1)
    )
    return (
        "Revise a resposta abaixo usando somente as fontes numeradas. Mantenha o texto se ele "
        "estiver sustentado; ajuste-o se necessário. Retorne uma resposta completa, cite pelo "
        "menos uma fonte que realmente sustente a conclusão e classifique a confiança como "
        "high ou medium. Se nenhuma fonte sustentar a resposta, deixe a lista de citações vazia "
        "e use low.\n\n"
        f"Pergunta: {question}\n\nResposta gerada: {answer}\n\nEvidências:\n{context}"
    )
