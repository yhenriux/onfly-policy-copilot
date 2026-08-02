# Migração segura do índice

Este procedimento deve ser usado quando mudar o modelo de embeddings, a dimensão do vetor ou a estrutura dos payloads. Payload é o conjunto de metadados guardado junto de cada vetor.

## Regra principal

Nunca altere a coleção ativa no mesmo lugar. Crie uma nova coleção com nome versionado, carregue todos os documentos, valide e somente depois direcione a aplicação para ela.

## Procedimento

1. Registre no `release.json` a nova `index_schema_version`.
2. Crie um novo nome, por exemplo `onfly_policy_documents_phase2_v2`.
3. Mantenha a coleção anterior sem alterações.
4. Configure temporariamente `QDRANT_COLLECTION` com o nome novo.
5. Execute a ingestão completa usando o novo modelo de embeddings e o novo payload.
6. Confira quantidade de chunks, tenants, documentos, versões, dimensão dos vetores e campos obrigatórios.
7. Execute testes de isolamento, golden dataset e gate de regressão contra a nova coleção.
8. Faça uma consulta sintética para Aurora e outra para Brisa.
9. Atualize a configuração da API e reinicie somente a API.
10. Observe erros, latência, fallbacks e qualidade antes de encerrar a migração.

## Rollback do índice

Se qualquer validação falhar, restaure `QDRANT_COLLECTION` para o nome anterior e reinicie a API. Como a coleção antiga não foi modificada, o retorno não exige reingestão.

## Limpeza

A coleção antiga só pode ser removida depois da janela de observação, do aceite das métricas e de um backup confirmado. A remoção não faz parte do comando de migração.
