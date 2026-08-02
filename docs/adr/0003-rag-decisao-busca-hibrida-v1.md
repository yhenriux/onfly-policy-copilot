# ADR 0003 — Recuperação híbrida com BM25 e RRF

## Contexto

A busca densa entende significado, mas pode posicionar mal trechos que dependem de palavras corporativas exatas. O BM25 cobre esse segundo tipo de consulta.

## Decisão

Executar busca densa e BM25 dentro do mesmo tenant e combinar as posições com RRF. RRF significa fusão por posição recíproca: quanto mais perto do início de uma lista, maior a contribuição do item.

Os pesos e a constante do RRF são configuráveis. O BM25 usa somente payloads ativos e não excluídos já armazenados no Qdrant.

## Consequências

- A aplicação melhora consultas com termos exatos sem abandonar a comparação semântica.
- O ranking final pode ser reproduzido e explicado pelas posições de cada busca.
- Não há um índice lexical persistente separado nesta escala pequena.
- Uma implantação com muitos documentos deverá avaliar um índice lexical dedicado.
