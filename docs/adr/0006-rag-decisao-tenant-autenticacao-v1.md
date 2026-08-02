# ADR 0006 — Tenant derivado de token assinado

## Contexto

Receber `tenant_id` no corpo permite que o cliente tente escolher outra empresa. O isolamento precisa começar em uma identidade validada e continuar depois da recuperação.

## Decisão

Usar login sintético com senhas armazenadas por hash PBKDF2 e emitir um token demonstrativo assinado por HMAC-SHA256. O token contém usuário, tenant, papéis e expiração.

O endpoint `/v1/ask` recebe somente a pergunta. O tenant autenticado é aplicado ao retrieval e cada chunk retornado é conferido novamente. Prompt injections conhecidas são bloqueadas e chunks com instruções maliciosas são retirados do contexto.

## Consequências

- O cliente não escolhe mais o tenant da consulta.
- Um erro no filtro primário ainda é contido pela validação pós-retrieval.
- O front-end futuro poderá demonstrar dois logins e regras conflitantes.
- O token próprio é adequado somente para o case local; produção deve usar um provedor de identidade.
