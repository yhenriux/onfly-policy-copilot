"""Fluxo LangGraph para uma consulta RAG sem autonomia de agente."""

from typing import NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from app.domain.schemas import AskRequest, AskResponse, AuthenticatedContext
from app.generation.service import AskHandler
from app.guardrails.input_guardrail import ensure_safe_question


class RagState(TypedDict):
    """Estado mínimo de uma consulta; não é persistido por padrão."""

    request: AskRequest
    context: AuthenticatedContext
    response: NotRequired[AskResponse]


class LangGraphAskHandler:
    """Executa validação e RAG como nós explícitos de um grafo determinístico."""

    def __init__(self, service: AskHandler) -> None:
        self._service = service
        graph = StateGraph(RagState)
        graph.add_node("validate_question", self._validate_question)
        graph.add_node("answer_with_rag", self._answer_with_rag)
        graph.add_edge(START, "validate_question")
        graph.add_edge("validate_question", "answer_with_rag")
        graph.add_edge("answer_with_rag", END)
        self._graph = graph.compile()

    async def _validate_question(self, state: RagState) -> dict[str, object]:
        ensure_safe_question(state["request"].question)
        return {}

    async def _answer_with_rag(self, state: RagState) -> dict[str, AskResponse]:
        response = await self._service.ask(state["request"], state["context"])
        return {"response": response}

    @traceable(name="onfly_policy_copilot_rag_graph")
    async def ask(self, request: AskRequest, context: AuthenticatedContext) -> AskResponse:
        """Executa o grafo mantendo o mesmo contrato público do serviço RAG."""
        initial_state: RagState = {"request": request, "context": context}
        result = cast(RagState, await self._graph.ainvoke(initial_state))
        return result["response"]
