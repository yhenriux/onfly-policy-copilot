"""Respostas claras para dúvidas frequentes, sempre extraídas das fontes recuperadas."""

import re
import unicodedata
from dataclasses import dataclass

from app.domain.models import RetrievedChunk

GROUNDED_ANSWER_VERSION = "grounded_answer_v1"

_QUERY_EXPANSIONS = {
    "bagagem": "bagagem mala despachada peso permitido condições",
    "hospedagem": "hotel hospedagem diária limite valor aprovação canal de reserva",
    "reembolso": "reembolso prazo comprovantes passo a passo aprovação",
    "transporte_local": "aplicativo táxi transporte local trajetos permitidos comprovante",
}


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Resposta montada somente com trechos encontrados pelo RAG."""

    answer: str
    chunks: list[RetrievedChunk]


def extract_grounding_facts(chunks: list[RetrievedChunk]) -> list[str]:
    """Extrai frases com limites, condições e ações para orientar a geração."""

    facts: list[str] = []
    markers = (
        "r$",
        "permit",
        "pode",
        "deve",
        "não pode",
        "até",
        "prazo",
        "aprovação",
        "comprov",
        "quando",
        "entre",
        "exige",
    )
    for chunk in chunks:
        for sentence in re.split(r"(?<=[.!?])\s+", chunk.text.strip()):
            normalized = _plain(sentence)
            if (
                sentence
                and any(marker in normalized for marker in markers)
                and sentence not in facts
            ):
                facts.append(sentence)
    return facts[:8]


_INTENTS = (
    (("mala", "bagagem", "despachar"), "bagagem", ("bagagem",), "Bagagem"),
    (("hotel", "hospedagem", "diaria"), "hospedagem", ("hospedagem",), "Hospedagem"),
    (("reembolso", "reembolsar"), "reembolso", ("reembolso",), "Reembolso"),
    (
        ("aplicativo", "taxi", "uber", "transporte"),
        "transporte_local",
        ("transporte local", "transporte terrestre"),
        "Transporte local",
    ),
)


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _intent(question: str) -> tuple[str, tuple[str, ...], str] | None:
    plain_question = _plain(question)
    for keywords, document_suffix, section_terms, label in _INTENTS:
        if any(re.search(rf"\b{re.escape(keyword)}\w*\b", plain_question) for keyword in keywords):
            return document_suffix, section_terms, label
    return None


def build_grounded_answer(
    question: str,
    chunks: list[RetrievedChunk],
) -> GroundedAnswer | None:
    """Reúne os chunks do assunto quando a pergunta corresponde a uma dúvida principal."""

    intent = _intent(question)
    if intent is None:
        return None
    document_suffix, section_terms, label = intent
    relevant = [
        chunk
        for chunk in chunks
        if chunk.document_id.endswith(document_suffix)
        or any(term in _plain(f"{chunk.title} {chunk.section}") for term in section_terms)
    ]
    if not relevant:
        return None
    relevant.sort(key=lambda chunk: chunk.position)
    unique: list[RetrievedChunk] = []
    seen_sections: set[str] = set()
    for chunk in relevant:
        if chunk.section not in seen_sections:
            unique.append(chunk)
            seen_sections.add(chunk.section)
    lines = [f"{label}: esta é a orientação da sua empresa."]
    for chunk in unique[:3]:
        lines.append(f"• {chunk.section}: {chunk.text}")
    return GroundedAnswer(answer="\n\n".join(lines), chunks=unique[:3])


def rewrite_frequent_question(question: str) -> str:
    """Acrescenta vocabulário da política às quatro perguntas principais."""

    intent = _intent(question)
    if intent is None:
        return question
    document_suffix, _, _ = intent
    return f"{question} {_QUERY_EXPANSIONS[document_suffix]}"
