# Integração de LangChain, LangGraph, LangSmith e LlamaIndex

## Decisão

O projeto mantém suas regras próprias de RAG e usa os frameworks como camadas de integração, orquestração e observabilidade. Busca híbrida, RRF, CrossEncoder, filtros por empresa e guardrails não foram substituídos.

## LangChain

[`app/generation/langchain_ollama_provider.py`](../app/generation/langchain_ollama_provider.py) implementa o contrato interno de provedor usando `ChatOllama` e `OllamaEmbeddings`. Ele mantém os modelos locais `llama3.2:1b` e `all-minilm`, mas passa a usar as interfaces intercambiáveis do LangChain.

O seletor `LLM_INTEGRATION` permite escolher `langchain` (padrão) ou `http` (adaptador HTTP anterior). Essa escolha é feita em [`app/main.py`](../app/main.py). O contrato `GenerationProvider` continua protegendo o restante do sistema contra mudanças de fornecedor.

## LlamaIndex

[`app/retrieval/dense.py`](../app/retrieval/dense.py) usa `Document` e `TextNode` do LlamaIndex para representar cada trecho de política e o adaptador oficial `QdrantVectorStore` para gravar e consultar vetores no Qdrant. Os metadados preservam empresa, documento, versão, seção, validade e estado do conteúdo.

O filtro da empresa continua obrigatório dentro da consulta vetorial. BM25, RRF, CrossEncoder, guardrails e a resposta final permanecem no código próprio do projeto, pois são regras de segurança e qualidade que não devem ser delegadas ao framework.

## LangGraph

[`app/orchestration/rag_graph.py`](../app/orchestration/rag_graph.py) cria um fluxo determinístico com dois nós:

```text
validar pergunta → responder com RAG existente
```

O grafo não cria um agente autônomo e não executa ferramentas externas. Ele torna o fluxo explícito e prepara o projeto para checkpoints e aprovação humana quando houver ações sensíveis no futuro. `WORKFLOW_ENGINE=langgraph` é o padrão; `service` preserva o caminho anterior para comparação.

## LangSmith

[`app/observability/langsmith.py`](../app/observability/langsmith.py) ativa tracing remoto somente quando `LANGSMITH_TRACING=true` e uma chave válida é fornecida. Por padrão, ele permanece desligado para que perguntas, documentos e traces sintéticos não saiam do ambiente local.

```text
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=onfly-policy-copilot
```

Antes de ativar LangSmith com dados reais, é necessário revisar privacidade, mascaramento, retenção, acesso à conta e custo.

## Verificação

Os testes [`tests/unit/test_langgraph_workflow.py`](../tests/unit/test_langgraph_workflow.py) e [`tests/unit/test_langsmith_configuration.py`](../tests/unit/test_langsmith_configuration.py) validam o bloqueio de prompt injection no grafo e a ativação explícita do tracing. Os contratos HTTP existentes continuam cobertos pelos testes de integração.
