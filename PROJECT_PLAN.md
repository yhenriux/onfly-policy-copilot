# Onfly Policy Copilot — Plano técnico

## 1. Visão

O Onfly Policy Copilot é um case técnico independente que demonstra um assistente B2B multiempresa para consulta de políticas de viagens corporativas, despesas e reembolsos. A solução utiliza exclusivamente dados sintéticos e prioriza respostas fundamentadas, isolamento entre clientes, segurança, avaliação e operação reproduzível.

Pergunta central: como permitir que viajantes e gestores consultem políticas corporativas com rapidez e segurança, mantendo cada resposta rastreável e cada empresa isolada das demais?

## 2. Escopo funcional

### Usuários

- Viajante corporativo.
- Gestor de viagens.
- Gestor financeiro.
- Administrador de políticas.
- Equipe responsável por qualidade e operação.

### Comportamentos obrigatórios

- Responder somente a partir das políticas autorizadas para o tenant autenticado.
- Citar as fontes utilizadas.
- Informar quando não houver evidência suficiente.
- Recusar instruções que tentem alterar as regras do sistema.
- Impedir recuperação de documentos pertencentes a outro tenant.
- Registrar identificador da requisição, latência e componentes utilizados.
- Retornar JSON validado por schema.
- Permitir feedback positivo ou negativo.

### Fora do escopo inicial

- Reservas, cancelamentos ou compras reais.
- Processamento de pagamentos.
- Dados reais de clientes.
- Ações irreversíveis em sistemas externos.
- Fine-tuning.
- Autonomia multiagente em produção.

## 3. Arquitetura-alvo

### Consulta

1. A API recebe a pergunta e o contexto autenticado.
2. Entrada, identidade, tenant e limites são validados.
3. Guardrails verificam prompt injection e conteúdo inadequado.
4. Buscas lexical e vetorial recuperam candidatos autorizados.
5. Reciprocal Rank Fusion combina os rankings.
6. Um re-ranker reordena os melhores candidatos.
7. O sistema monta o contexto dentro do orçamento configurado.
8. O LLM gera uma resposta estruturada e fundamentada.
9. Guardrails de saída validam schema, fontes e suporte documental.
10. A API retorna resposta, fontes, confiança, latência e `request_id`.
11. Logs, métricas e trace registram a execução.

### Ingestão

1. Receber documento e metadados.
2. Validar formato, tenant e versão.
3. Extrair e normalizar texto.
4. Dividir o conteúdo por seções e chunks.
5. Calcular hashes para controle de duplicidade.
6. Gerar embeddings.
7. Indexar vetores e payloads no Qdrant.
8. Alimentar o índice lexical.
9. Registrar versão, data e lineage.
10. Executar testes de recuperação do documento ingerido.

### Componentes planejados

- FastAPI e Pydantic para contrato HTTP e schemas.
- Ollama com `llama3.2:1b` para geração local.
- `all-MiniLM-L6-v2` para embeddings de 384 dimensões.
- Qdrant para persistência e busca vetorial.
- BM25 para recuperação lexical.
- RRF para fusão de rankings.
- CrossEncoder para re-ranking local.
- pytest e httpx para validação automatizada.
- tenacity para retry com backoff.
- Logs estruturados, Prometheus ou OpenTelemetry para operação.
- Docker Compose e CI para reprodutibilidade.
- Front-end demonstrativo para autenticação simulada e uso do assistente.

## 4. Contrato principal

`POST /v1/ask`

Entrada de referência:

```json
{
  "tenant_id": "horizonte_tecnologia",
  "user_id": "user_123",
  "question": "Em quanto tempo devo solicitar o reembolso?"
}
```

Saída de referência:

```json
{
  "answer": "O reembolso deve ser solicitado em até 10 dias úteis.",
  "sources": [
    {
      "document_id": "politica_reembolsos_v1",
      "title": "Política de reembolsos",
      "chunk_id": "chunk_004",
      "score": 0.88
    }
  ],
  "confidence": "high",
  "request_id": "req_abc123",
  "latency_ms": 842
}
```

Endpoints complementares planejados:

- `GET /health`
- `GET /ready`
- `POST /v1/documents`
- `DELETE /v1/documents/{document_id}`
- `POST /v1/feedback`
- `GET /metrics`
- `POST /internal/evaluations/run`

## 5. Fases de execução

### Fase 0 — Fundação

Criar repositório, regras, registro de execução, configuração Python, ambiente seguro, estrutura modular, base funcional e documentação de execução.

**Aceite:** aplicação local reproduzível, Swagger acessível e testes da base passando.

### Fase 1 — Domínio e dados sintéticos

Criar dois tenants fictícios, políticas conflitantes, metadados e perguntas comuns, críticas, sem resposta e adversariais.

**Aceite:** regras conflitantes suficientes para comprovar recuperação correta e isolamento.

### Fase 2 — Ingestão versionada

Separar loading, normalização, chunking, embedding e indexação; adicionar hashes, controle de duplicidade, versão ativa, reindexação e exclusão lógica.

**Aceite:** duas versões de um documento são ingeridas sem duplicidade e somente a versão ativa é recuperada.

### Fase 3 — Recuperação híbrida

Implementar BM25, RRF próprio, pesos configuráveis, filtros obrigatórios por tenant e rastreamento de scores e posições.

**Aceite:** ao menos um caso demonstra melhora do ranking relevante sobre retrievers isolados.

### Fase 4 — Re-ranking e contexto

Aplicar CrossEncoder, remover redundância, controlar orçamento de contexto e comparar qualidade e latência.

**Aceite:** ganho de ranking e custo de latência registrados para sustentar a decisão.

### Fase 5 — Geração e abstração de provedor

Criar interface de provedor, adaptador Ollama, structured output, timeout, retry, fallback, prompt versionado e resposta sem evidência.

**Aceite:** indisponibilidade do modelo produz erro controlado ou degradação sem violar o contrato.

### Fase 6 — Segurança multi-tenant

Obter tenant do contexto autenticado, aplicar filtros em toda busca, validar payloads, detectar prompt injection, mascarar logs e documentar ameaças.

**Aceite:** nenhum caso adversarial recupera conteúdo de outro tenant.

### Fase 7 — Avaliação e regressão

Versionar golden dataset, separar retrieval e geração, medir Recall@k, MRR e nDCG, aplicar rubricas e criar gate de regressão.

Metas iniciais:

- Recall@5 maior ou igual a 0,85.
- Zero vazamento entre tenants.
- Toda resposta factual apresenta fonte autorizada.
- Casos sem evidência resultam em recusa ou sinalização adequada.

**Aceite:** relatório reproduzível compara baseline vetorial, híbrido e híbrido com re-ranking.

### Fase 8 — Observabilidade e confiabilidade

Adicionar `request_id`, logs estruturados, latência por componente, documentos e scores, versões, erros, retries, fallbacks, health, readiness, SLI, SLO e runbook.

**Aceite:** uma requisição pode ser reconstruída pelo trace sem registrar conteúdo sensível desnecessário.

### Fase 9 — Docker, CI/CD e rollback

Criar Dockerfile, Compose, lint, type checking, testes no CI, gates de merge, versionamento, simulação de deploy e rollback e estratégia de migração do índice.

**Aceite:** ambiente limpo sobe pela documentação e o pipeline bloqueia uma regressão proposital.

### Fase 10 — Interface, demonstração e acabamento

Finalizar documentação, seeds, revisões e resultados; implementar um front-end demonstrativo com credenciais mockadas, contexto autenticado do tenant, consulta, fontes, confiança, estados operacionais, feedback e rastreabilidade.

**Aceite:** um avaliador instala, executa, testa e percorre o fluxo completo do usuário até a resposta fundamentada.

### Fase 11 — Apresentação técnica

Consolidar problema, valor, arquitetura, ingestão, retrieval, segurança, avaliação, operação, entrega, demonstração, trade-offs, limitações e roadmap.

**Aceite:** apresentação sustentada por evidéncias reproduzíveis coletadas no projeto.

## 6. Definição de pronto

O case estará pronto quando a API, o Qdrant, o Ollama, os dois tenants, a busca híbrida, o RRF, o re-ranking, as fontes, os guardrails, a avaliação, os testes, o CI, o Docker, os logs, as métricas, o rollback, a documentação e o front-end demonstrativo estiverem integrados e reproduzíveis.

