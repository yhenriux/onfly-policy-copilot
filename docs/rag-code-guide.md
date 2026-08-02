# Guia do código RAG

Este guia conecta cada etapa do RAG aos arquivos que a implementam. Ele foi escrito para que uma pessoa avaliadora possa entender o fluxo e chegar rapidamente ao código responsável por cada decisão.

RAG significa *Retrieval-Augmented Generation*: a aplicação recupera evidências da base antes de responder. O fluxo completo é montado em [`app/main.py`](../app/main.py#L49), na função `_build_ask_service`.

## Mapa rápido

| Etapa | Onde está no código | Por que existe |
|---|---|---|
| Carregar documentos | [`scripts/seed_demo.py`](../scripts/seed_demo.py) e [`app/ingestion/loaders.py`](../app/ingestion/loaders.py) | Lê políticas e catálogos de dúvidas das duas empresas sintéticas. |
| Normalizar e dividir | [`app/ingestion/normalizer.py`](../app/ingestion/normalizer.py) e [`app/ingestion/chunker.py`](../app/ingestion/chunker.py#L89) | Prepara trechos consistentes, com seção e contexto. |
| Gerar embeddings | [`app/ingestion/embeddings.py`](../app/ingestion/embeddings.py#L15) e [`app/generation/ollama_provider.py`](../app/generation/ollama_provider.py#L103) | Permite buscar por significado, e não apenas por palavras idênticas. |
| Indexar no Qdrant | [`app/ingestion/pipeline.py`](../app/ingestion/pipeline.py) e [`app/retrieval/dense.py`](../app/retrieval/dense.py#L84) | Persiste vetores e metadados com versão, empresa e estado ativo. |
| Buscar por significado | [`app/retrieval/dense.py`](../app/retrieval/dense.py#L153) | Recupera vetores próximos, filtrados pela empresa autorizada. |
| Buscar por palavras | [`app/retrieval/lexical.py`](../app/retrieval/lexical.py#L63) | Complementa a busca vetorial quando termos específicos são importantes. |
| Combinar resultados | [`app/retrieval/hybrid.py`](../app/retrieval/hybrid.py#L28) e [`app/retrieval/fusion.py`](../app/retrieval/fusion.py#L8) | Usa os dois sinais de busca sem depender de somente um deles. |
| Reordenar por relevância | [`app/retrieval/reranker.py`](../app/retrieval/reranker.py#L31) | Compara pergunta e trecho diretamente para priorizar a melhor evidência. |
| Controlar contexto | [`app/retrieval/context.py`](../app/retrieval/context.py#L18) | Evita repetir texto e ultrapassar o limite enviado ao modelo. |
| Gerar resposta segura | [`app/generation/service.py`](../app/generation/service.py#L75) | Coordena segurança, retrieval, geração, fallback e fontes. |
| Sintetizar perguntas frequentes | [`app/generation/grounded_answers.py`](../app/generation/grounded_answers.py#L59) | Produz respostas claras usando somente as fontes recuperadas. |
| Isolar empresas | [`app/guardrails/tenant_guardrail.py`](../app/guardrails/tenant_guardrail.py#L20) | Exige a empresa do token antes da busca e confere os resultados depois dela. |

## 1. Ingestão: do documento ao trecho pesquisável

O comando [`scripts/seed_demo.py`](../scripts/seed_demo.py) localiza os manifestos de política e os catálogos de dúvidas, monta o provedor Ollama, cria a configuração de chunking e chama `ingest_document` para cada documento.

O encadeamento principal está em [`app/ingestion/pipeline.py`](../app/ingestion/pipeline.py):

```text
normalize_document
       ↓
chunk_by_section
       ↓
embed_chunks
       ↓
index_chunks
```

Antes de processar um documento, `ingest_document` consulta os hashes já armazenados. Um conteúdo idêntico é ignorado; uma mesma versão com conteúdo diferente é recusada. Isso evita duplicação acidental e protege o histórico de versões.

### Como o chunking funciona

A função [`chunk_by_section`](../app/ingestion/chunker.py#L89) procura títulos Markdown de nível `##` até `####`. Ela conserva o caminho da seção, por exemplo `Hospedagem > Limites`, e cria `DocumentChunk` com título, versão, seção, posição e hashes.

Quando uma seção é longa, [`_split_with_overlap`](../app/ingestion/chunker.py#L53) agrupa parágrafos e frases completas até o limite configurado. O final de um trecho reaparece parcialmente no início do próximo. Essa sobreposição reduz o risco de uma regra ficar separada da condição que dá sentido a ela.

Os valores padrão ficam em [`app/core/config.py`](../app/core/config.py#L56):

- `chunk_max_chars = 800`: tamanho máximo aproximado de cada trecho;
- `chunk_overlap_chars = 120`: quantidade máxima de contexto reaproveitado;
- as validações impedem sobreposição maior ou igual ao próprio trecho.

Esse desenho funciona porque evita cortes arbitrários no meio de frases e mantém a seção ao lado do texto que será indexado.

## 2. Embeddings: transformar sentido em vetores

Em [`embed_chunks`](../app/ingestion/embeddings.py#L15), o texto enviado ao modelo inclui três partes:

```text
título do documento
seção do documento
texto do trecho
```

Incluir título e seção melhora a representação de contexto. Um trecho que menciona apenas “R$ 480” não perde a ligação com “Hospedagem” ou com a empresa e a versão corretas.

O método [`OllamaProvider.embed`](../app/generation/ollama_provider.py#L103) envia esses textos ao endpoint local `/api/embed` do Ollama. O modelo configurado é `all-minilm`, definido em [`app/core/config.py`](../app/core/config.py#L34). O retorno é uma lista de vetores numéricos, um para cada trecho.

Na pergunta, [`AskService.ask`](../app/generation/service.py#L75) usa o mesmo provedor para gerar o vetor da consulta. Como documentos e pergunta são representados no mesmo espaço numérico, o Qdrant consegue encontrar trechos semanticamente próximos.

## 3. Índice vetorial, versões e filtro por empresa

[`index_chunks`](../app/ingestion/indexer.py#L7) cria a coleção quando necessário, desativa versões anteriores do mesmo documento e grava a versão atual.

O método [`QdrantVectorStore.upsert`](../app/retrieval/dense.py#L84) persiste cada vetor junto com metadados: `tenant_id`, `document_id`, título, versão, validade, seção, texto, hashes, `is_active` e `is_deleted`.

Na busca, [`QdrantVectorStore.search`](../app/retrieval/dense.py#L153) exige um `tenant_id` e aplica três filtros ao mesmo tempo:

- empresa autorizada;
- versão ativa;
- documento não excluído logicamente.

Isso explica por que uma regra inativa ou de outra empresa não deve aparecer na resposta.

## 4. Busca híbrida: significado e termos importantes

[`HybridRetriever.search`](../app/retrieval/hybrid.py#L28) realiza duas buscas no mesmo contexto de empresa:

1. A busca densa do Qdrant usa o vetor da pergunta para procurar semelhança de significado.
2. [`BM25Retriever.search`](../app/retrieval/lexical.py#L69) procura termos presentes na pergunta nos textos ativos da empresa.

Depois, [`reciprocal_rank_fusion`](../app/retrieval/fusion.py#L8) aplica RRF (*Reciprocal Rank Fusion*). Em vez de comparar diretamente escalas de pontuação diferentes, o RRF considera a posição de cada trecho nas duas listas. Um trecho bem colocado nas duas buscas ganha mais força.

Essa combinação funciona especialmente bem em políticas: a busca vetorial entende variações como “posso levar mala?” e “bagagem despachada”, enquanto o BM25 preserva termos precisos como nomes de comprovantes, siglas ou limites.

## 5. Re-ranking: escolher melhor entre bons candidatos

A busca híbrida devolve candidatos promissores, mas ainda não decidiu qual explica melhor a pergunta. [`ContextualRetriever.search`](../app/retrieval/contextual.py#L31) envia esses candidatos ao re-ranking.

[`LocalCrossEncoderReranker.rerank`](../app/retrieval/reranker.py#L31) monta pares de `pergunta + trecho` e usa o modelo configurado em `cross_encoder_model`. Diferentemente da busca vetorial, ele lê os dois textos juntos e atribui uma pontuação específica para aquele par.

Os candidatos são ordenados por essa pontuação. Na sequência, [`select_context`](../app/retrieval/context.py#L18) elimina textos muito parecidos e respeita o orçamento de caracteres. O resultado é um contexto menor, mais diverso e mais relevante para a resposta.

O re-ranking funciona porque atua depois da busca ampla: primeiro a aplicação encontra possibilidades rapidamente; depois usa uma comparação mais criteriosa somente nos melhores candidatos.

## 6. Resposta, segurança e fallback

[`AskService.ask`](../app/generation/service.py#L75) é o orquestrador da consulta. Sua sequência é:

```text
validar pergunta
       ↓
expandir termos de perguntas frequentes
       ↓
gerar embedding da pergunta
       ↓
buscar, reordenar e selecionar contexto
       ↓
confirmar isolamento e filtrar conteúdo inseguro
       ↓
sintetizar resposta fundamentada ou chamar o modelo gerador
       ↓
devolver fontes, confiança e request_id
```

Para bagagem, hospedagem, reembolso e transporte local, [`build_grounded_answer`](../app/generation/grounded_answers.py#L59) seleciona os trechos do assunto recuperados e os organiza em linguagem direta. [`rewrite_frequent_question`](../app/generation/grounded_answers.py#L88) adiciona termos de política à consulta interna, sem mudar a pergunta mostrada à pessoa usuária.

Nas demais perguntas, [`OllamaProvider.generate`](../app/generation/ollama_provider.py#L118) chama `llama3.2:1b` com temperatura zero e exige JSON validado por Pydantic. Caso falte evidência, o modelo esteja indisponível ou devolva um formato inválido, o serviço retorna uma resposta controlada, sem inventar uma política.

## 7. Onde o isolamento é conferido

O token autenticado é transformado em contexto no fluxo HTTP. A composição do retriever em [`_build_ask_service`](../app/main.py#L49) embrulha a busca com `TenantGuardedRetriever`.

[`TenantGuardedRetriever.search`](../app/guardrails/tenant_guardrail.py#L20) confirma que existe empresa autenticada antes de buscar e verifica que todos os trechos recebidos pertencem à mesma empresa depois da busca. [`AskService.ask`](../app/generation/service.py#L75) repete essa conferência como defesa adicional.

## 8. Como verificar o comportamento

| O que validar | Testes relacionados |
|---|---|
| Chunking por seção, tamanho e sobreposição | [`tests/unit/test_chunker.py`](../tests/unit/test_chunker.py) |
| Embeddings e contrato do Ollama | [`tests/unit/test_ollama_provider.py`](../tests/unit/test_ollama_provider.py) e [`tests/integration/test_ingestion_pipeline.py`](../tests/integration/test_ingestion_pipeline.py) |
| BM25 e RRF | [`tests/unit/test_lexical_retrieval.py`](../tests/unit/test_lexical_retrieval.py) e [`tests/unit/test_fusion.py`](../tests/unit/test_fusion.py) |
| CrossEncoder e contexto não redundante | [`tests/unit/test_reranker.py`](../tests/unit/test_reranker.py) e [`tests/unit/test_contextual_retriever.py`](../tests/unit/test_contextual_retriever.py) |
| Respostas frequentes fundamentadas | [`tests/unit/test_grounded_answers.py`](../tests/unit/test_grounded_answers.py) |
| Isolamento entre empresas | [`tests/security/test_tenant_isolation.py`](../tests/security/test_tenant_isolation.py) |

Execute a suíte completa com:

```powershell
uv run pytest
```

O conjunto de avaliações reproduzíveis está documentado em [Plano e métricas de avaliação](evaluation-plan.md).
