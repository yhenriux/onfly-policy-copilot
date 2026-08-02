# Design QA

## Evidências

- Referência visual: `C:\Users\yhenr\.codex\generated_images\019fbeed-7706-70b3-84ac-72d9839b4180\exec-ffb8d0d8-e307-4e47-97bc-2f2865cafa5d.png`
- Implementação: `http://localhost:8000/`, capturada no navegador integrado em 2026-08-02.
- Viewport de comparação: desktop, 1248 × 788 CSS px. A referência é 1440 × 1024 px; a composição foi comparada por regiões, sem normalização de densidade.
- Estado: Aurora autenticada, pergunta preenchida. O navegador integrado não expõe `window.fetch` ao contexto de teste e, por isso, não conseguiu renderizar a resposta gerada nesse ambiente. A API foi validada separadamente com login e `POST /v1/ask` locais.

## Comparação

### Tipografia e conteúdo

Os títulos, rótulos técnicos e valores de métricas usam uma hierarquia curta e legível. O texto auxiliar do produto deixou de usar caixa alta, para não competir com a resposta. A nomenclatura preserva os termos que um engenheiro precisa encontrar: Top-k, score, retrieval, re-ranking, custo e protocolo.

### Espaçamento e layout

A resposta passa a ser a coluna principal; as evidências ficam em uma coluna lateral própria. O trace ocupa uma faixa inferior contínua, seguindo a sequência do pipeline. Em larguras menores que 1080 px, as colunas se empilham; abaixo de 720 px, a linha do tempo vira uma grade para evitar corte horizontal.

### Cores e tokens

Foram mantidos os tokens existentes da Onfly: azul para ação e progresso, verde para estados aprovados e cinzas neutros para informação secundária. Bordas sutis substituem sombras excessivas.

### Imagens e ícones

O fluxo não exige imagens ou ilustrações. Nenhum ativo visual do alvo foi substituído por desenho em CSS; os símbolos já existentes foram preservados como parte da interface funcional.

## Findings

- [P3] O navegador integrado não executou a chamada `fetch` da página durante a automação, embora o login, `GET /ready` e `POST /v1/ask` tenham sido validados localmente. Isso impede comparar a resposta preenchida nesse ambiente específico.
  - Impacto: não afeta o contrato da API, mas deixa uma lacuna na captura visual automatizada do estado com resposta.
  - Próximo passo: abrir `http://localhost:8000/` no navegador local comum e executar uma das perguntas rápidas para uma captura adicional.

## Interações validadas

- Login demonstrativo da Aurora.
- Renderização do espaço de consulta, estado da API e perguntas rápidas.
- Validação de sintaxe do JavaScript.
- Teste de integração de front-end e feedback: 4 aprovados.
- API local: `GET /ready`, login e consulta `reembolso` retornaram resposta, fontes, trace e Top-k.

## Resultado final

final result: passed
