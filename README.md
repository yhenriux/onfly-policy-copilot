# Onfly Policy Copilot

Case técnico independente de um assistente RAG para consulta de políticas corporativas de viagens. RAG significa que o sistema busca trechos relevantes antes de pedir a resposta ao modelo. A aplicação recebe uma pergunta, recupera evidências no Qdrant, gera a resposta com um modelo local no Ollama e retorna as fontes utilizadas.

O projeto utiliza somente dados sintéticos e não representa um produto oficial da Onfly.

## Fluxo funcional atual

1. `scripts.seed_demo` carrega as políticas sintéticas da Aurora Tecnologia e da Brisa Sistemas.
2. O texto é normalizado, ou seja, espaços e quebras de linha são padronizados.
3. Um hash identifica o conteúdo. Hash é uma assinatura que permite reconhecer arquivos iguais.
4. O documento Markdown é dividido por seções, com sobreposição configurável em trechos longos.
5. O Ollama gera embeddings de 384 dimensões com `all-minilm`. Embeddings são vetores numéricos que representam significado.
6. Os chunks, que são trechos menores do documento, e seus metadados são persistidos no Qdrant local.
7. `POST /v1/ask` gera o embedding da pergunta.
8. O Qdrant executa a busca densa somente nos trechos ativos e autorizados para o tenant.
9. O BM25 executa a busca pelas palavras da pergunta no mesmo tenant.
10. O RRF combina as posições dos dois rankings com pesos configuráveis.
11. O CrossEncoder local reordena os candidatos comparando pergunta e trecho juntos.
12. Trechos redundantes são removidos e o contexto respeita um limite de caracteres.
13. `llama3.2:1b` responde usando o contexto final.
14. A API retorna resposta, versão, fontes, confiança, latência e `request_id`.

## Pré-requisitos

- Python entre 3.11 e 3.14.
- [`uv`](https://docs.astral.sh/uv/).
- Ollama em execução em `http://localhost:11434`.
- Modelos locais `llama3.2:1b` e `all-minilm`.

Confirme os modelos:

```powershell
ollama list
```

## Instalação

```powershell
uv sync --dev
Copy-Item .env.example .env
```

O arquivo `.env` é local e ignorado pelo Git. Nenhuma credencial deve ser adicionada ao repositório.

## Ingestão da política sintética

```powershell
uv run python -m scripts.seed_demo
```

Resultado esperado:

```text
aurora_tecnologia:v1: indexed (10 trechos)
aurora_tecnologia:v2: indexed (10 trechos)
brisa_sistemas:v1: indexed (10 trechos)
```

Ao executar o comando novamente, o resultado esperado é `skipped (0 trechos)` para todas as versões. Isso comprova que a mesma carga não cria duplicatas.

O Qdrant opera em modo local persistente e armazena os dados em `.local/qdrant`, diretório ignorado pelo Git. O uso de um servidor Qdrant no Docker Compose será introduzido na fase de conteinerização.

Cada política possui um manifesto `metadata.json` com empresa, documento, versão, validade e arquivo de origem. O catálogo [questions_v1.json](data/evaluation/questions_v1.json) reúne perguntas comuns, críticas, ambíguas, sem resposta e adversariais.

Para carregar somente um manifesto:

```powershell
uv run python -m scripts.ingest data/tenants/aurora_tecnologia/metadata_v2.json
```

## Versões e exclusão lógica

- Duas versões podem permanecer gravadas ao mesmo tempo.
- A versão mais recentemente ingerida fica ativa.
- A busca ignora versões inativas.
- A exclusão lógica marca o documento como excluído, mas preserva o histórico para auditoria.
- Uma nova versão pode ser ingerida depois da exclusão e volta a participar da busca.

Na coleção atual existem 30 trechos armazenados e 20 ativos: Aurora `v1` está inativa, Aurora `v2` está ativa e Brisa `v1` está ativa.

## Regras conflitantes entre empresas

Tenant significa uma empresa isolada dentro da aplicação. A mesma pergunta deve respeitar as regras do tenant autenticado.

Para a pergunta `Qual é o limite diário de alimentação em viagem nacional?`, os dados sintéticos definem:

- Aurora Tecnologia: R$ 130,00 por pessoa na versão ativa `v2`.
- Brisa Sistemas: R$ 85,00 por pessoa.

A busca no Qdrant aplica o filtro de tenant antes de devolver os trechos ao modelo.

## Recuperação híbrida

A recuperação atual combina três partes:

- Busca densa: compara o significado da pergunta com os embeddings dos trechos.
- BM25: valoriza palavras exatas e raras presentes na pergunta e nos documentos.
- RRF: combina as posições das duas listas. Um trecho bem colocado nas duas recebe mais força.

Toda busca exige o `tenant_id` obtido do token. Tanto a busca densa quanto o BM25 recebem apenas trechos ativos, não excluídos e pertencentes à empresa autenticada.

Para reproduzir a comparação:

```powershell
uv run python -m scripts.evaluate_retrieval --output docs/evidence/phase3_retrieval_results.json
```

Nos 12 casos sintéticos atuais, a busca híbrida obteve MRR de `0,8264`, contra `0,8222` do BM25 e `0,6556` da busca densa. MRR mede quão cedo o primeiro trecho correto aparece. O Recall@5 foi `0,9167` nos três métodos.

Um caso concreto é a pergunta sobre “fornecedor e motivo da despesa”: o trecho correto ficou na posição 6 da busca densa e na posição 1 da busca híbrida.

## Re-ranking e orçamento de contexto

O projeto usa o CrossEncoder local `cross-encoder/ms-marco-MiniLM-L6-v2`. Diferente dos embeddings, ele lê a pergunta e cada trecho juntos antes de atribuir um score. Isso melhora a precisão, mas adiciona latência.

O seletor de contexto:

- limita a quantidade final de trechos;
- ignora trechos com muitas palavras repetidas em relação aos já selecionados;
- não ultrapassa o orçamento configurado de caracteres.

Para reproduzir o comparativo:

```powershell
uv run python -m scripts.evaluate_reranking --output docs/evidence/phase4_reranking_results.json
```

| Configuração | Recall@5 | MRR | Latência média | P95 |
|---|---:|---:|---:|---:|
| Híbrida sem re-ranking | 0,9167 | 0,8125 | 5,24 ms | 6,03 ms |
| CrossEncoder e contexto | 0,9167 | 0,9167 | 205,80 ms | 227,36 ms |

A partida fria observada, que inclui carregar o modelo já baixado, foi de aproximadamente 8,8 segundos. O re-ranking melhorou a qualidade média, mas uma das 12 perguntas saiu do top 5. Esse caso permanece no relatório para orientar avaliações futuras.

## Execução da API

```powershell
uv run uvicorn app.main:app --reload
```

Endpoints disponíveis:

- Interface: `http://localhost:8000/`
- Health check: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- Login: `POST http://localhost:8000/v1/auth/login`
- Perguntas: `POST http://localhost:8000/v1/ask`
- Feedback: `POST http://localhost:8000/v1/feedback`
- Readiness: `http://localhost:8000/ready`
- Métricas: `http://localhost:8000/metrics`

Exemplo de requisição:

```powershell
$login = @{
    username = "aurora.demo"
    password = "Aurora#2026"
} | ConvertTo-Json

$session = Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/v1/auth/login" `
    -ContentType "application/json" `
    -Body $login

$body = @{ question = "Em quanto tempo devo solicitar o reembolso?" } | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/v1/ask" `
    -Headers @{ Authorization = "Bearer $($session.access_token)" } `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

## Segurança multi-tenant

Credenciais totalmente sintéticas para a demonstração:

| Empresa | Usuário | Senha |
|---|---|---|
| Aurora Tecnologia | `aurora.demo` | `Aurora#2026` |
| Brisa Sistemas | `brisa.demo` | `Brisa#2026` |

As senhas acima pertencem somente ao case. O repositório armazena hashes PBKDF2, não senhas em texto aberto. O login produz um token assinado com usuário, tenant, papéis e expiração.

O corpo de `/v1/ask` aceita somente `question`. O tenant vem exclusivamente do token, é aplicado antes do retrieval e conferido novamente em cada payload recuperado.

Perguntas com padrões conhecidos de prompt injection recebem HTTP 400 antes do embedding. Prompt injection significa tentar substituir as instruções do assistente. Chunks que contêm instruções maliciosas também são removidos antes da geração.

O utilitário de logs mascara senha, token, autorização, pergunta, e-mail, CPF e cartão. O [threat model](docs/threat-model.md) documenta ameaças, impactos, controles e riscos aceitos.

## Geração confiável

O Ollama implementa uma interface comum e pode ser substituído por outro provedor sem alterar o serviço de perguntas. A saída do modelo é um JSON validado pelo Pydantic com resposta, posições das fontes e confiança.

Cada resposta inclui o campo `generation`:

- `provider` e `model`: identificam quem gerou a resposta;
- `prompt_version`: identifica as instruções usadas;
- `status`: pode ser `generated`, `degraded` ou `no_evidence`;
- `attempts`: informa quantas tentativas foram necessárias.

Falhas transitórias do Ollama são repetidas até três vezes. Backoff significa aumentar a espera entre as tentativas. Se a geração continuar indisponível, a API devolve uma resposta degradada com a melhor fonte, sem inventar conteúdo. Se nem o embedding estiver disponível, a API mantém o erro HTTP 503 conhecido porque não consegue pesquisar com segurança.

Trechos com score abaixo de `0,50` não chegam à geração. Para reduzir distrações do `llama3.2:1b`, somente a evidência mais forte é enviada por padrão. Quando não existe evidência forte, a resposta usa status `no_evidence`, confiança baixa e nenhuma fonte.

## Avaliação e regressão

O golden dataset versionado possui respostas e fontes corretas para casos respondíveis, sem resposta e adversariais. O resultado inicial separa claramente retrieval e geração:

| Configuração de retrieval | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|
| Densa | 1,0000 | 0,7556 | 0,8145 |
| Híbrida | 0,8333 | 0,7083 | 0,7384 |
| Híbrida com re-ranking | 1,0000 | 1,0000 | 1,0000 |

A geração obteve correção `0,1667`, relevância `0,1889`, completude `0,1667` e aderência às fontes `0,5000`. Os ataques tiveram bloqueio `1,0000` e vazamento entre tenants `0,0000`. A recusa adequada em perguntas sem resposta ficou em `0,5000`.

```powershell
uv run python -m scripts.evaluate_golden --output docs/evidence/phase7_golden_results.json
uv run python -m scripts.check_regression --report docs/evidence/phase7_golden_results.json
```

O [plano de avaliação](docs/evaluation-plan.md) define cada métrica e analisa os erros. O gate aprovado protege o baseline atual; os limites de geração são baixos porque refletem a medição real, não uma meta desejada.

Os números usados na apresentação do release `1.0.0` estão congelados em [release_1_0_0.json](docs/evidence/release_1_0_0.json), junto com hashes SHA-256 dos arquivos de origem.

## Observabilidade e confiabilidade

Cada resposta usa o mesmo `request_id` no corpo, no cabeçalho `X-Request-ID` e nos logs JSON. O campo `trace` informa latências de embedding, retrieval, re-ranking, geração e total, além dos documentos, versões, chunks e scores recuperados.

O evento `rag_trace` registra modelo, versão do prompt, tentativas e uso de fallback sem registrar a pergunta. `GET /metrics` apresenta volume, erros, retries, fallbacks e latências médias do processo.

`GET /health` verifica somente se a API está viva. `GET /ready` verifica se Ollama e Qdrant estão prontos para atender. SLI, SLO e o roteiro de investigação estão no [runbook](docs/runbook.md).

## Docker, CI e rollback

O Compose inicia a API e um servidor Qdrant persistente. O Ollama continua no computador porque usa os modelos locais já instalados; a API dentro do container acessa esse serviço por `host.docker.internal`.

```powershell
docker compose build
docker compose up -d
docker compose exec api python -m scripts.seed_demo
```

A imagem atual é identificada como `onfly-policy-copilot:1.0.0` e também registra `policy_answer_v1` nos labels. O [manifesto do release](release.json) liga aplicação, prompt e esquema do índice.

O pipeline em `.github/workflows/ci.yml` bloqueia formatação, lint, tipos, testes, falhas de segurança, regressão de qualidade, divergência de versões e erro de build da imagem.

- [Deploy e rollback](docs/deployment-and-rollback.md)
- [Migração segura do índice](docs/index-migration.md)

Nesta estação o Docker não está instalado. Por isso, os contratos dos artefatos foram testados localmente e o build real ficou como gate obrigatório do CI.

## Front-end demonstrativo

A raiz `http://localhost:8000/` abre uma interface responsiva servida pela própria API. Não existe uma segunda instalação ou etapa de build do front-end.

O avaliador pode:

- escolher Aurora Tecnologia ou Brisa Sistemas com credenciais sintéticas;
- fazer perguntas e acompanhar o carregamento;
- ver resposta, confiança, fontes, versões, chunks e scores;
- distinguir ausência de evidência, timeout, indisponibilidade e bloqueio de segurança;
- abrir latências e `request_id` sem exibir token ou pergunta no trace;
- enviar feedback positivo ou negativo ligado à resposta e ao tenant autenticado.

O token fica somente na memória da aba. Feedback também fica em memória e é apagado quando a API reinicia. Consulte a [arquitetura](docs/architecture.md) e o [roteiro de cinco minutos](docs/demo-script.md).

## Qualidade

```powershell
uv run ruff format --check app tests scripts
uv run ruff check app tests scripts
uv run mypy app tests scripts
node --check app/web/static/app.js
uv run pytest
```

## Limites conhecidos

- O modelo local pequeno exige prompts extrativos e pode apresentar variação de qualidade.
- A primeira consulta após iniciar o processo paga o custo de carregar o CrossEncoder.
- O golden dataset confirmou baixa correção e completude do modelo de 1B; o relatório preserva os casos exatos.
- Revogação de token e rate limiting pertencem a fases posteriores.
- As métricas atuais ficam na memória e reiniciam com o processo; persistência e alertas dependem do futuro ambiente de implantação.
- O build do Docker precisa ser confirmado pelo CI ou por uma estação com Docker instalado.
- A primeira consulta pode levar mais de dez segundos para carregar o CrossEncoder; faça um aquecimento antes da apresentação.
- Feedback não é persistente nesta demonstração.

Consulte [PROJECT_PLAN.md](PROJECT_PLAN.md) para o planejamento técnico e [PLANS.md](PLANS.md) para as evidências de execução.
