# Guia do código RAG

Este guia conecta cada etapa do RAG aos arquivos que a implementam. Ele foi escrito para que uma pessoa avaliadora possa entender o fluxo e chegar rapidamente ao código responsável por cada decisão.

RAG significa *Retrieval-Augmented Generation*: a aplicação recupera evidências da base antes de responder. O fluxo completo é montado em [`app/main.py`](../app/main.py#L49), na função `_build_ask_service`.

## Mapa rápido

| Etapa | Onde está no código | Por que existe |
|---|---|---|
| Carregar documentos | [`scripts/seed_demo.py`](../scripts/seed_demo.py) e [`app/ingestion/loaders.py`](../app/ingestion/loaders.py) | Lê políticas e catálogos de dúvidas das duas empresas sintéticas. |
| Receber ingestão | [`app/main.py`](../app/main.py) | Recebe o Markdown, grava o manifesto no volume compartilhado e retorna `202 Accepted`. |
| Publicar job | [`app/messaging/rabbitmq.py`](../app/messaging/rabbitmq.py) e [`app/messaging/schemas.py`](../app/messaging/schemas.py) | Declara a fila durável e publica o contrato versionado do job. |
| Processar job | [`app/worker/ingestion_worker.py`](../app/worker/ingestion_worker.py) | Consome jobs, executa o pipeline e aplica retry/DLQ. |
| Consultar status | [`app/messaging/redis_store.py`](../app/messaging/redis_store.py) e [`app/main.py`](../app/main.py) | Persiste estados com TTL e protege a consulta pelo tenant. |
| Construir grafo | [`app/knowledge_graph/extractor.py`](../app/knowledge_graph/extractor.py) e [`app/knowledge_graph/neo4j_repository.py`](../app/knowledge_graph/neo4j_repository.py) | Extrai fatos auditáveis, mantém somente a versão ativa e grava políticas, regras e evidências no Neo4j. |
| Normalizar e dividir | [`app/ingestion/normalizer.py`](../app/ingestion/normalizer.py) e [`app/ingestion/chunker.py`](../app/ingestion/chunker.py#L89) | Prepara trechos consistentes, com seção e contexto. |
| Gerar embeddings | [`app/ingestion/embeddings.py`](../app/ingestion/embeddings.py#L15) e [`app/generation/ollama_provider.py`](../app/generation/ollama_provider.py#L103) | Permite buscar por significado, e não apenas por palavras idênticas. |
| Indexar no Qdrant | [`app/ingestion/pipeline.py`](../app/ingestion/pipeline.py) e [`app/retrieval/dense.py`](../app/retrieval/dense.py#L141) | Persiste vetores e metadados com versão, empresa e estado de busca. |
| Buscar por significado | [`app/retrieval/dense.py`](../app/retrieval/dense.py#L188) | Recupera vetores próximos, filtrados pela empresa autorizada. |
| Buscar por palavras | [`app/retrieval/lexical.py`](../app/retrieval/lexical.py#L63) | Complementa a busca vetorial quando termos específicos são importantes. |
| Combinar resultados | [`app/retrieval/hybrid.py`](../app/retrieval/hybrid.py#L28) e [`app/retrieval/fusion.py`](../app/retrieval/fusion.py#L8) | Usa os dois sinais de busca sem depender de somente um deles. |
| Reordenar por relevância | [`app/retrieval/reranker.py`](../app/retrieval/reranker.py#L31) | Compara pergunta e trecho diretamente para priorizar a melhor evidência. |
| Controlar contexto | [`app/retrieval/context.py`](../app/retrieval/context.py#L18) | Evita repetir texto e ultrapassar o limite enviado ao modelo. |
| Gerar resposta segura | [`app/generation/service.py`](../app/generation/service.py#L75) | Coordena segurança, retrieval, geração, fallback e fontes. |
| Reescrever perguntas frequentes | [`app/generation/grounded_answers.py`](../app/generation/grounded_answers.py#L88) | Amplia a consulta de busca com termos de política, sem mudar a pergunta mostrada. |
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

O método [`QdrantVectorStore.upsert`](../app/retrieval/dense.py#L141) persiste cada vetor junto com metadados: `tenant_id`, `policy_document_id`, título, versão, validade, seção, texto, hashes, `search_status` e `deletion_status`.

Na busca, [`QdrantVectorStore.search`](../app/retrieval/dense.py#L188) exige um `tenant_id` e aplica filtros de tenant, documento, `search_status` e `deletion_status`.

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
gerar resposta pelo modelo generativo com as fontes autorizadas
       ↓
devolver fontes, confiança e request_id
```

Com evidência acima do limiar, a resposta passa por fatos extraídos, geração via [`OllamaProvider.generate`](../app/generation/ollama_provider.py#L118) ou LangChain e validação JSON com `llama3.2:3b`. Se o modelo recusar uma fonte suficiente, a camada factual organiza a evidência em modo degradado. [`rewrite_frequent_question`](../app/generation/grounded_answers.py#L88) adiciona termos de política à consulta interna.

Caso falte evidência, o modelo esteja indisponível ou devolva um formato inválido, o serviço retorna uma resposta controlada, mostrando a fonte autorizada sem inventar uma política.

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

O filtro é aplicado em [`AskService.ask`](../app/generation/service.py#L75) logo depois da busca e antes da geração. Portanto, o conteúdo suspeito não é enviado ao `llama3.2:3b`.

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

Esse guardrail exige a empresa antes da busca e confere cada trecho retornado depois dela. Em paralelo, o Qdrant filtra `tenant_id`, `search_status` e `deletion_status` em [`QdrantVectorStore.search`](../app/retrieval/dense.py#L188).

**Por que funciona:** o navegador não escolhe a empresa no corpo da pergunta, a busca não acontece sem empresa autenticada e um resultado de outra empresa interrompe o fluxo. O teste [`test_post_retrieval_validation_blocks_cross_tenant_payload`](../tests/security/test_tenant_isolation.py#L44) valida exatamente esse cenário.

### Resumo dos controles

| Risco | Controle implementado | Código principal |
|---|---|---|
| Pergunta tenta mudar regras do assistente | Normalização e bloqueio por padrões conhecidos | [`input_guardrail.py`](../app/guardrails/input_guardrail.py) |
| Documento tenta virar instrução | Remoção de trechos suspeitos antes do modelo | [`output_guardrail.py`](../app/guardrails/output_guardrail.py) |
| Modelo inventa uma regra | Prompt com evidências, saída estruturada e fallback | [`prompts.py`](../app/generation/prompts.py) e [`service.py`](../app/generation/service.py) |
| Fonte não autorizada é citada | Validação das posições citadas | [`service.py`](../app/generation/service.py#L129) |
| Empresa A acessa documentos da empresa B | Token assinado, filtros no Qdrant e validação dupla | [`auth.py`](../app/core/auth.py), [`dense.py`](../app/retrieval/dense.py) e [`tenant_guardrail.py`](../app/guardrails/tenant_guardrail.py) |

## 9. Integração de APIs de IA, riscos e opções de execução

O projeto possui uma integração de IA efetivamente implementada: o **Ollama**, executado localmente. Ele atende a duas necessidades diferentes do RAG: criar embeddings e gerar respostas. O Qdrant também é acessado por API, mas é um banco vetorial, não um modelo de IA.

### APIs utilizadas hoje

| Serviço | Chamadas usadas | Finalidade no projeto | Onde está no código |
|---|---|---|---|
| Ollama | `POST /api/embed` | Cria embeddings com `all-minilm` para documentos e perguntas. | [`OllamaProvider.embed`](../app/generation/ollama_provider.py#L103) |
| Ollama | `POST /api/chat` | Gera resposta estruturada com `llama3.2:3b` para toda pergunta com evidência suficiente. | [`OllamaProvider.generate`](../app/generation/ollama_provider.py#L118) |
| Qdrant | cliente Python do Qdrant | Grava vetores e pesquisa documentos por semelhança. | [`QdrantVectorStore`](../app/retrieval/dense.py#L19) |
| FastAPI | `/v1/auth/login`, `/v1/ask` e demais rotas | Expõe a API do próprio projeto para a interface e para testes. | [`app/main.py`](../app/main.py) |

[`OllamaProvider`](../app/generation/ollama_provider.py#L32) é o adaptador da integração. Ele centraliza endereço, timeout, tentativas e conversão das respostas HTTP para os modelos internos. Portanto, o restante da aplicação não depende diretamente de endpoints do Ollama.

### Como a integração funciona

1. [`Settings`](../app/core/config.py#L11) lê `OLLAMA_BASE_URL`, modelos, timeout e tentativas do arquivo `.env`.
2. [`_build_ask_service`](../app/main.py#L49) cria uma instância de `OllamaProvider` e a entrega ao serviço de perguntas.
3. Na ingestão, [`embed_chunks`](../app/ingestion/embeddings.py#L15) envia título, seção e texto para `/api/embed`.
4. Na consulta, [`AskService.ask`](../app/generation/service.py#L75) gera o embedding da pergunta, faz o retrieval e só então chama a geração quando necessário.
5. [`OllamaProvider.generate`](../app/generation/ollama_provider.py#L118) pede JSON compatível com `GenerationOutput`; a validação rejeita uma resposta fora do formato esperado.

O contrato [`GenerationProvider`](../app/generation/provider.py#L22) define o mínimo que qualquer provedor precisa oferecer: `embed`, `generate`, nome do provedor, modelo e versão de prompt. Isso mantém Ollama substituível sem alterar chunking, retrieval, guardrails ou a API pública.

### Reprodução local e self-hosted

O modo atual já é **self-hosted local**: os modelos rodam no computador, sem enviar perguntas e documentos para uma API comercial.

```powershell
ollama pull llama3.2:3b
ollama pull all-minilm
uv sync --dev
Copy-Item .env.example .env
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload
```

O endereço padrão é `http://localhost:11434`, configurado em [`.env.example`](../.env.example). Para rodar em um servidor próprio, o mesmo desenho pode ser usado com:

- Ollama em uma máquina ou container privado;
- API FastAPI em container;
- Qdrant em disco local ou em um serviço Qdrant privado;
- rede interna entre API, Ollama e Qdrant, sem expor o endpoint do modelo à internet pública.

Para Qdrant remoto, o projeto já oferece `QDRANT_MODE=server`, `QDRANT_URL` e `QDRANT_API_KEY`. A chave deve ficar apenas no `.env` ou no cofre de segredos do ambiente, nunca no repositório. Para a ingestão assíncrona, `RABBITMQ_URL`, `REDIS_URL` e `INGESTION_STORAGE_PATH` cumprem o mesmo papel de configuração externa.

### Caminho para uma execução hospedada em nuvem

O repositório **não integra atualmente** OpenAI, Anthropic, Gemini, Bedrock, Vertex AI ou Azure OpenAI. A arquitetura, porém, foi preparada para essa troca por meio de `GenerationProvider`. RabbitMQ e Redis não substituem o provedor de IA: coordenam o processamento assíncrono e o estado da ingestão.

Para adicionar um provedor em nuvem, o passo responsável seria:

1. criar, por exemplo, `app/generation/cloud_provider.py` implementando `GenerationProvider`;
2. implementar `embed` e `generate` com a API oficial escolhida;
3. guardar chave e endpoint em variáveis de ambiente ou em um cofre de segredos;
4. selecionar o provedor na composição em [`_build_ask_service`](../app/main.py#L49), sem alterar `AskService`;
5. manter o mesmo contrato de saída, timeout, retry, fontes autorizadas e testes;
6. implantar a API em ambiente privado, com Qdrant gerenciado ou privado e observabilidade centralizada.

Essa separação evita reescrever o pipeline quando houver uma decisão de fornecedor. Ela também permite comparar modelos locais e hospedados sob as mesmas métricas de qualidade, latência e custo.

### Riscos da integração e controles atuais

| Risco | Impacto possível | Controle presente | Próximo controle para nuvem |
|---|---|---|---|
| Indisponibilidade ou lentidão do modelo | Falha ou demora na resposta | Timeout, retry com espera progressiva e fallback em [`ollama_provider.py`](../app/generation/ollama_provider.py#L62) | Health check externo, autoscaling e alertas. |
| Resposta fora do formato | Interface ou API recebem dados inválidos | Schema Pydantic e saída estruturada em [`generate`](../app/generation/ollama_provider.py#L118) | Testes de contrato por provedor e versionamento de modelo. |
| Resposta inventada | Regra incorreta para a pessoa usuária | Evidências autorizadas, fontes verificadas e fallback em [`service.py`](../app/generation/service.py) | Avaliação contínua, revisão humana para casos críticos e limites de confiança. |
| Exposição de documentos e perguntas | Risco de privacidade e conformidade | Execução local; logs mascarados; dados sintéticos na demonstração | Rede privada, criptografia, retenção mínima e acordo de processamento de dados. |
| Vazamento de segredos | Uso indevido da conta ou API | `.env` separado e segredos tipados em [`config.py`](../app/core/config.py#L11) | Cofre de segredos, rotação de chaves e identidade de serviço. |
| Custo e limites de uso | Custo imprevisível ou respostas bloqueadas | Modelos locais e métricas de latência | Orçamentos, rate limit, medição de tokens e alertas de custo. |
| Prompt injection | Modelo segue instruções indevidas | Guardrails documentados na [seção de segurança](#8-guardrails-filtro-de-conteúdo-e-alinhamento-da-resposta) | Filtros adicionais, monitoramento e revisão de ataques reais. |

### Decisão demonstrada

Ollama foi escolhido para a prova de conceito porque permite reproduzir o fluxo sem chave de API, custo por chamada ou envio externo de dados. Esse desenho é adequado para validar arquitetura e qualidade localmente. Para produção, a escolha entre self-hosted e nuvem deve considerar volume, latência, custo, requisitos de privacidade, maturidade operacional e modelos aprovados pela organização.

## 10. Como verificar o comportamento

| O que validar | Testes relacionados |
|---|---|
| Chunking por seção, tamanho e sobreposição | [`tests/unit/test_chunker.py`](../tests/unit/test_chunker.py) |
| Embeddings e contrato do Ollama | [`tests/unit/test_ollama_provider.py`](../tests/unit/test_ollama_provider.py) e [`tests/integration/test_ingestion_pipeline.py`](../tests/integration/test_ingestion_pipeline.py) |
| BM25 e RRF | [`tests/unit/test_lexical_retrieval.py`](../tests/unit/test_lexical_retrieval.py) e [`tests/unit/test_fusion.py`](../tests/unit/test_fusion.py) |
| CrossEncoder e contexto não redundante | [`tests/unit/test_reranker.py`](../tests/unit/test_reranker.py) e [`tests/unit/test_contextual_retriever.py`](../tests/unit/test_contextual_retriever.py) |
| Reescrita de consultas frequentes | [`tests/unit/test_grounded_answers.py`](../tests/unit/test_grounded_answers.py) |
| Isolamento entre empresas | [`tests/security/test_tenant_isolation.py`](../tests/security/test_tenant_isolation.py) |

Execute a suíte completa com:

```powershell
uv run pytest
```

O conjunto de avaliações reproduzíveis está documentado em [Plano e métricas de avaliação](rag-avaliacao-metricas-qualidade-v1.md).
