"""Testes da extração determinística de fatos para o grafo."""

from datetime import date

from app.domain.models import DocumentChunk
from app.knowledge_graph.extractor import extract_document_graph


def test_extract_graph_fact_preserves_tenant_source_and_amount() -> None:
    chunk = DocumentChunk(
        tenant_id="aurora_tecnologia",
        document_id="alimentacao",
        title="Alimentação",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id="chunk_001",
        position=1,
        section="Alimentação > Limites",
        text="Em viagem nacional, o limite é R$ 130,00 por dia, exceto refeição com cliente.",
        document_hash="document-hash",
        chunk_hash="chunk-hash",
    )

    graph = extract_document_graph([chunk])

    assert graph.tenant_id == "aurora_tecnologia"
    assert graph.facts[0].amount == 130.0
    assert graph.facts[0].currency == "BRL"
    assert graph.facts[0].chunk_id == "chunk_001"
    assert graph.facts[0].exceptions == ("exceto refeição com cliente",)


def test_extract_graph_amount_accepts_brazilian_and_decimal_formats() -> None:
    brazilian = DocumentChunk(
        tenant_id="tenant",
        document_id="policy",
        title="Policy",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id="br",
        position=1,
        section="Geral",
        text="Limite R$ 1.234,56.",
        document_hash="document",
        chunk_hash="br",
    )
    decimal = DocumentChunk(
        tenant_id="tenant",
        document_id="policy",
        title="Policy",
        version="v1",
        valid_from=date(2026, 1, 1),
        valid_until=None,
        source="policy.md",
        chunk_id="dec",
        position=1,
        section="Geral",
        text="Limite R$ 130.00.",
        document_hash="document",
        chunk_hash="dec",
    )

    graph = extract_document_graph([brazilian, decimal])

    assert graph.facts[0].amount == 1234.56
    assert graph.facts[1].amount == 130.0
