"""Métricas operacionais simples mantidas na memória do processo."""

from collections import defaultdict
from threading import Lock
from typing import Any


class OperationalMetrics:
    """Conta eventos e calcula a latência média de cada componente."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latency_sum: dict[str, float] = defaultdict(float)
        self._latency_count: dict[str, int] = defaultdict(int)

    def increment(self, name: str, amount: int = 1) -> None:
        """Soma uma ocorrência a um contador."""

        with self._lock:
            self._counters[name] += amount

    def observe_latency(self, component: str, milliseconds: float) -> None:
        """Acumula uma medição para calcular a média."""

        with self._lock:
            self._latency_sum[component] += max(0.0, milliseconds)
            self._latency_count[component] += 1

    def snapshot(self) -> dict[str, Any]:
        """Produz uma fotografia segura para o endpoint operacional."""

        with self._lock:
            latencies = {
                name: {
                    "count": self._latency_count[name],
                    "average_ms": round(total / self._latency_count[name], 3),
                }
                for name, total in self._latency_sum.items()
                if self._latency_count[name]
            }
            return {"counters": dict(self._counters), "latencies": latencies}

    def reset(self) -> None:
        """Limpa medições para manter testes independentes."""

        with self._lock:
            self._counters.clear()
            self._latency_sum.clear()
            self._latency_count.clear()


operational_metrics = OperationalMetrics()
