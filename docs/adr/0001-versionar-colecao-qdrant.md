# ADR 0001 — Versionar o nome da coleção do Qdrant

## Situação

A Fase 1 adicionou versão e validade aos metadados de cada trecho. A coleção criada na Fase 0 ainda continha seis pontos sem esses campos.

ADR significa registro de decisão arquitetural. Este documento explica uma escolha que afeta a estrutura técnica do projeto.

## Decisão

A Fase 1 usa a coleção `onfly_policy_documents_phase1`. A nova carga possui 20 pontos, todos com versão e validade.

## Motivo

O modo local do Qdrant preservou pontos antigos ao apagar e recriar uma coleção com o mesmo nome dentro do mesmo processo. Um nome novo evita misturar formatos diferentes e torna a mudança visível.

## Consequências

- A aplicação consulta somente dados com o formato atual.
- A coleção antiga permanece apenas no armazenamento local ignorado pelo Git.
- A Fase 2 implementará versionamento e migração de documentos de forma explícita.

