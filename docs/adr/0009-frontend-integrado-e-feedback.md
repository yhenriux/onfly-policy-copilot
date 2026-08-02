# ADR 0009 — Front-end integrado e feedback em memória

## Contexto

O avaliador precisa percorrer autenticação, consulta, fontes, estados operacionais, trace e feedback sem instalar uma segunda aplicação.

## Decisão

O FastAPI serve um front-end em HTML, CSS e JavaScript sem dependências externas. O token permanece somente na memória da aba. A API registra a relação entre `request_id` e tenant e aceita feedback somente do mesmo tenant autenticado.

O retrieval síncrono e pesado roda em uma thread de trabalho. Assim, health e readiness continuam respondendo durante o carregamento do CrossEncoder.

## Consequências

- Um único comando inicia API e interface.
- Não existe etapa de build do front-end.
- Reiniciar a API apaga feedbacks, pois o armazenamento é demonstrativo e fica em memória.
- Persistência de feedback e revogação de tokens seriam requisitos de produção.
