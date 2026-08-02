# Catálogo e organização do repositório

Este catálogo organiza o repositório como um acervo técnico. Ele usa uma adaptação das facetas de Ranganathan para que o nome de um documento indique, de forma previsível, o que ele é e para que serve.

## Regra de nomenclatura

Documentos que não participam de imports, comandos, testes ou caminhos de execução seguem este padrão:

```text
assunto-tipo-finalidade-contexto-versao.extensao
```

As cinco facetas são:

| Faceta | Pergunta simples | Exemplo |
|---|---|---|
| Assunto | Sobre o que é? | `rag` |
| Tipo | Que material é? | `pipeline` |
| Finalidade | O que ele faz? | `explicacao` |
| Contexto | Onde se aplica? | `local` |
| Versão | Qual recorte temporal? | `v1` |

Exemplo: `rag-pipeline-explicacao-local-v1.md` descreve o pipeline RAG, é uma explicação, vale para a execução local e registra sua primeira versão documental.

## Limites intencionais

Nem todo arquivo deve ser renomeado. Código Python, arquivos de dados, configurações, evidências congeladas e fluxos de CI possuem nomes ou caminhos usados pelo próprio projeto. Alterá-los apenas para padronização visual aumenta risco sem trazer benefício ao leitor.

Esses itens mantêm nomes estáveis e são classificados pelo diretório, comentários e documentação. Assim, a organização melhora a navegação sem quebrar imports, scripts, testes, histórico de avaliação ou comandos do README.

## Coleções do repositório

| Pasta | Assunto | Tipo | Finalidade | Contexto | Versão ou estado |
|---|---|---|---|---|---|
| `app/` | aplicação | código Python | executar a API e o RAG | local e container | versão corrente |
| `app/web/` | interface | HTML, CSS e JavaScript | oferecer a demonstração | navegador | versão corrente |
| `data/` | conhecimento sintético | documentos e catálogos | alimentar o RAG e as avaliações | Aurora e Brisa | versões dos dados |
| `docs/` | documentação | Markdown e apresentação | explicar decisões e operação | GitHub | versão documental `v1` |
| `docs/adr/` | decisões arquiteturais | registros de decisão | preservar o porquê das escolhas | arquitetura RAG | decisão numerada e `v1` |
| `docs/evidence/` | evidências | JSON reproduzível | congelar resultados de avaliação | release apresentada | nomes preservados por scripts e CI |
| `docs/presentation/` | apresentação | PowerPoint | apoiar a demonstração técnica | avaliação | versão de release |
| `scripts/` | automação | Python executável | ingerir, avaliar e verificar | desenvolvimento e CI | versão corrente |
| `tests/` | qualidade | testes automatizados | comprovar comportamento e segurança | local e CI | versão corrente |
| `.github/` | automação remota | workflow YAML | executar verificações no GitHub | CI | versão corrente |

## Documentos classificados

| Arquivo | Assunto | Tipo | Finalidade | Contexto | Versão |
|---|---|---|---|---|---|
| [`rag-arquitetura-explicacao-local-v1.md`](rag-arquitetura-explicacao-local-v1.md) | RAG | arquitetura | explicar componentes | local | v1 |
| [`rag-pipeline-explicacao-local-v1.md`](rag-pipeline-explicacao-local-v1.md) | RAG | pipeline | explicar fluxo | local | v1 |
| [`rag-prova-validacao-tecnica-v1.md`](rag-prova-validacao-tecnica-v1.md) | RAG | prova | validar hipótese | técnica | v1 |
| [`rag-codigo-navegacao-tecnica-v1.md`](rag-codigo-navegacao-tecnica-v1.md) | RAG | código | navegar implementação | técnica | v1 |
| [`rag-seguranca-modelagem-tecnica-v1.md`](rag-seguranca-modelagem-tecnica-v1.md) | RAG | segurança | modelar ameaças e controles | técnica | v1 |
| [`rag-avaliacao-metricas-qualidade-v1.md`](rag-avaliacao-metricas-qualidade-v1.md) | RAG | avaliação | medir qualidade | qualidade | v1 |
| [`rag-operacao-procedimento-local-v1.md`](rag-operacao-procedimento-local-v1.md) | RAG | operação | investigar incidentes | local | v1 |
| [`rag-deploy-procedimento-operacao-v1.md`](rag-deploy-procedimento-operacao-v1.md) | RAG | deploy | orientar entrega e retorno | operação | v1 |
| [`rag-indice-migracao-operacao-v1.md`](rag-indice-migracao-operacao-v1.md) | RAG | índice | migrar dados com segurança | operação | v1 |
| [`rag-demonstracao-roteiro-avaliacao-v1.md`](rag-demonstracao-roteiro-avaliacao-v1.md) | RAG | demonstração | conduzir apresentação | avaliação | v1 |
| [`repositorio-catalogo-classificacao-github-v1.md`](repositorio-catalogo-classificacao-github-v1.md) | repositório | catálogo | classificar o acervo | GitHub | v1 |

## Decisões arquiteturais classificadas

Os ADRs mantêm a numeração cronológica para preservar o histórico. Após o número, os nomes seguem assunto, tipo, decisão, contexto e versão.

| Documento | Decisão registrada |
|---|---|
| `0001-rag-decisao-colecao-qdrant-v1.md` | coleção e versão no Qdrant |
| `0002-rag-decisao-versao-exclusao-v1.md` | versão ativa e exclusão lógica |
| `0003-rag-decisao-busca-hibrida-v1.md` | BM25, busca vetorial e RRF |
| `0004-rag-decisao-reranking-contexto-v1.md` | CrossEncoder e orçamento de contexto |
| `0005-rag-decisao-geracao-fallback-v1.md` | saída estruturada e fallback |
| `0006-rag-decisao-tenant-autenticacao-v1.md` | empresa derivada do token |
| `0007-rag-decisao-avaliacao-regressao-v1.md` | golden dataset e gate de regressão |
| `0008-rag-decisao-observabilidade-local-v1.md` | logs, métricas e readiness |
| `0009-rag-decisao-interface-feedback-v1.md` | front-end e feedback por requisição |

## Arquivos preservados por estabilidade técnica

| Grupo | Motivo para não renomear |
|---|---|
| `README.md`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `compose.yaml`, `release.json` | São convenções de ferramentas, comandos ou release. |
| `data/**/*.json` e `data/**/*.md` | São lidos pelos catálogos de ingestão e representam documentos da base de conhecimento. |
| `docs/evidence/*.json` | São saídas reproduzíveis citadas por scripts, CI e release congelada. |
| `docs/presentation/*.pptx` | É o artefato de apresentação já associado à versão apresentada. |
| `app/**/*.py`, `scripts/**/*.py`, `tests/**/*.py` | Os nomes participam de imports, execução de módulos e descoberta automática de testes. |

## Limpeza aplicada

Não foram encontrados arquivos vazios rastreados pelo Git. Caches, ambiente virtual, cobertura de testes e logs locais são ignorados por [`.gitignore`](../.gitignore) e não fazem parte do repositório publicado. Eles podem ser apagados localmente sem mudar o conteúdo do GitHub.
