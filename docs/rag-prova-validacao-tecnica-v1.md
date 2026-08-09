# Prova de conceito: Onfly Policy Copilot

## Objetivo

Esta prova de conceito verifica se um assistente de IA pode responder dúvidas sobre políticas corporativas de viagem com evidências rastreáveis, regras diferentes por empresa e controles básicos de segurança.

O projeto usa dados, empresas, credenciais e políticas inteiramente sintéticos. Ele não é um produto oficial da Onfly e não utiliza dados de clientes, colaboradores ou operações reais.

## Problema demonstrado

Políticas corporativas costumam estar distribuídas em documentos longos e podem mudar conforme a empresa, a versão e o tipo de despesa. Uma resposta útil precisa encontrar a regra certa, respeitar quem pode vê-la e mostrar de onde a informação veio.

## Hipótese validada

> É possível combinar recuperação de documentos, geração local e controles de isolamento para responder perguntas sobre políticas de viagem sem depender apenas da memória do modelo.

## Escopo da demonstração

| Capacidade | Como é demonstrada |
|---|---|
| Consulta de políticas | A pessoa pergunta em linguagem natural pela interface ou pela API. |
| Empresas com regras diferentes | Aurora Tecnologia e Brisa Sistemas possuem políticas sintéticas próprias. |
| Isolamento de dados | A empresa vem do token autenticado; a busca só considera seus documentos. |
| Recuperação com evidências | A aplicação encontra trechos relevantes antes de responder. |
| Resposta rastreável | A resposta devolve fontes, confiança e identificador da requisição. |
| Respostas frequentes claras | Bagagem, hospedagem, reembolso e transporte por aplicativo recebem síntese baseada nas fontes recuperadas. |
| Segurança básica | Tentativas conhecidas de alterar as instruções do assistente são bloqueadas ou sinalizadas. |
| Confiabilidade | Timeout, tentativa controlada, fallback, health check, readiness e logs estruturados fazem parte do fluxo. |

## Fluxo que pode ser testado

1. A pessoa abre a interface e escolhe uma identidade fictícia.
2. A API autentica a identidade e cria um token assinado com a empresa autorizada.
3. A pessoa envia uma pergunta, sem informar a empresa no corpo da requisição.
4. A aplicação valida a pergunta e procura documentos somente da empresa presente no token.
5. A busca híbrida encontra evidências por significado e por termos importantes.
6. Os melhores trechos são reordenados e enviados como contexto autorizado.
7. A aplicação devolve uma resposta clara, as fontes utilizadas, a confiança e um `request_id`.
8. A mesma pergunta pode gerar respostas diferentes para Aurora e Brisa porque suas políticas sintéticas são diferentes.

## Exemplo de validação

A pergunta “Quanto posso gastar com hotel?” permite verificar duas propriedades ao mesmo tempo:

- na Aurora Tecnologia, a resposta usa a política ativa da Aurora;
- na Brisa Sistemas, a resposta usa a política ativa da Brisa;
- fontes de uma empresa não aparecem para a outra;
- a interface apresenta a regra em linguagem simples e mantém os detalhes técnicos separados.

Outras perguntas prontas na interface testam bagagem despachada, prazo de reembolso e transporte por aplicativo.

## Como a hipótese é sustentada

O pipeline reúne divisão de documentos por seção, embeddings locais com `all-minilm`, Qdrant, BM25, RRF e CrossEncoder. Em termos simples: ele primeiro encontra trechos relevantes, combina busca por significado e por palavras, reorganiza os melhores resultados e só então prepara a resposta.

O modelo local `llama3.2:1b` é usado quando a pergunta não pertence ao conjunto de perguntas frequentes tratadas diretamente pelas evidências recuperadas. Se não houver suporte suficiente na base, a aplicação informa essa limitação em vez de criar uma regra.

Consulte [Pipeline RAG](rag-pipeline-explicacao-local-v1.md) para a descrição técnica completa e [Arquitetura](rag-arquitetura-explicacao-local-v1.md) para a organização dos componentes.

## Critérios de sucesso

Esta prova de conceito é considerada bem-sucedida quando:

- a API, o Qdrant e o Ollama estão disponíveis localmente;
- no cenário Docker, API, worker, RabbitMQ, Redis e Neo4j aparecem ativos em `docker compose ps`;
- uma pergunta válida retorna resposta e pelo menos uma fonte autorizada quando há evidência;
- a mesma pergunta retorna regras distintas para as duas empresas fictícias, quando aplicável;
- nenhuma consulta da Aurora recupera conteúdo da Brisa, ou o contrário;
- perguntas suspeitas e falhas do provedor retornam respostas HTTP controladas;
- testes automatizados cobrem os fluxos principais de recuperação, segurança e geração.

Os comandos reproduzíveis estão no [README](../README.md#testes-e-qualidade), e o estado operacional está descrito no [runbook](rag-operacao-procedimento-local-v1.md#verificação-rápida).

## O que esta prova de conceito não pretende demonstrar

- autenticação corporativa real, integração com SSO ou gestão de usuários reais;
- políticas corporativas reais ou conexão com bases de produção;
- escala, alta disponibilidade ou monitoramento externo de produção;
- aprovação automática de despesas ou reserva de viagens;
- uso de provedores comerciais de IA ou infraestrutura em nuvem.

Esses limites são intencionais: a demonstração prioriza a validação técnica do RAG, da rastreabilidade, do isolamento entre empresas e da experiência de consulta antes de decisões de produto ou operação em escala.
