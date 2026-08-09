# Deploy e rollback

Este procedimento usa imagens identificadas por versão. Rollback significa voltar para a última imagem que passou por testes e health check.

## Deploy local com Compose

1. Inicie o Ollama no computador e confirme os modelos com `ollama list`.
2. Defina `AUTH_TOKEN_SECRET` no arquivo `.env`; não use o valor demonstrativo fora do ambiente local.
3. Execute `docker compose build`.
4. Execute `docker compose up -d`.
5. Carregue os dados com `docker compose exec api python -m scripts.seed_demo`.
6. Confirme `http://localhost:8010/health` e `http://localhost:8010/ready`.

O Compose inicia `api`, `worker`, `rabbitmq`, `redis`, `neo4j` e `qdrant`. API e worker montam o volume `ingestion_data`; RabbitMQ, Redis e Neo4j possuem volumes próprios. Os containers acessam o Ollama do computador por `host.docker.internal:11434`. O Qdrant guarda o índice no volume `qdrant_data`.

O serviço publicado pelo Compose usa `8010:8000`: `8010` é a porta do computador e `8000` é a porta interna da API. A configuração está em [`compose.yaml`](../compose.yaml#L22). O Qdrant não usa healthcheck interno porque a imagem oficial não inclui `wget`; sua disponibilidade deve ser confirmada por `/ready` e pelos logs.

Verifique também:

```powershell
docker compose ps
docker compose logs --tail=100 worker
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
docker compose exec redis redis-cli ping
```

## Critério para promover uma versão

- O pipeline de CI está aprovado.
- A imagem possui os labels da aplicação e do prompt.
- `/health` e `/ready` retornam HTTP 200.
- Login e uma pergunta sintética funcionam para cada tenant.
- Um upload Markdown autenticado retorna `202` e o worker conclui o job.
- `GET /v1/ingestion/{job_id}` retorna `completed` ou `skipped` para o tenant correto.
- O gate de regressão e os testes de segurança passaram.

## Rollback

1. Preserve logs, `request_id`, versão da aplicação e versão do prompt.
2. Troque a tag da imagem no Compose para a última versão aprovada.
3. Execute `docker compose up -d --no-deps api worker`.
4. Confirme `/health`, `/ready`, login, pergunta sintética e o consumo da fila.
5. Se a falha envolver a ingestão, preserve mensagens da DLQ e os estados no Redis antes de reiniciar o worker.
6. Se a falha envolver o índice, siga o procedimento de migração e altere o alias para a coleção anterior.

Nunca apague a imagem ou a coleção anterior antes do fim da janela de observação.

## Simulação versionada

O comando abaixo implanta logicamente uma candidata com health quebrado, detecta a falha e retorna para `0.9.0`:

```powershell
uv run python -m scripts.simulate_rollback
```

O resultado fica em `docs/evidence/phase9_rollback_simulation.json` e pode ser auditado sem alterar um ambiente real.
