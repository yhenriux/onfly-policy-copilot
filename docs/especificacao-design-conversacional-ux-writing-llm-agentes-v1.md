# Especificação de Design Conversacional e UX Writing para LLMs e Agentes

**Versão:** 1.0  
**Status:** referência técnica para implementação  
**Escopo:** LLMs, RAG, copilotos, agentes e interfaces conversacionais  
**Público:** Produto, UX, UX Writing, Engenharia, IA, Dados, QA, Segurança e Governança

## 1. Objetivo

Esta especificação define requisitos verificáveis para construir experiências conversacionais claras, controláveis, acessíveis e rastreáveis. Ela separa:

- experiência e linguagem;
- interpretação e contexto;
- recuperação de conhecimento;
- geração e validação;
- execução de ferramentas;
- segurança e autorização;
- observabilidade e avaliação.

Os requisitos usam a seguinte convenção:

| Código | Obrigatoriedade |
|---|---|
| MUST | obrigatório para liberar uma implementação |
| MUST NOT | comportamento proibido |
| SHOULD | padrão recomendado; exceções precisam ser justificadas |
| MAY | opcional quando fizer sentido para o produto |

## 2. Princípios

### CONV-001: orientar a tarefa

Cada turno MUST compreender o objetivo, coletar contexto, executar uma ação, comunicar um resultado, resolver ambiguidade ou oferecer recuperação.

### CONV-002: reduzir esforço

O sistema SHOULD pedir somente a informação necessária para o próximo passo. Perguntas independentes MAY aparecer juntas em formulário; perguntas dependentes SHOULD ser feitas uma por vez.

### CONV-003: preservar controle

O usuário MUST conseguir entender o estado atual, corrigir dados, cancelar quando possível e recuperar falhas sem reiniciar a conversa.

### CONV-004: informar progressivamente

Respostas SHOULD seguir esta ordem:

1. conclusão ou resultado;
2. condição ou impacto necessário;
3. fonte ou detalhe complementar;
4. próximo passo.

### CONV-005: autoridade explícita

O sistema MUST distinguir informação fornecida pelo usuário, inferência, memória, conteúdo recuperado e resultado de ferramenta. O LLM MUST NOT ser a autoridade final para permissões, transações ou políticas de acesso.

## 3. Contrato conversacional por fluxo

Cada caso de uso MUST possuir um contrato como este:

```yaml
use_case: answer_policy_question
user_goal: obter orientação de política corporativa
required_context:
  - tenant_id
source_of_truth:
  - policy_documents
risk: medium
tools: []
success_condition: resposta com evidência autorizada
failure_conditions:
  - no_evidence
  - retrieval_unavailable
  - invalid_generation
recovery:
  no_evidence: pedir mais detalhes ou orientar suporte
  retrieval_unavailable: tentar novamente sem afirmar resposta
observability:
  - request_id
  - tenant_id
  - retrieval_score
  - cited_sources
  - generation_status
```

O contrato MUST definir objetivo, contexto, fonte de verdade, risco, permissões, estados, mensagens, recuperação e métricas.

## 4. Contexto e memória

### CONV-010: carry-over

Informações válidas MUST permanecer no contexto enquanto não forem alteradas, expirarem ou entrarem em conflito.

```json
{
  "intent": "search_policy",
  "constraints": {
    "tenant_id": "aurora_tecnologia",
    "topic": "transporte",
    "date": null
  }
}
```

Uma nova mensagem SHOULD alterar somente o atributo correspondente.

### CONV-011: procedência

Valores de contexto SHOULD carregar procedência:

```json
{
  "topic": {
    "value": "reembolso",
    "source": "USER_PROVIDED",
    "confidence": 1.0
  }
}
```

Fontes válidas: `USER_PROVIDED`, `INFERRED`, `RETRIEVED`, `REMEMBERED`, `SYSTEM_DEFINED` e `TOOL_RETURNED`.

### CONV-012: memória persistente

Memória de longo prazo MUST possuir finalidade, retenção, exclusão, correção, controle de acesso e transparência. O histórico técnico deste projeto não deve armazenar pergunta ou resposta sem necessidade operacional.

## 5. Desambiguação e confirmação

### CONV-020: ambiguidade relevante

O sistema MUST perguntar quando interpretações diferentes alterarem a resposta, o custo, a permissão ou o risco.

**Preferir:** “Você quer cancelar a reserva ou alterar a data?”  
**Evitar:** “Pode explicar melhor?”

### CONV-021: confirmação proporcional

Confirmação implícita é adequada para busca e recomendação reversível. Confirmação explícita é obrigatória antes de pagamento, exclusão, envio externo, alteração irreversível ou ação com impacto financeiro.

### CONV-022: não confirmar o óbvio

O sistema MUST NOT pedir confirmação para uma busca de baixo risco que ainda não executa uma ação externa.

## 6. Estados e UX Writing

Todo fluxo MUST representar pelo menos:

| Estado | Objetivo da mensagem |
|---|---|
| `IDLE` | explicar o que o usuário pode fazer |
| `UNDERSTANDING` | informar interpretação em andamento |
| `RETRIEVING` | informar busca em fontes autorizadas |
| `EXECUTING` | informar ferramenta em execução |
| `PARTIAL` | comunicar o que foi concluído e o que falta |
| `SUCCESS` | mostrar resultado e próxima ação |
| `EMPTY` | diferenciar ausência de resultado de falha de compreensão |
| `ERROR` | explicar causa e recuperação |
| `BLOCKED` | explicar limite sem revelar regra de segurança explorável |
| `CANCELLED` | informar o que foi interrompido |

### WRITE-001: voz

A voz MUST ser clara, profissional, direta e respeitosa. O tom SHOULD ser calmo em erro, objetivo em risco e positivo em sucesso.

### WRITE-002: estrutura de erro

Toda mensagem de erro SHOULD conter:

1. o que aconteceu;
2. impacto para o usuário;
3. ação possível.

**Exemplo:** “A consulta demorou mais que o esperado. Nenhuma alteração foi feita. Tente novamente.”

### WRITE-003: verbos concretos

Preferir `buscar`, `comparar`, `enviar`, `salvar`, `cancelar`, `corrigir` e `tentar novamente`. Evitar linguagem vaga como “dar andamento” quando houver uma ação específica.

### WRITE-004: não alegar ações inexistentes

O sistema MUST NOT dizer “sua reserva foi cancelada” sem confirmação da ferramenta responsável.

### WRITE-005: escaneabilidade

Listas SHOULD ser usadas para etapas, alternativas, requisitos e comparações. Respostas longas SHOULD usar resumo, detalhes, evidências e próxima ação.

## 7. RAG e grounding

### RAG-001: pipeline

O pipeline MUST seguir:

```text
extração → limpeza → estrutura → chunking → metadados → embeddings
→ indexação → retrieval → reranking → contexto → geração → validação → fontes
```

### RAG-002: estrutura

O sistema SHOULD preservar título, seção, subseção, versão, vigência, tenant, documento, origem e posição. O texto usado para embedding SHOULD incluir título e seção; o texto apresentado ao usuário MUST permanecer limpo.

### RAG-003: chunking

O chunker MUST preferir documento, seção, subseção, parágrafo e sentença nessa ordem. O limite de caracteres ou tokens só deve dividir uma unidade semanticamente longa.

Baseline recomendado para políticas: `300–600 tokens`, overlap de `10%–20%`, calibrado pelo golden dataset.

### RAG-004: parent-child

Para documentos longos, embeddings SHOULD ser gerados para chunks filhos e o contexto de geração SHOULD recuperar o parent correspondente quando condições ou exceções estiverem separadas.

### RAG-005: metadados mínimos

```json
{
  "tenant_id": "empresa_01",
  "document_id": "policy_123",
  "title": "Política de viagens",
  "section": "Hospedagem > Limite de diária",
  "version": "v4",
  "valid_from": "2026-06-02",
  "source": "policy.md",
  "chunk_id": "chunk_001",
  "document_hash": "...",
  "chunk_hash": "..."
}
```

### RAG-006: isolamento

`tenant_id` MUST ser aplicado no backend durante retrieval. O prompt MUST NOT ser responsável por isolamento de tenant.

### RAG-007: versões e conflitos

O índice MUST manter versões para auditoria, mas somente a versão vigente deve participar da busca. Conflitos entre documentos não podem ser resolvidos silenciosamente.

### RAG-008: score

Score de dense search, score de RRF e score de reranking MUST ser armazenados separadamente. Nenhum limiar deve ser escolhido sem avaliação offline.

### RAG-009: geração ancorada

Uma resposta MUST possuir fonte citada ou ser explicitamente marcada como resposta baseada em evidência estruturada. Respostas sem suporte não podem ser promovidas a alta confiança.

## 8. LLM e saída estruturada

### LLM-001: responsabilidades do prompt

O prompt MUST declarar papel, fontes permitidas, tratamento de ausência, conflitos, confiança, citações e formato de saída.

### LLM-002: validação

Toda saída MUST passar por schema, validação de posições, presença de resposta, tamanho mínimo e verificação de fatos.

### LLM-003: fatos intermediários

Quando o modelo não citar uma fonte suficiente, o sistema SHOULD extrair fatos determinísticos dos chunks e executar uma síntese factual ou fallback estruturado. Repetir o mesmo prompt sem mudança de contexto não é uma estratégia de recuperação.

### LLM-004: confiança

Confiança de retrieval e confiança de geração MUST ser métricas separadas:

```text
retrieval_score: 0.98
generation_confidence: medium
source_support: confirmed
```

## 9. Agentes e ferramentas

Cada ferramenta MUST declarar nome, finalidade, schema de entrada, schema de saída, timeout, erros, permissões, idempotência e telemetria.

Texto livre do LLM MUST NOT executar ações críticas diretamente. O fluxo obrigatório é:

```text
LLM → plano estruturado → autorização → regra de negócio → ferramenta
→ validação do resultado → resposta
```

Retries de operações não idempotentes MUST ser bloqueados ou protegidos por `Idempotency-Key`.

## 10. Segurança e privacidade

- Retrieved content MUST ser tratado como dado, nunca como instrução de sistema.
- Prompt injection indireto MUST ser filtrado e testado.
- PII, tokens, senhas e documentos confidenciais MUST ser removidos ou mascarados em logs.
- Cada ferramenta MUST seguir least privilege.
- Cross-tenant retrieval MUST possuir teste automatizado.
- A UI MUST distinguir “não encontrei” de “não tenho permissão”.

## 11. Acessibilidade e interface

A interface MUST possuir:

- navegação por teclado;
- foco visível;
- labels semânticos;
- contraste adequado;
- estados dinâmicos anunciados por `aria-live`;
- suporte a zoom;
- alternativa textual para ícones e cores;
- comportamento compatível com `prefers-reduced-motion`.

Mensagens de erro MUST estar associadas ao estado ou campo correspondente. A UI não deve depender apenas de cor para comunicar confiança, erro ou sucesso.

## 12. Observabilidade

Cada interação SHOULD possuir:

- `request_id`;
- `session_id`;
- tenant e usuário autorizados;
- modelo;
- versão do prompt;
- versão do embedding;
- chunks recuperados;
- chunks enviados;
- fontes citadas;
- score por etapa;
- latência;
- tentativas;
- status final;
- feedback.

Perguntas e respostas só devem ser persistidas quando houver finalidade aprovada, retenção e proteção adequadas.

## 13. Avaliação

### Métricas de retrieval

- Recall@K;
- Hit Rate@K;
- MRR;
- NDCG;
- score Top-1;
- taxa de evidência elegível.

### Métricas de geração

- correctness;
- answer relevance;
- completeness;
- source adherence;
- citation correctness;
- citation completeness;
- false refusal rate.

### Métricas de experiência

- task success rate;
- turns to resolution;
- clarification rate;
- rephrase rate;
- abandonment rate;
- error recovery rate;
- feedback positivo/negativo.

O golden dataset MUST conter happy paths, perguntas sem resposta, ambiguidades, condições, exceções, conflitos de versão, prompt injection e tentativas cross-tenant.

## 14. Critérios de aceite

Uma funcionalidade conversacional só pode ser considerada pronta quando:

- há contrato conversacional documentado;
- todos os estados possuem copy;
- o fluxo foi testado em múltiplos turnos;
- o retrieval foi medido antes e depois;
- fontes e versões estão corretas;
- ausência de evidência gera recusa adequada;
- respostas não afirmam ações não executadas;
- saída estruturada é validada;
- ferramentas possuem autorização e timeout;
- prompt injection e cross-tenant foram testados;
- métricas e trace estão disponíveis;
- documentação, UX e engenharia usam a mesma terminologia.

## 15. Aplicação neste projeto

| Requisito | Implementação atual | Situação |
|---|---|---|
| Isolamento por tenant | `TenantGuardedRetriever` e filtros Qdrant | implementado |
| Chunking estrutural | `app/ingestion/chunker.py` | implementado |
| Contexto semântico no embedding | título + seção + texto | implementado |
| Coleção versionada | `onfly_policy_documents_phase3` | implementado |
| Reranking | CrossEncoder local | implementado |
| Fontes e trace | `ExecutionTrace` | implementado |
| Fatos intermediários | `extract_grounding_facts` | implementado |
| Citation repair | providers Ollama | implementado |
| Parent-child chunking | não implementado | roadmap |
| Memória multi-turn persistente | não implementado | roadmap |
| Ferramentas transacionais | não implementado | roadmap |
| Handoff humano estruturado | não implementado | roadmap |

## 16. Versionamento e governança

Devem ser versionados conjuntamente:

- documentos e políticas;
- chunking;
- embeddings;
- reranker;
- modelo de geração;
- prompts;
- schemas;
- dataset de avaliação;
- copy tokens;
- feature flags.

Toda mudança que alterar resposta, fonte, confiança, latência ou copy MUST registrar motivo, evidência de avaliação e estratégia de rollback.
