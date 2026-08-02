# Registro de execução — Onfly Policy Copilot

Este documento registra a evolução técnica do case, as decisões tomadas e as evidências produzidas em cada fase. O histórico deve permitir que revisores compreendam o estado do projeto, reproduzam validações e identifiquem riscos pendentes.

## Convenção de atualização

Cada fase deve registrar:

- Objetivo.
- Escopo.
- Decisões tomadas.
- Tarefas concluídas.
- Descobertas.
- Testes executados.
- Métricas obtidas.
- Pendências.
- Próximo passo.

Resultados ainda não verificados devem permanecer identificados como pendentes. Decisões arquiteturais relevantes também devem ser registradas em ADRs no diretório `docs/adr/`.

## Fase 0 — Fundação do repositório

### Objetivo

Estabelecer uma base local controlada, reproduzível e preparada para a implementação incremental do Onfly Policy Copilot.

### Escopo

- Inicialização do repositório Git.
- Definição das regras permanentes do projeto.
- Configuração do projeto Python.
- Criação da estrutura modular inicial.
- Configuração segura de ambiente, sem segredos versionados.
- Implementação da base funcional da API, integração local e testes.
- Documentação dos comandos de execução.

### Decisões tomadas

- O desenvolvimento inicial será local.
- O repositório remoto será configurado depois que a fundação estiver validada.
- Todo dado utilizado pelo case será sintético.
- O front-end demonstrativo integrará o acabamento do projeto após a estabilização dos contratos da API, da segurança e da observabilidade.

### Tarefas concluídas

- Repositório Git local inicializado na branch `main`.
- Regras permanentes registradas em `AGENTS.md`.
- Registro de execução criado em `PLANS.md`.
- Planejamento técnico incorporado ao repositório em `PROJECT_PLAN.md`.
- Projeto Python e ferramentas de qualidade configurados em `pyproject.toml`.
- Contrato de configuração local e regras de arquivos ignorados definidos em `.env.example` e `.gitignore`.
- Estrutura modular inicial criada e classificada por responsabilidade.
- Configuração tipada implementada com validação de ambiente, URLs, limites e segredo do Qdrant.
- Ambiente virtual e lock de dependências gerados com `uv`.
- Primeira fatia HTTP implementada com aplicação FastAPI e `GET /health` documentado no OpenAPI.
- `POST /v1/ask` implementado com validação de entrada, resposta JSON e erro controlado para indisponibilidade.
- Integração HTTP com `llama3.2:1b` e `all-minilm` implementada via Ollama.
- Primeira política sintética criada para o tenant `aurora_tecnologia`.
- Ingestão por seção, embeddings e persistência local no Qdrant implementadas.
- Retrieval denso conectado à geração com retorno de fontes, confiança, latência e `request_id`.
- Execução local documentada em `README.md`.

### Descobertas

- Ollama `0.32.5` está disponível no ambiente local.
- O modelo gerador `llama3.2:1b` está instalado e respondeu a uma inferência de validação.
- O modelo de embeddings `all-minilm` está disponível localmente.
- Python `3.14.3` e o executável do `uv` estão disponíveis no ambiente local.

### Testes executados

- Verificação da instalação e da versão do Ollama.
- Inferência local simples com `llama3.2:1b`.
- Ruff executado para formatação e lint em 47 arquivos.
- mypy executado em modo estrito em 47 arquivos.
- Cinco testes unitários da configuração executados com pytest.
- Dois testes de integração validaram o health check e sua documentação OpenAPI.
- API iniciada com Uvicorn e validada por requisições reais a `/health` e `/docs`.
- Ingestão real executada com seis chunks e embeddings de 384 dimensões.
- Pergunta real de reembolso executada de ponta a ponta com resposta correta e fonte autorizada.
- Dezoito testes unitários e de integração executados com pytest.

### Métricas obtidas

- Dezoito testes aprovados.
- Cobertura total de 88% do código executável atual.
- Health check respondeu HTTP 200 e o Swagger respondeu HTTP 200 no ambiente local.
- Embeddings `all-minilm` confirmados com 384 dimensões.
- Seis chunks persistidos no Qdrant local.
- Resposta RAG real retornou a regra de 10 dias úteis com o chunk de reembolso em primeiro lugar.
- Latência observada da requisição RAG validada: aproximadamente 11 segundos com modelos aquecidos.
- Ainda não há baseline de qualidade ou desempenho do pipeline RAG.

### Pendências

- Capturar as evidências visuais da estrutura, Swagger e pytest para a apresentação final.
- As limitações funcionais restantes estão planejadas para as fases seguintes.

### Próximo passo

Iniciar a Fase 1 com a criação dos dois tenants fictícios e suas políticas conflitantes.

## Fases seguintes

As Fases 3 a 11 serão abertas neste registro quando iniciadas, preservando a ordem, os objetivos, os critérios de aceite e as evidências definidos no planejamento técnico do projeto.

## Fase 1 — Domínio B2B e dados sintéticos

### Objetivo

Representar duas empresas fictícias com regras diferentes e metadados suficientes para demonstrar isolamento e rastreabilidade.

### Escopo

- Completar as políticas da Aurora Tecnologia.
- Criar a Brisa Sistemas com regras conflitantes.
- Definir metadados obrigatórios de documento e trecho.
- Criar um catálogo versionado de perguntas.
- Demonstrar respostas diferentes para a mesma pergunta.

### Decisões tomadas

- Cada documento possui um manifesto JSON separado do texto da política.
- Os metadados obrigatórios são tenant, documento, versão, validade, seção e identificador do trecho.
- A coleção do Qdrant passou a se chamar `onfly_policy_documents_phase1` para não misturar pontos antigos sem versão. A decisão está registrada no ADR 0001.

### Tarefas concluídas

- Política completa da Aurora criada com nove seções de regras.
- Política completa da Brisa criada com nove seções e limites conflitantes.
- Manifestos `metadata.json` criados para as duas empresas.
- Metadados propagados do documento até o payload recuperado do Qdrant.
- Catálogo criado com perguntas comuns, críticas, ambíguas, sem resposta e adversariais.
- Docstrings e comentários existentes revisados para português simples.

### Descobertas

- A coleção local antiga reteve seis pontos sem versão ao ser recriada com o mesmo nome dentro do mesmo processo.
- Uma coleção versionada separou o formato novo sem manipular arquivos internos do Qdrant.
- O modelo local respondeu corretamente à mesma pergunta quando recebeu os trechos filtrados de cada empresa.

### Testes executados

- Validação dos manifestos e dos metadados obrigatórios.
- Validação das cinco categorias do catálogo de perguntas.
- Teste de regras conflitantes para a mesma pergunta.
- Suíte completa de lint, tipagem e testes automatizados.
- Duas chamadas reais à API usando a mesma pergunta e tenants diferentes.

### Métricas obtidas

- 10 trechos indexados para a Aurora Tecnologia.
- 10 trechos indexados para a Brisa Sistemas.
- 20 pontos na coleção atual, todos com versão.
- 10 casos no catálogo de perguntas, distribuídos em cinco categorias.
- 21 testes aprovados antes da validação final da fase.
- Cobertura total de 89% nessa execução.

### Pendências

- A autenticação do tenant será implementada na Fase 6.
- As perguntas ambíguas e adversariais ainda não possuem tratamento especializado.

### Próximo passo

Iniciar a Fase 2 com o pipeline de ingestão versionado, controle de duplicidade e recuperação somente da versão ativa.

## Fase 2 — Ingestão versionada

### Objetivo

Transformar documentos em conhecimento versionado, sem duplicatas e com controle claro de ativação e exclusão.

### Escopo

- Separar leitura, normalização, divisão, embeddings e indexação.
- Dividir seções longas com sobreposição configurável.
- Calcular hashes de documento e trecho.
- Ignorar reingestão idêntica.
- Preservar versões antigas como inativas.
- Implementar exclusão lógica e reindexação.

### Decisões tomadas

- Texto carregado e texto normalizado usam modelos diferentes para deixar cada etapa explícita.
- Hashes são calculados depois da normalização, evitando diferenças causadas apenas por espaços.
- A mesma versão com conteúdo diferente é rejeitada e exige um novo número de versão.
- Versões antigas e documentos excluídos continuam no Qdrant para auditoria.
- A coleção atual se chama `onfly_policy_documents_phase2`.

### Tarefas concluídas

- Loader, normalizador, chunker, gerador de embeddings e indexador separados.
- Chunking por seção com tamanho e sobreposição configuráveis.
- Hashes de documento e trecho adicionados aos payloads.
- Controle de duplicidade e conflito de versão implementados.
- Ativação de nova versão e exclusão lógica implementadas.
- Comando para ingerir um único manifesto implementado.
- Política Aurora `v2` criada com novos limites e prazo de reembolso.
- Versão e seção adicionadas às fontes retornadas pela API.

### Descobertas

- A normalização permite tratar diferenças apenas de espaços como o mesmo conteúdo.
- Identificadores estáveis e hashes permitem reexecutar a carga sem aumentar a quantidade de pontos.
- A Aurora `v1` e `v2` coexistem, mas somente `v2` participa da busca.

### Testes executados

- Testes isolados de leitura, normalização, chunking e sobreposição.
- Testes da geração de embeddings e indexação.
- Teste de reingestão sem duplicidade.
- Teste de conflito da mesma versão com conteúdo diferente.
- Teste de coexistência, ativação, exclusão lógica e nova indexação.
- Duas cargas reais consecutivas no Qdrant local.
- Pergunta real pela API para confirmar o uso da Aurora `v2`.

### Métricas obtidas

- 30 trechos armazenados na coleção da Fase 2.
- 20 trechos ativos.
- 10 trechos da Aurora `v1` preservados como inativos.
- Segunda carga real adicionou zero trechos.
- A resposta real usou o novo limite de R$ 130,00 da Aurora `v2`.
- 27 testes automatizados aprovados, com cobertura total de 88%.
- Ruff e mypy aprovados, sem erros de estilo ou de tipos.

### Pendências

- A ativação é definida pela ordem de ingestão; uma fase futura poderá aplicar regras de vigência por data.
- Migrações entre modelos de embedding serão tratadas na fase de entrega e operação.

### Próximo passo

Iniciar a Fase 3 com busca lexical BM25, fusão de rankings e comparação contra a busca vetorial atual.

## Fase 3 — Recuperação híbrida

### Objetivo

Combinar busca por significado e busca por palavras para melhorar a posição das fontes corretas.

### Escopo concluído

- Baseline da busca densa registrado.
- BM25 implementado em código próprio e testado.
- RRF implementado em código próprio, com constante e pesos configuráveis.
- Scores e posições das buscas densa e lexical preservados nos resultados.
- Filtro obrigatório por tenant aplicado à busca densa, ao BM25 e à coordenação híbrida.
- Comparação reproduzível entre dense, BM25 e híbrida criada.

### Decisões tomadas

- O BM25 lê os payloads ativos do Qdrant. Assim, não existe uma segunda cópia persistente que possa ficar desatualizada.
- A tokenização remove diferenças de maiúsculas e acentos antes de comparar palavras.
- O RRF combina posições, porque scores vetoriais e lexicais possuem escalas diferentes.
- Os pesos padrão são iguais e podem ser alterados por variáveis de ambiente.

### Evidências e métricas

- Dataset versionado com 12 perguntas e seções esperadas.
- Busca densa: Recall@5 `0,9167` e MRR `0,6556`.
- BM25: Recall@5 `0,9167` e MRR `0,8222`.
- Busca híbrida: Recall@5 `0,9167` e MRR `0,8264`.
- “Tarifas não reembolsáveis” melhorou da posição 2 na densa para 1 na híbrida.
- “Fornecedor e motivo da despesa” melhorou da posição 6 na densa para 1 na híbrida.
- Relatório reproduzível salvo em `docs/evidence/phase3_retrieval_results.json`.
- 36 testes automatizados aprovados, com cobertura total de 87%.
- Ruff e mypy aprovados, sem erros de estilo ou de tipos.
- Chamada real à API retornou `Documentos obrigatórios`, versão ativa `v2`, como primeira fonte.

### Limitações conhecidas

- O conjunto sintético ainda é pequeno; as métricas demonstram comportamento, não desempenho estatístico de produção.
- O BM25 é reconstruído a partir dos payloads a cada consulta. Uma fase de escala poderá manter um índice lexical dedicado.
- A autenticação do tenant permanece planejada para a Fase 6; nesta fase, o identificador ainda vem no contrato validado da API.

### Próximo passo

Iniciar a Fase 4 com re-ranking e montagem controlada do contexto.

## Fase 4 — Re-ranking e contexto

### Objetivo

Melhorar a ordem dos candidatos e controlar exatamente quais trechos chegam ao modelo gerador.

### Escopo concluído

- CrossEncoder `cross-encoder/ms-marco-MiniLM-L6-v2` adicionado para execução local.
- Dez candidatos híbridos são reordenados antes da seleção final.
- Scores e posições do re-ranking são preservados no modelo de domínio.
- Redundância controlada por similaridade de palavras.
- Contexto limitado por quantidade de trechos e orçamento de caracteres.
- Benchmark antes e depois criado e versionado.

### Métricas obtidas

| Configuração | Recall@5 | MRR | Média | P95 |
|---|---:|---:|---:|---:|
| Híbrida sem re-ranking | 0,9167 | 0,8125 | 5,24 ms | 6,03 ms |
| CrossEncoder e contexto | 0,9167 | 0,9167 | 205,80 ms | 227,36 ms |

- Partida fria com o modelo já no cache: 8.808,93 ms.
- A aprovação internacional da Aurora subiu de fora do top 5 para a posição 1.
- A violação de política da Brisa subiu da posição 4 para a posição 1.
- O caso de documentos obrigatórios da Brisa saiu do top 5 depois do re-ranking.
- Relatório salvo em `docs/evidence/phase4_reranking_results.json`.
- 43 testes automatizados aprovados, com cobertura total de 88%.
- Ruff e mypy aprovados, sem erros de estilo ou de tipos.
- A chamada real retornou a seção correta em primeiro lugar, versão `v2`, com score `0,989`.

### Decisões e limitações

- O modelo é carregado sob demanda para não aumentar o tempo de inicialização quando a recuperação não é usada.
- A partida fria é registrada separadamente da latência aquecida.
- O ganho de MRR justifica manter o experimento, mas o caso que piorou deverá permanecer na regressão.
- O conjunto de 12 perguntas é demonstrativo e ainda não representa uma amostra de produção.
- Na chamada real, o modelo gerador citou uma fonte secundária mesmo recebendo a fonte correta em primeiro lugar. A aderência estruturada às fontes pertence à Fase 5.

### Próximo passo

Iniciar a Fase 5 com geração estruturada e abstração de provedor.

## Fase 5 — Geração confiável

### Objetivo

Tornar a geração substituível, validada e segura diante de falhas ou ausência de evidência.

### Escopo concluído

- Interface comum de provedor formalizada em `app/generation/provider.py`.
- Ollama mantido como primeira implementação da interface.
- Structured output validado pelo Pydantic com resposta, posições das fontes e confiança.
- Posições citadas convertidas somente em chunks realmente autorizados.
- Timeout, novas tentativas e backoff exponencial configuráveis.
- Fallback controlado com status `degraded` e confiança baixa.
- Prompt versionado como `policy_answer_v1`.
- Metadados de provedor, modelo, prompt, status e tentativas incluídos em toda resposta.
- Ausência de evidência tratada por limiar antes da geração ou por lista vazia do modelo.

### Decisões tomadas

- Posições numéricas substituem IDs longos no JSON pedido ao modelo de 1B; o serviço faz a conversão segura para IDs reais.
- Lista de posições vazia significa ausência de evidência, evitando um campo booleano redundante e contraditório.
- Somente chunks com score mínimo de `0,50` podem entrar na geração.
- Por padrão, somente a evidência mais forte é enviada ao `llama3.2:1b` para reduzir citações secundárias incorretas.
- Falha de geração produz resposta degradada; falha de embedding mantém HTTP 503 porque impede a recuperação segura.

### Evidências

- Pergunta respondível retornou status `generated`, prompt `policy_answer_v1` e somente a seção correta com score `0,989`.
- Pergunta sobre emissão de passaporte retornou status `no_evidence`, zero tentativas de geração e zero fontes.
- Teste de falha HTTP 503 comprovou três tentativas com esperas de `0,1 s` e `0,2 s`.
- Teste de indisponibilidade comprovou fallback com status `degraded` sem quebrar o contrato.
- 48 testes automatizados aprovados, com cobertura total de 90%.

### Limitações

- Na chamada real, o modelo resumiu a regra completa como “diretor financeiro”, omitindo o gestor da área. A Fase 7 medirá completude e correção da geração.
- O retry ocorre dentro da requisição e aumenta a latência quando o Ollama está instável.
- Um provedor externo ainda não foi adicionado; a substituição está preparada pelo contrato e pelos mocks.

### Próximo passo

Iniciar a Fase 6 com segurança e isolamento multi-tenant.

## Fase 6 — Segurança multi-tenant

### Objetivo

Derivar a empresa de uma identidade autenticada e impedir que perguntas, documentos ou logs atravessem as fronteiras de segurança.

### Escopo concluído

- Login demonstrativo com duas credenciais totalmente sintéticas.
- Senhas armazenadas por hash PBKDF2 com salt.
- Token assinado por HMAC-SHA256 com usuário, tenant, papéis e expiração.
- `tenant_id` e `user_id` removidos do corpo de `/v1/ask`.
- Tenant aplicado antes do retrieval e validado novamente em cada chunk.
- Testes de vazamento entre Aurora e Brisa.
- Prompt injection conhecida bloqueada antes do embedding.
- Chunks com instruções maliciosas removidos antes da geração.
- Mascaramento de credenciais, perguntas, e-mail e CPF para logs.
- Threat model documentado em `docs/threat-model.md`.

### Evidências reais

- Login Aurora produziu `user_aurora_001` e tenant `aurora_tecnologia`.
- Login Brisa produziu `user_brisa_001` e tenant `brisa_sistemas`.
- A mesma pergunta, sem tenant no corpo, retornou R$ 130,00 para Aurora e R$ 85,00 para Brisa.
- Tentativa de prompt injection cruzando empresas retornou HTTP 400.
- Campo `tenant_id` forjado no corpo retorna HTTP 422.
- Token adulterado e senha inválida são rejeitados.
- 57 testes automatizados aprovados, com cobertura total de 90%.
- Ruff e mypy aprovados, sem erros de estilo ou de tipos.

### Decisões e limitações

- O token próprio é demonstrativo. Produção deve usar um provedor de identidade consolidado.
- O catálogo de prompt injection cobre padrões conhecidos e deve evoluir com testes adversariais.
- Resposta factual sem fonte citada é substituída pela resposta padrão sem evidência.
- Não há revogação de token ou rate limiting nesta fase.
- Auditoria de eventos e métricas de segurança pertencem à Fase 8.

### Próximo passo

Iniciar a Fase 7 com avaliação de RAG e regressão.

## Fase 7 — Avaliação e regressão

### Objetivo

Transformar qualidade de retrieval, geração e segurança em resultados reproduzíveis e protegidos por um gate automático.

### Escopo concluído

- Golden dataset `v1` com dez casos, respostas esperadas e fontes corretas.
- Retrieval avaliado separadamente com Recall@5, MRR e nDCG@5.
- Geração avaliada com correção, relevância, completude e aderência às fontes.
- Perguntas sem resposta e ataques avaliados separadamente.
- Busca densa, híbrida e híbrida com re-ranking comparadas.
- Gate de regressão com limites versionados e código de saída de falha.

### Resultados reais

| Retrieval | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|
| Densa | 1,0000 | 0,7556 | 0,8145 |
| Híbrida | 0,8333 | 0,7083 | 0,7384 |
| Híbrida com re-ranking | 1,0000 | 1,0000 | 1,0000 |

- Correção da geração: `0,1667`.
- Relevância da geração: `0,1889`.
- Completude da geração: `0,1667`.
- Aderência às fontes: `0,5000`.
- Recusa adequada sem resposta: `0,5000`.
- Bloqueio adversarial: `1,0000`.
- Vazamento entre tenants: `0,0000`.
- Gate executado e aprovado contra o baseline real.
- 61 testes automatizados aprovados, com cobertura total de 90%.
- Ruff e mypy aprovados, sem erros de estilo ou de tipos.

### Análise e limitações

- O re-ranking colocou todas as fontes corretas na primeira posição.
- O gargalo medido é o `llama3.2:1b`, que encurta respostas, perde citações e falhou em uma recusa.
- Os limites atuais de geração são conservadores e protegem somente contra piora do baseline.
- Melhorias futuras devem elevar as métricas e os limites no mesmo conjunto de mudanças.
- Métricas determinísticas não substituem avaliação humana, que pode ser adicionada como complemento.

### Próximo passo

Iniciar a Fase 8 com observabilidade e confiabilidade.

## Fase 8 — Observabilidade e confiabilidade

### Objetivo

Permitir localizar, medir e reconstruir tecnicamente cada requisição sem registrar conteúdo sensível.

### Escopo concluído

- `request_id` compartilhado entre cabeçalho, resposta e logs estruturados.
- Latência medida para embedding, retrieval, re-ranking, geração e total.
- Trace com modelo, prompt, documentos, versões, chunks, scores, retries e fallback.
- Health da API separado do readiness de Ollama e Qdrant.
- Métricas de volume, erros, latência, retries e fallbacks.
- SLI, SLO e procedimento de incidentes documentados no runbook.

### Evidências reais

- `GET /health`, `GET /ready` e `GET /metrics` cobertos por testes integrados.
- Readiness retorna HTTP 503 e identifica a dependência indisponível.
- Teste de log confirma configuração e fontes sem expor a pergunta.
- 65 testes automatizados aprovados, com cobertura total de 90%.
- Ruff e mypy aprovados, sem erros de estilo ou de tipos.

### Decisões e limitações

- As métricas ficam na memória e reiniciam junto com o processo.
- O endpoint fornece contagem e média; percentis dependem da futura plataforma de monitoramento.
- Os SLOs são objetivos iniciais e devem ser recalibrados com tráfego real.
- Logs não incluem pergunta, token, senha ou dados pessoais.

### Próximo passo

Iniciar a Fase 9 com Docker, CI/CD e rollback.

## Fase 9 — Docker, CI/CD e rollback

### Objetivo

Empacotar a API, automatizar os gates de qualidade e permitir retorno seguro para uma versão estável.

### Escopo concluído

- Dockerfile com Python e uv fixados, dependências congeladas e health check.
- Compose com API, Qdrant persistente e conexão documentada ao Ollama local.
- Qdrant configurável em modo de pasta local ou servidor HTTP.
- CI com Ruff, mypy, pytest, segurança, regressão, versões e build Docker.
- Release `0.9.0` ligado ao prompt `policy_answer_v1` e ao esquema do índice.
- Deploy candidato com falha e rollback para a versão estável simulados em código.
- Migração do índice por nova coleção e retorno para a anterior documentados.

### Evidências

- A simulação detectou a candidata `0.9.1-broken` e retornou para `0.9.0` saudável.
- O resultado foi versionado em `docs/evidence/phase9_rollback_simulation.json`.
- Testes protegem conexão do Compose, volume do Qdrant, labels da imagem e comandos obrigatórios do CI.
- O manifesto de release foi validado automaticamente.
- 70 testes automatizados aprovados, com cobertura total de 90%.
- Ruff, mypy, testes de segurança e gate de regressão aprovados.

### Decisões e limitações

- O Ollama fica fora do Compose para reutilizar a instalação e os modelos locais existentes.
- A estação atual não possui Docker; portanto, o build real não pôde ser executado localmente e é um gate obrigatório do CI.
- A coleção antiga deve permanecer disponível durante a janela de rollback.
- O pipeline foi criado localmente, mas somente executará no provedor depois que o repositório for publicado no Git.

### Próximo passo

Iniciar a Fase 10 com interface, demonstração e acabamento.

## Fase 10 — Front-end e acabamento

### Objetivo

Entregar uma experiência completa para o avaliador percorrer autenticação, consulta, evidências, operação e feedback em cinco minutos.

### Escopo concluído

- Front-end responsivo em HTML, CSS e JavaScript servido pelo FastAPI.
- Login visual com Aurora e Brisa usando somente credenciais sintéticas.
- Consulta com exemplos, carregamento progressivo, resposta, fontes e confiança.
- Estados de ausência, modo degradado, timeout, indisponibilidade, sessão expirada e bloqueio de segurança.
- Feedback positivo ou negativo ligado ao `request_id` e validado pelo tenant.
- Trace visual com modelo, prompt, latências, fontes, scores e identificador.
- Seed e roteiro cronometrado de cinco minutos documentados.
- Arquitetura, ADR, threat model, avaliação, runbook e README revisados.
- Release final atualizado para `1.0.0`, mantendo o prompt `policy_answer_v1`.

### Evidências reais

- QA visual confirmou tela inicial, login Aurora, consulta, fonte, trace e feedback.
- A pergunta sobre alimentação retornou `130,00`, documento Aurora `v2` e score `0,999`.
- A execução observada levou cerca de 16,4 segundos: 1,3 s de embedding, 11,5 s de retrieval com re-ranking e 3,7 s de geração.
- Feedback positivo foi recebido e ligado ao `request_id` da consulta.
- Teste confirma que feedback da Brisa não pode usar requisição da Aurora.
- 75 testes automatizados aprovados, com cobertura total de 90%.
- Ruff, mypy, JavaScript, segurança, versões e regressão aprovados.

### Decisões e limitações

- O front-end não usa dependências externas nem exige build separado.
- Token e feedback ficam somente em memória e desaparecem ao recarregar ou reiniciar.
- Conteúdo da API é inserido como texto, nunca como HTML executável.
- O retrieval pesado roda em thread de trabalho para manter a API responsiva.
- A primeira consulta deve ser aquecida antes da demonstração por causa do CrossEncoder.

### Próximo passo

Iniciar a Fase 11 com a apresentação técnica sustentada pelas evidências do projeto.
