# ADR 0002 — Versão ativa e exclusão lógica

## Situação

As políticas mudam ao longo do tempo. O sistema precisa preservar versões anteriores para auditoria, mas não pode usar regras antigas nas respostas.

ADR significa registro de decisão arquitetural. Este documento explica uma escolha importante para a estrutura do projeto.

## Decisão

Cada trecho possui dois campos de controle:

- `is_active`: informa se a versão pode participar da busca.
- `is_deleted`: informa se o documento foi excluído de forma lógica.

Ao ingerir uma nova versão, as anteriores recebem `is_active=false`. A nova versão recebe `is_active=true` e `is_deleted=false`.

Ao excluir um documento, todas as versões recebem `is_active=false` e `is_deleted=true`.

## Motivo

Essa escolha preserva o histórico sem permitir que regras antigas ou excluídas apareçam nas respostas.

## Consequências

- A busca sempre filtra pontos ativos e não excluídos.
- O histórico ocupa espaço, mas permanece disponível para auditoria.
- Uma nova versão reativa o documento sem alterar as versões anteriores.

