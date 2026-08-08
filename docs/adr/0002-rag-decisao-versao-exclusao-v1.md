# ADR 0002 — Versão ativa e exclusão lógica

## Situação

As políticas mudam ao longo do tempo. O sistema precisa preservar versões anteriores para auditoria, mas não pode usar regras antigas nas respostas.

ADR significa registro de decisão arquitetural. Este documento explica uma escolha importante para a estrutura do projeto.

## Decisão

Cada trecho possui dois campos de controle:

- `search_status`: informa se a versão está ativa para participar da busca.
- `deletion_status`: informa se o documento foi excluído de forma lógica.

Ao ingerir uma nova versão, as anteriores recebem `search_status=inactive`. A nova versão recebe `search_status=active` e `deletion_status=available`.

Ao excluir um documento, todas as versões devem receber `search_status=inactive` e `deletion_status=deleted`.

## Motivo

Essa escolha preserva o histórico sem permitir que regras antigas ou excluídas apareçam nas respostas.

## Consequências

- A busca sempre filtra pontos ativos e não excluídos.
- O histórico ocupa espaço, mas permanece disponível para auditoria.
- Uma nova versão reativa o documento sem alterar as versões anteriores.

