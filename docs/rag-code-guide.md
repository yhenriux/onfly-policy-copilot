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

## 8. Guardrails, filtro de conteúdo e alinhamento da resposta

Esta parte protege o fluxo em três momentos: antes da busca, depois da recuperação e antes de devolver a resposta. *Guardrail* é uma regra de proteção que limita comportamentos indesejados; ele não substitui a validação humana nem transforma a demonstração em um sistema de segurança completo.

### Guardrail da pergunta

[`ensure_safe_question`](../app/guardrails/input_guardrail.py#L26) é chamado logo no início de [`AskService.ask`](../app/generation/service.py#L75), antes de gerar embedding ou consultar qualquer documento.

O controle normaliza letras maiúsculas, minúsculas e acentos com [`normalize_security_text`](../app/guardrails/input_guardrail.py#L17). Em seguida, compara a pergunta com padrões conhecidos de tentativa de *prompt injection*, como pedidos para ignorar instruções, revelar o prompt do sistema ou consultar a política de outra empresa.

**Por que funciona:** a pergunta maliciosa é interrompida antes de consumir o modelo ou alcançar a base de conhecimento. O teste [`test_known_prompt_injection_is_blocked_before_embedding`](../tests/security/test_prompt_injection.py#L18) confirma que nem mesmo o embedding é chamado nesses casos.

**Limite consciente:** este é um detector baseado em padrões conhecidos. Ele reduz ataques simples e demonstráveis, mas em produção precisaria ser complementado por monitoramento, revisão contínua de padrões e controles adicionais.

### Filtro de conteúdo recuperado

Documentos também podem conter uma frase que tenta se passar por instrução do sistema. Por isso, [`keep_safe_document_chunks`](../app/guardrails/output_guardrail.py#L26) remove do contexto trechos que contenham padrões maliciosos, como “ignore previous instructions” ou “revele o segredo”.

O filtro é aplicado em [`AskService.ask`](../app/generation/service.py#L75) logo depois da busca e antes da síntese ou geração. Portanto, o conteúdo suspeito não é enviado ao `llama3.2:1b`.

**Por que funciona:** o modelo recebe documentos como dados, não como comandos. Além do filtro, o prompt do sistema estabelece que somente evidências autorizadas podem sustentar a resposta. O teste [`test_malicious_document_instruction_never_reaches_generator`](../tests/security/test_prompt_injection.py#L28) comprova que o gerador não é acionado quando o único trecho recuperado é malicioso.

### Alinhamento com evidências autorizadas

O alinhamento do projeto não depende apenas de uma frase no prompt. Ele combina regras de instrução, validação estrutural e conferência das fontes:

1. [`SYSTEM_PROMPT`](../app/generation/prompts.py#L7) obriga o modelo a usar somente as evidências recebidas, preservar valores e condições e reconhecer ausência de evidência.
2. [`build_user_prompt`](../app/generation/prompts.py#L17) identifica as fontes por posição. Isso permite verificar depois quais trechos foram citados.
3. [`OllamaProvider.generate`](../app/generation/ollama_provider.py#L118) exige saída JSON no formato definido por `GenerationOutput`, validado com Pydantic. Isso evita aceitar texto livre fora do contrato esperado.
4. [`_response_from_generation`](../app/generation/service.py#L129) rejeita citações de posições que não estavam no contexto autorizado.
5. Quando o modelo pequeno responde com baixa confiança ou formato inválido, [`_degraded_response`](../app/generation/service.py#L174) mostra a orientação recuperada em vez de inventar uma interpretação.
6. Quando não existe evidência acima do limite mínimo, [`_response_without_evidence`](../app/generation/service.py#L153) responde sem chamar o gerador.

**Por que funciona:** o modelo não recebe uma pergunta sem contexto, não pode referenciar uma fonte que não recebeu e não é a única barreira contra uma resposta não fundamentada. A aplicação mantém o texto encontrado como fallback controlado.

### Isolamento entre empresas como guardrail de dados

O isolamento também é uma proteção de segurança. [`MockAuthService`](../app/core/auth.py#L30) assina um token que contém a empresa autorizada. A composição em [`_build_ask_service`](../app/main.py#L49) aplica [`TenantGuardedRetriever`](../app/guardrails/tenant_guardrail.py#L20) ao mecanismo de busca.

Esse guardrail exige a empresa antes da busca e confere cada trecho retornado depois dela. Em paralelo, o Qdrant filtra `tenant_id`, `is_active` e `is_deleted` em [`QdrantVectorStore.search`](../app/retrieval/dense.py#L153).

**Por que funciona:** o navegador não escolhe a empresa no corpo da pergunta, a busca não acontece sem empresa autenticada e um resultado de outra empresa interrompe o fluxo. O teste [`test_post_retrieval_validation_blocks_cross_tenant_payload`](../tests/security/test_tenant_isolation.py#L44) valida exatamente esse cenário.

### Resumo dos controles

| Risco | Controle implementado | Código principal |
|---|---|---|
| Pergunta tenta mudar regras do assistente | Normalização e bloqueio por padrões conhecidos | [`input_guardrail.py`](../app/guardrails/input_guardrail.py) |
| Documento tenta virar instrução | Remoção de trechos suspeitos antes do modelo | [`output_guardrail.py`](../app/guardrails/output_guardrail.py) |
| Modelo inventa uma regra | Prompt com evidências, saída estruturada e fallback | [`prompts.py`](../app/generation/prompts.py) e [`service.py`](../app/generation/service.py) |
| Fonte não autorizada é citada | Validação das posições citadas | [`service.py`](../app/generation/service.py#L129) |
| Empresa A acessa documentos da empresa B | Token assinado, filtros no Qdrant e validação dupla | [`auth.py`](../app/core/auth.py), [`dense.py`](../app/retrieval/dense.py) e [`tenant_guardrail.py`](../app/guardrails/tenant_guardrail.py) |

## 9. Como verificar o comportamento

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
