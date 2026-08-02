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

## Pipeline RAG em detalhes

O pipeline abaixo explica o caminho completo entre uma política e uma resposta. Os nomes técnicos aparecem acompanhados de uma explicação simples.

```text
Documentos de políticas
        ↓
Leitura, normalização e divisão por seção
        ↓
Embeddings com all-minilm
        ↓
Qdrant + índice BM25
        ↓
Pergunta autenticada e filtro obrigatório por empresa
        ↓
Busca híbrida → RRF → CrossEncoder
        ↓
Contexto sem repetições e com tamanho controlado
        ↓
Resposta fundamentada, fontes e confiança
```

1. Os documentos sintéticos de cada empresa são lidos, normalizados e divididos em trechos menores. A divisão preserva títulos e seções para manter o sentido da regra.
2. Cada trecho recebe um *embedding*: uma representação numérica do seu significado, gerada localmente pelo modelo `all-minilm`.
3. Os trechos, seus embeddings e metadados são guardados no Qdrant. Os metadados incluem empresa, documento, versão, seção, validade e estado ativo. Hashes evitam a duplicação durante uma nova carga.
4. Ao entrar, a pessoa recebe um token sintético assinado. A empresa vem desse token; ela nunca é enviada pelo navegador no corpo da pergunta.
5. A pergunta passa por uma checagem de segurança. Em seguida, a busca vetorial encontra trechos com significado parecido e o BM25 encontra palavras importantes. O filtro da empresa autenticada é aplicado em toda recuperação.
6. O RRF combina os dois rankings de busca. Depois, o CrossEncoder compara diretamente pergunta e trecho para ordenar os candidatos mais relevantes.
7. O sistema remove trechos repetidos e limita o tamanho do contexto. Assim, o modelo recebe evidências suficientes sem uma quantidade desnecessária de texto.
8. Para as perguntas frequentes de bagagem, hotel, reembolso e transporte por aplicativo, a aplicação monta uma resposta clara a partir das fontes recuperadas. Nas demais perguntas, o `llama3.2:1b` gera uma resposta estruturada usando somente o contexto autorizado.
9. A API devolve a resposta, as fontes usadas, a confiança e um `request_id`, que é o identificador da requisição. Quando não há evidência suficiente, ela informa isso em vez de inventar uma política.

Leia a descrição completa em [Pipeline RAG](docs/rag-pipeline-explicacao-local-v1.md).

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

A carga inicial indexa as políticas versionadas e os catálogos de dúvidas das duas empresas sintéticas. Somente a versão ativa de cada política participa da busca. Repetir o seed não duplica dados.

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

- [Catálogo e organização do repositório](docs/repositorio-catalogo-classificacao-github-v1.md)
- [Arquitetura](docs/rag-arquitetura-explicacao-local-v1.md)
- [Pipeline RAG](docs/rag-pipeline-explicacao-local-v1.md)
- [Prova de conceito](docs/rag-prova-validacao-tecnica-v1.md)
- [Guia do código RAG](docs/rag-codigo-navegacao-tecnica-v1.md)
- [Ameaças e controles](docs/rag-seguranca-modelagem-tecnica-v1.md)
- [Plano e métricas de avaliação](docs/rag-avaliacao-metricas-qualidade-v1.md)
- [Operação e investigação de incidentes](docs/rag-operacao-procedimento-local-v1.md)
- [Deploy e rollback](docs/rag-deploy-procedimento-operacao-v1.md)
- [Migração segura do índice](docs/rag-indice-migracao-operacao-v1.md)
- [Roteiro de demonstração](docs/rag-demonstracao-roteiro-avaliacao-v1.md)

## Limitações conhecidas

- O modelo de 1B pode recusar uma resposta mesmo quando o retrieval encontrou uma fonte forte. Nesse caso, o sistema mostra a fonte em modo degradado sem inventar conteúdo.
- A primeira consulta carrega o CrossEncoder e pode ser mais lenta.
- Feedback e métricas operacionais ficam em memória e são apagados ao reiniciar a API.
- Revogação de token, rate limiting e monitoramento externo não fazem parte desta demonstração local.
