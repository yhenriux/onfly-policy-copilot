# Runbook de operação

Este guia explica como verificar e investigar o Onfly Policy Copilot localmente. Runbook é um roteiro curto para agir durante uma falha.

## Indicadores e objetivos

SLI é o indicador realmente medido. SLO é o objetivo esperado para esse indicador. Os objetivos iniciais abaixo valem para uma janela móvel de 30 dias e devem ser recalibrados depois de medições em um ambiente semelhante ao de produção.

| SLI | Como medir | SLO inicial |
|---|---|---|
| Disponibilidade da API | respostas de `/health` com HTTP 200 | 99,5% |
| Prontidão do serviço | respostas de `/ready` com HTTP 200 | 99,0% |
| Erros da API | `errors_total / requests_total` | menor que 1% |
| Latência total | tempo da requisição HTTP | P95 menor que 5 segundos |
| Respostas degradadas | `fallbacks_total / requests_total` | menor que 2% |
| Isolamento | vazamentos entre tenants no gate | exatamente zero |

P95 significa que 95% das requisições devem terminar abaixo do limite. A API atual guarda contagem e média; percentis serão calculados pela plataforma de monitoramento quando houver um ambiente implantado.

## Verificação rápida

1. Abra `GET /health` em `http://localhost:8010` no Compose ou em `http://localhost:8000` com Uvicorn. Se falhar, o processo da API não está acessível.
2. Abra `GET /ready`. O corpo informa separadamente `ollama` e `qdrant`. RabbitMQ, Redis, Neo4j e worker são dependências do fluxo de ingestão e devem ser verificados com `docker compose ps`.
3. Abra `GET /metrics`. Compare erros, retries, fallbacks, volume e latências.
4. Copie o `X-Request-ID` da resposta ou o `request_id` do JSON.
5. Procure esse identificador nos eventos `http_request` e `rag_trace`.
6. Na interface, confira se o indicador superior representa o mesmo estado de `/ready`.

## Investigação por sintoma

### API indisponível

- Confirme se o processo `uvicorn` está em execução.
- Leia o último erro de inicialização.
- Valide as configurações com `uv run python -c "from app.core.config import Settings; print(Settings())"`.

### Ollama indisponível

- Confirme `ollama list` e a presença de `llama3.2:3b` e `all-minilm`.
- Teste `http://localhost:11434/api/tags`.
- Observe `retries_total`, `fallbacks_total` e `ollama_generation` em `/metrics`.
- Reinicie o Ollama somente depois de guardar o `request_id` e os logs do caso.

### Qdrant indisponível

- Confirme o caminho `QDRANT_PATH` e a coleção configurada.
- Execute novamente a ingestão somente se a coleção estiver ausente.
- Não apague a pasta local durante a investigação; ela contém o índice persistido.

### Ingestão parada ou job pendente

- Consulte `GET /v1/ingestion/{job_id}` e registre o `request_id`.
- Veja `docker compose logs --tail=200 worker` e procure o `job_id`.
- Verifique `docker compose ps rabbitmq redis worker`.
- Consulte a fila em `http://localhost:15672` usando as credenciais locais do RabbitMQ.
- Se houver erro transitório no Ollama ou Qdrant, corrija a dependência e aguarde os retries do worker.
- Se o job estiver na dead-letter queue, preserve a mensagem antes de reprocessar manualmente.
- Se o RabbitMQ estiver indisponível durante um retry ou envio para a DLQ, a mensagem original permanece sujeita a reentrega; confirme a recuperação do broker antes de investigar perda de job.
- Não apague o diretório correspondente no volume `ingestion_data` enquanto o job estiver em `queued` ou `processing`.

### Redis indisponível

- Confirme `docker compose exec redis redis-cli ping`.
- O endpoint de status pode retornar `503`, mesmo que a fila esteja funcionando.
- Não trate a ausência do status como confirmação de que o job falhou; verifique RabbitMQ e os logs do worker.

### Latência alta

- Compare `retrieval`, `reranking`, `ollama_embedding`, `ollama_generation` e `total` no trace.
- Se o re-ranking dominar, verifique partida fria e carga do CrossEncoder.
- Se o Ollama dominar, verifique retries, uso de CPU e memória.
- Se retrieval dominar, confirme o tamanho da coleção e o filtro de tenant.
- A primeira consulta pode carregar o CrossEncoder; faça um aquecimento antes da demonstração.

### Front-end não abre

- Confirme `GET /health` e abra a raiz `/`, não apenas `/docs`.
- Confirme que `app/web/index.html` e `app/web/static` existem no artefato.
- Recarregue a página; a sessão em memória será reiniciada.

### Suspeita de vazamento

- Interrompa a demonstração e preserve o `request_id`.
- Confira o tenant do token e todos os documentos do `rag_trace`.
- Execute `uv run pytest tests/security` e o gate de regressão.
- Não registre token, pergunta ou dados pessoais no relato do incidente.

## Encerramento

Registre horário, impacto, `request_id`, dependência afetada, causa, correção e teste usado para confirmar a recuperação. Uma falha só é encerrada quando `/ready` volta a HTTP 200 e uma pergunta sintética autorizada termina sem vazamento.
