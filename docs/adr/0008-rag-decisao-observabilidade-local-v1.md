# ADR 0008 — Observabilidade local por requisição

## Contexto

Uma resposta precisa ser investigável sem guardar pergunta, token ou dados pessoais. Também precisamos distinguir processo vivo de dependências prontas.

## Decisão

Cada requisição recebe um `request_id`, reutiliza um valor enviado em `X-Request-ID` e o devolve no mesmo cabeçalho. Logs estruturados em JSON e o trace da resposta registram tempos, modelo, prompt, documentos, scores, retries e fallback.

`/health` informa somente que a API está viva. `/ready` verifica Ollama e Qdrant separadamente. `/metrics` expõe contadores e médias mantidos no processo.

## Consequências

- Uma execução pode ser localizada pelo mesmo identificador.
- Perguntas e credenciais não entram nos logs.
- As métricas em memória reiniciam junto com o processo e ainda não calculam percentis.
- Uma plataforma de monitoramento futura poderá consumir os mesmos nomes de eventos e métricas.
