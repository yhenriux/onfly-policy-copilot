# Biblioteca Técnica

Esta pasta é a biblioteca de referência do Onfly Policy Copilot. Comece pelo índice abaixo conforme a tarefa.

## Por tarefa

| Preciso... | Leia primeiro |
|---|---|
| entender o produto e os limites | [Prova de validação](rag-prova-validacao-tecnica-v1.md) |
| entender a arquitetura | [Arquitetura](rag-arquitetura-explicacao-local-v1.md) |
| acompanhar um fluxo ponta a ponta | [Fluxos operacionais](fluxos-operacionais-v1.md) |
| alterar chunking ou retrieval | [Pipeline RAG](rag-pipeline-explicacao-local-v1.md) e [Guia do código](rag-codigo-navegacao-tecnica-v1.md) |
| alterar copy ou comportamento conversacional | [Especificação de Conversational Design](especificacao-design-conversacional-ux-writing-llm-agentes-v1.md) |
| medir qualidade | [Avaliação e métricas](rag-avaliacao-metricas-qualidade-v1.md) |
| investigar uma falha local | [Operação e incidentes](rag-operacao-procedimento-local-v1.md) |
| publicar ou reverter | [Deploy e rollback](rag-deploy-procedimento-operacao-v1.md) |
| entender uma decisão | [ADRs](adr/) |

## Camadas

1. **Experience:** interface, Conversational Design e UX Writing.
2. **Knowledge:** documentos, normalização, chunking, metadados e embeddings.
3. **Retrieval:** Qdrant, BM25, RRF, reranking e contexto.
4. **Generation:** prompt, structured output, grounding e validação.
5. **Control:** autenticação, tenant isolation, guardrails e autorização.
6. **Quality:** testes, golden dataset, métricas, logs e feedback.
7. **Operations:** Compose, volumes, readiness, migração e rollback.

## Status documental

Documentos com sufixo `v1` são a referência inicial e devem ser atualizados quando uma decisão ou contrato mudar. O README principal aponta para esta biblioteca; o catálogo detalha nomenclatura e responsabilidade de cada arquivo.

## Implementado versus recomendado

A especificação de Conversational Design contém requisitos normativos e uma tabela de implementação atual. Ela não transforma automaticamente uma recomendação em capacidade do produto. Requisitos marcados como `roadmap` ainda precisam de código, teste e decisão de produto.
