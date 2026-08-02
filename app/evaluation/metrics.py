"""Métricas determinísticas para respostas e recusas."""

from app.retrieval.lexical import tokenize


def term_coverage(answer: str, expected_terms: list[str]) -> float:
    """Mede a parcela de termos centrais encontrada na resposta."""

    if not expected_terms:
        return 1.0
    normalized_answer = " ".join(tokenize(answer))
    found = sum(" ".join(tokenize(term)) in normalized_answer for term in expected_terms)
    return found / len(expected_terms)


def token_f1(answer: str, expected_answer: str) -> float:
    """Compara palavras esperadas e produz equilíbrio entre precisão e cobertura."""

    actual = set(tokenize(answer))
    expected = set(tokenize(expected_answer))
    if not actual or not expected:
        return 0.0
    shared = len(actual & expected)
    precision = shared / len(actual)
    recall = shared / len(expected)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
