# Deploy e rollback

Este procedimento usa imagens identificadas por versão. Rollback significa voltar para a última imagem que passou por testes e health check.

## Deploy local com Compose

1. Inicie o Ollama no computador e confirme os modelos com `ollama list`.
2. Defina `AUTH_TOKEN_SECRET` no arquivo `.env`; não use o valor demonstrativo fora do ambiente local.
3. Execute `docker compose build`.
4. Execute `docker compose up -d`.
5. Carregue os dados com `docker compose exec api python -m scripts.seed_demo`.
6. Confirme `http://localhost:8000/health` e `http://localhost:8000/ready`.

O container acessa o Ollama do computador por `host.docker.internal:11434`. O Qdrant roda no Compose e guarda o índice no volume `qdrant_data`.

## Critério para promover uma versão

- O pipeline de CI está aprovado.
- A imagem possui os labels da aplicação e do prompt.
- `/health` e `/ready` retornam HTTP 200.
- Login e uma pergunta sintética funcionam para cada tenant.
- O gate de regressão e os testes de segurança passaram.

## Rollback

1. Preserve logs, `request_id`, versão da aplicação e versão do prompt.
2. Troque a tag da imagem no Compose para a última versão aprovada.
3. Execute `docker compose up -d --no-deps api`.
4. Confirme `/health`, `/ready`, login e pergunta sintética.
5. Se a falha envolver o índice, siga o procedimento de migração e altere o alias para a coleção anterior.

Nunca apague a imagem ou a coleção anterior antes do fim da janela de observação.

## Simulação versionada

O comando abaixo implanta logicamente uma candidata com health quebrado, detecta a falha e retorna para `0.9.0`:

```powershell
uv run python -m scripts.simulate_rollback
```

O resultado fica em `docs/evidence/phase9_rollback_simulation.json` e pode ser auditado sem alterar um ambiente real.
