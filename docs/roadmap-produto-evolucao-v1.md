# Roadmap de produto e evolução

## Entregue nesta iteração

- Expansão da base sintética para 70 documentos catalogados, cobrindo os 10 domínios prioritários.
- Reindexação local validada com 250 pontos no Qdrant e 188 chunks no Neo4j.
- Ingestão assíncrona com RabbitMQ, worker, retries e DLQ.
- Status de jobs no Redis.
- Grafo Neo4j com `PolicyVersion`, tópicos, condições, exceções e evidências.
- Validação de tenant no worker e nas consultas do grafo.
- Reprocessamento idempotente do grafo após `skipped` no Qdrant.
- Lifecycle de clientes externos via `lifespan` do FastAPI.
- Prompt versionado em `v2` no código, release, Dockerfile e Compose.
- Respostas grounded condicionadas a evidência acima do limiar configurado.
- Correção de inicialização e clipboard defensivo no frontend.

## Próxima fase: piloto seguro

- OIDC/SSO e RBAC para viajante, gestor, financeiro, administrador e auditor.
- Persistência de feedback, auditoria e métricas fora da memória.
- Rate limiting, revogação de sessão e alertas.
- Readiness separado para consulta e ingestão, incluindo RabbitMQ, Redis, worker e Neo4j.
- Transactional outbox ou reconciliador para eliminar a janela entre Redis e RabbitMQ.
- Lock distribuído por tenant, documento e versão.
- Object storage para substituir o volume compartilhado em múltiplos hosts.
- Secrets, TLS, backups e portas administrativas restritas.

## Qualidade de IA

- Golden dataset com perguntas reais anonimizadas e avaliação humana.
- Testes de condições, exceções, datas, moedas, conflitos e ausência de evidência.
- Modelo de geração mais capaz ou resposta extrativa para fatos críticos.
- Validação de cobertura dos requisitos da pergunta antes da resposta.
- Escalonamento humano quando a evidência for insuficiente ou conflitante.

## Governança de políticas

- Portal de publicação e aprovação.
- Diff entre versões.
- Vigência e expiração programadas.
- Detecção de conflitos.
- Auditoria de autor, aprovador e motivo da alteração.

## GraphRAG

- Usar regras do Neo4j como contexto adicional no `/v1/ask`.
- Combinar relações do grafo com evidências textuais do Qdrant.
- Consultar regras por data, tipo de viagem e exceção.
- Exibir ao usuário a condição que determinou a resposta.

## Métricas de sucesso

- Taxa de respostas corretas por categoria.
- Taxa de recusa correta.
- Taxa de respostas sem evidência.
- Tempo para encontrar uma política.
- Redução de tickets ao Financeiro/Travel.
- Adoção por tenant e persona.
