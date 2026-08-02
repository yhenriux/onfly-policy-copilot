# ADR 0007 — Golden dataset e gate de regressão

## Contexto

Testes funcionais não mostram se uma alteração melhorou ou piorou a qualidade do RAG. Retrieval e geração também podem falhar por motivos diferentes.

## Decisão

Versionar um golden dataset com respostas e fontes esperadas. Medir retrieval, geração e segurança separadamente e salvar o relatório real no repositório.

O gate usa limites versionados e retorna erro quando uma métrica mínima cai ou quando a taxa de vazamento passa de zero.

## Consequências

- Mudanças podem ser comparadas de forma reproduzível.
- O relatório mostra que o retrieval reordenado está forte e a geração local ainda é fraca.
- Limites baixos de geração preservam o baseline, mas não devem ser tratados como meta de produto.
- Melhorias futuras precisam elevar também os limites do gate.
