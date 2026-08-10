# Fluxos Operacionais do Sistema

Este documento conecta Produto, UX, IA e Engenharia por meio dos fluxos reais do projeto.

## 1. Ingestão e indexação

```mermaid
flowchart TD
    A[Documento ou catálogo] --> B[Loader e manifesto]
    B --> C[Normalização NFC e limpeza]
    C --> D[Estrutura título / seção]
    D --> E[Chunking semântico com overlap]
    E --> F[Metadados tenant / versão / hashes]
    F --> G[Embedding com all-minilm]
    G --> H[Qdrant phase3]
    H --> I[Neo4j opcional]
    I --> J[Resultado indexed ou skipped]
```

**Código:** `app/ingestion`, `scripts/seed_demo.py`, `app/retrieval/dense.py`.

**Contrato:** uma versão idêntica é `skipped`; uma versão alterada com o mesmo identificador é conflito; uma nova coleção deve ser usada quando o contrato de chunking mudar.

## 2. Consulta e retrieval

```mermaid
flowchart LR
    A[Pergunta] --> B[Input guardrail]
    B --> C[Rewrite de termos frequentes]
    C --> D[Embedding da pergunta]
    C --> E[BM25 lexical]
    D --> F[Busca vetorial tenant-scoped]
    E --> G[RRF híbrido]
    F --> G
    G --> H[CrossEncoder reranking]
    H --> I[Remoção de redundância]
    I --> J[Contexto final]
```

**Código:** `app/generation/service.py`, `app/retrieval/hybrid.py`, `app/retrieval/fusion.py`, `app/retrieval/reranker.py`, `app/retrieval/context.py`.

**Regra:** `tenant_id` é filtro de autorização no backend; não é uma instrução delegada ao modelo.

## 3. Geração grounded

```mermaid
flowchart TD
    A[Contexto final] --> B[Extração de fatos]
    B --> C[Prompt com fatos e evidências]
    C --> D[LangChain Ollama / llama3.2:3b]
    D --> E{JSON válido?}
    E -- não --> F[Retry controlado]
    E -- sim --> G{Citou fonte?}
    G -- sim --> H[Validação de posição e suporte]
    G -- não --> I[Citation repair]
    I --> H
    H -- suportado --> J[Resposta gerada + fontes]
    H -- não suportado --> K[Resposta factual estruturada]
    K --> L[Confiança medium e status degraded]
```

**Código:** `app/generation/prompts.py`, `app/generation/grounded_answers.py`, `app/generation/langchain_ollama_provider.py`, `app/generation/service.py`.

## 4. Resposta HTTP e experiência

```mermaid
sequenceDiagram
    participant U as Usuário
    participant UI as Interface
    participant API as FastAPI
    participant RAG as AskService
    participant LLM as Ollama
    U->>UI: envia pergunta
    UI->>API: POST /v1/ask + Bearer + session id
    API->>RAG: valida tenant e pergunta
    RAG->>LLM: envia contexto autorizado
    LLM-->>RAG: resposta estruturada
    RAG-->>API: resposta, fontes, confiança e trace
    API-->>UI: JSON validado
    UI->>U: mostra conclusão, fonte e próximo passo
```

## 5. Segurança

```mermaid
flowchart TD
    A[Token Bearer] --> B[AuthenticatedContext]
    B --> C[TenantGuardedRetriever]
    C --> D[Qdrant filter tenant]
    D --> E[Output guardrail]
    E --> F[Prompt com documentos como dados]
    F --> G[Structured output validator]
    G --> H[Resposta autorizada]
```

## 6. Observabilidade

```mermaid
flowchart LR
    A[HTTP middleware] --> B[request counter]
    C[AskService] --> D[latências por etapa]
    C --> E[trace de documentos]
    C --> F[ObservabilityStore SQLite]
    B --> G[/metrics Prometheus]
    D --> G
    E --> H[/observability/responses]
    F --> H
    H --> I[/metrics/ui]
```

## 7. Avaliação

```mermaid
flowchart TD
    A[Golden dataset] --> B[Dense retrieval]
    A --> C[Hybrid retrieval]
    A --> D[Reranked context]
    B --> E[Recall / MRR / NDCG]
    C --> E
    D --> E
    D --> F[Generation correctness]
    D --> G[Source adherence]
    E --> H[Regression gate]
    F --> H
    G --> H
```

## 8. Deploy local e rollback

```mermaid
flowchart TD
    A[git revision] --> B[Docker build api / worker]
    B --> C[Compose up]
    C --> D[health e readiness]
    D --> E[seed phase3]
    E --> F[golden evaluation]
    F -- aprovado --> G[teste manual]
    F -- reprovado --> H[rollback imagem ou coleção]
```

## 9. Fluxo de uma falha

```mermaid
flowchart TD
    A[Resposta inesperada] --> B[request_id]
    B --> C[Trace individual]
    C --> D[Separar retrieval / generation / UI]
    D --> E{Fonte correta?}
    E -- não --> F[Corrigir conteúdo ou índice]
    E -- sim --> G{Resposta correta?}
    G -- não --> H[Corrigir prompt, modelo ou síntese factual]
    G -- sim --> I{Interface correta?}
    I -- não --> J[Corrigir UX e estado visual]
    I -- sim --> K[Adicionar caso de regressão]
```
