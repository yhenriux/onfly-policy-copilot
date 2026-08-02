# Onfly Policy Copilot

Case técnico independente de um assistente para consulta de políticas corporativas de viagens. A aplicação busca trechos autorizados antes de responder, mantém empresas isoladas e apresenta as fontes utilizadas.

O projeto usa somente dados sintéticos e não representa um produto oficial da Onfly.

## O que a solução demonstra

- autenticação com duas identidades fictícias;
- base de conhecimento com 50 documentos curtos sobre dúvidas comuns de viagem;
- isolamento de documentos por empresa, também chamada de tenant;
- ingestão versionada e sem duplicação;
- busca vetorial com Qdrant e busca por palavras com BM25;
- combinação dos rankings com RRF e reordenação com CrossEncoder;
- geração local com `llama3.2:1b` pelo Ollama;
- resposta estruturada, fontes, confiança, trace e `request_id`;
- bloqueio de prompt injection e mascaramento de dados em logs;
- feedback associado à resposta e ao tenant autenticado;
- avaliação reproduzível, gate de regressão, Docker e CI.

## Arquitetura resumida

```text
Navegador
   │ login e pergunta
   ▼
FastAPI ── autenticação e guardrails
   │
   ├── Ollama all-minilm ── embedding da pergunta
   │
   ├── Qdrant + BM25 ── busca filtrada por tenant
   │
   ├── RRF + CrossEncoder ── ranking e contexto
   │
   └── Ollama llama3.2:1b ── resposta estruturada
             │
             ▼
     resposta + fontes + trace
```

RAG significa geração apoiada por recuperação: o modelo recebe trechos encontrados nas políticas em vez de responder apenas com conhecimento próprio.

## Tecnologias

| Tecnologia | Função |
|---|---|
| FastAPI e Pydantic | API HTTP e validação dos contratos |
| Ollama | execução local dos modelos de embedding e geração |
| Qdrant | persistência e busca vetorial |
| BM25 e RRF | busca por palavras e combinação de rankings |
| CrossEncoder | reordenação dos trechos por relevância |
| pytest, Ruff e mypy | testes, qualidade e verificação de tipos |
| Docker Compose | API e Qdrant reproduzíveis |

## Pré-requisitos

- Python entre 3.11 e 3.14;
- [uv](https://docs.astral.sh/uv/);
- Ollama em execução;
- modelos `llama3.2:1b` e `all-minilm`;
- Docker Desktop para a execução em containers.

```powershell
ollama pull llama3.2:1b
ollama pull all-minilm
ollama list
```

## Executar localmente

```powershell
uv sync --dev
Copy-Item .env.example .env
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload
```

Acesse [http://localhost:8000](http://localhost:8000). Não abra `app/web/index.html` diretamente: a interface depende da API.

A carga inicial cria 30 trechos: Aurora `v1`, Aurora `v2` e Brisa `v1`. Somente Aurora `v2` e Brisa `v1` ficam ativas. Repetir o seed não duplica dados.

## Credenciais da demonstração

| Empresa | Usuário | Senha | Regra de alimentação |
|---|---|---|---:|
| Aurora Tecnologia | `aurora.demo` | `Aurora#2026` | R$ 130,00 por dia |
| Brisa Sistemas | `brisa.demo` | `Brisa#2026` | R$ 85,00 por dia |

As credenciais são públicas porque pertencem somente ao conjunto sintético. O repositório armazena os hashes das senhas, não senhas reais.

## Executar com Docker

O Compose inicia a API e o Qdrant. O Ollama continua no computador e é acessado pelo endereço `host.docker.internal`.

```powershell
docker compose build
docker compose up -d
docker compose exec api python -m scripts.seed_demo
```

Para encerrar:

```powershell
docker compose down
```

O volume do Qdrant é preservado. Use `docker compose down --volumes` somente quando quiser apagar conscientemente o índice criado pelo Compose.

## Endpoints principais

| Método | Caminho | Finalidade |
|---|---|---|
| `GET` | `/` | interface demonstrativa |
| `GET` | `/health` | confirma que a API está viva |
| `GET` | `/ready` | verifica Ollama e Qdrant |
| `POST` | `/v1/auth/login` | cria a sessão fictícia |
| `POST` | `/v1/ask` | consulta políticas autorizadas |
| `POST` | `/v1/feedback` | registra avaliação da resposta |
| `GET` | `/metrics` | apresenta métricas operacionais |
| `GET` | `/docs` | documentação interativa Swagger |

O corpo de `/v1/ask` aceita somente a pergunta. O tenant vem exclusivamente do token autenticado.

## Testes e qualidade

```powershell
uv run ruff format --check app tests scripts
uv run ruff check app tests scripts
uv run mypy app tests scripts
uv run pytest
```

A suíte cobre contratos HTTP, ingestão, versionamento, retrieval, re-ranking, autenticação, isolamento entre tenants, prompt injection, indisponibilidade do Ollama, logs, observabilidade, front-end, feedback, Docker e regressão de qualidade.

## Avaliações reproduzíveis

```powershell
uv run python -m scripts.evaluate_retrieval --output docs/evidence/phase3_retrieval_results.json
uv run python -m scripts.evaluate_reranking --output docs/evidence/phase4_reranking_results.json
uv run python -m scripts.evaluate_golden --output docs/evidence/phase7_golden_results.json
uv run python -m scripts.check_regression --report docs/evidence/phase7_golden_results.json
```

O resultado congelado da versão apresentada está em [`docs/evidence/release_1_0_0.json`](docs/evidence/release_1_0_0.json). A apresentação técnica está em [`docs/presentation/onfly-policy-copilot-1.0.0.pptx`](docs/presentation/onfly-policy-copilot-1.0.0.pptx).

## Estrutura do repositório

```text
app/
├── core/            configuração, autenticação, erros e logs
├── domain/          modelos e contratos da API
├── evaluation/      métricas e gate de regressão
├── feedback/        feedback ligado à requisição e ao tenant
├── generation/      provedor Ollama, prompt e fallback
├── guardrails/      proteção da pergunta, fonte e tenant
├── ingestion/       leitura, normalização, chunks e indexação
├── observability/   health, readiness, métricas e trace
├── retrieval/       Qdrant, BM25, RRF, contexto e re-ranking
├── web/             interface demonstrativa
└── main.py          ponto de entrada da API
data/
├── auth/            usuários sintéticos
├── evaluation/      perguntas, golden dataset e limites
└── tenants/         políticas e documentos de ajuda das duas empresas
docs/
├── adr/             decisões arquiteturais relevantes
├── evidence/        resultados reproduzíveis
└── presentation/    apresentação técnica
scripts/             ingestão, seed, avaliações e verificações
tests/               testes unitários, integrados e de segurança
```

## Documentação técnica

- [Arquitetura](docs/architecture.md)
- [Ameaças e controles](docs/threat-model.md)
- [Plano e métricas de avaliação](docs/evaluation-plan.md)
- [Operação e investigação de incidentes](docs/runbook.md)
- [Deploy e rollback](docs/deployment-and-rollback.md)
- [Migração segura do índice](docs/index-migration.md)
- [Roteiro de demonstração](docs/demo-script.md)

## Limitações conhecidas

- O modelo de 1B pode recusar uma resposta mesmo quando o retrieval encontrou uma fonte forte. Nesse caso, o sistema mostra a fonte em modo degradado sem inventar conteúdo.
- A primeira consulta carrega o CrossEncoder e pode ser mais lenta.
- Feedback e métricas operacionais ficam em memória e são apagados ao reiniciar a API.
- Revogação de token, rate limiting e monitoramento externo não fazem parte desta demonstração local.
