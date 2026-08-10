"""Testes do histórico técnico por resposta."""

from pathlib import Path

from app.domain.schemas import AskResponse, ExecutionTrace, GenerationMetadata
from app.observability.session_store import ObservabilityStore


def test_store_groups_responses_by_session_without_content(tmp_path: Path) -> None:
    store = ObservabilityStore(tmp_path / "observability.sqlite")
    response = AskResponse(
        answer="resposta que não deve ser persistida",
        sources=[],
        confidence="medium",
        request_id="req_history_123",
        latency_ms=240,
        generation=GenerationMetadata(
            provider="ollama",
            model="test",
            prompt_version="test",
            status="generated",
            attempts=1,
        ),
        trace=ExecutionTrace(
            timings_ms={"total": 240.0},
            documents=[],
            estimated_output_tokens=18,
        ),
    )

    store.record(response, session_id="session_a", tenant_id="aurora", user_id="demo")

    sessions = store.sessions()
    responses = store.responses(session_id="session_a")
    assert sessions[0]["responses"] == 1
    assert responses[0]["request_id"] == "req_history_123"
    assert responses[0]["latency_ms"] == 240
    assert "answer" not in responses[0]
