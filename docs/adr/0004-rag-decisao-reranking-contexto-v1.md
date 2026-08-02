# ADR 0004 — CrossEncoder e orçamento de contexto

## Contexto

A recuperação híbrida encontra bons candidatos, mas seus scores não comparam pergunta e trecho diretamente. Além disso, enviar trechos repetidos aumenta o contexto sem acrescentar evidência.

## Decisão

Reordenar os dez candidatos com o modelo local `cross-encoder/ms-marco-MiniLM-L6-v2`. Depois, selecionar até cinco trechos, removendo redundância por palavras compartilhadas e respeitando um limite total de caracteres.

Os logits, que são scores brutos do CrossEncoder, são convertidos pela função sigmoide para o intervalo entre zero e um antes de entrar no contrato da API.

## Consequências

- O MRR do conjunto sintético aumentou de `0,8125` para `0,9167`.
- A latência média aquecida aumentou de `5,24 ms` para `205,80 ms`.
- A partida fria observada foi de aproximadamente `8,8 s`.
- Um caso piorou e continuará no conjunto de avaliação para impedir que o ganho médio esconda regressões específicas.
