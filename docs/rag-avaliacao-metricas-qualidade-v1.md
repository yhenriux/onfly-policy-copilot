# Plano de avaliação e regressão

## Relação com o front-end

O front-end demonstrativo não possui uma lógica paralela de resposta. Ele usa os mesmos endpoints autenticados avaliados pelo golden dataset e exibe sem alteração resposta, fontes, confiança e trace. Feedback positivo ou negativo é uma evidência de uso, não substitui as métricas reproduzíveis nem altera automaticamente o gate de regressão.

## Objetivo

Medir retrieval, geração e segurança separadamente. Essa separação mostra se um erro nasceu na busca das fontes ou na resposta do modelo.

## Golden dataset

O arquivo `data/evaluation/golden_dataset_v1.json` contém dez casos sintéticos versionados:

- seis perguntas respondíveis;
- duas perguntas sem resposta nas políticas;
- duas tentativas adversariais de prompt injection.

Cada caso respondível registra resposta esperada, termos centrais, documento, versão e seção correta.

## Métricas de retrieval

- Recall@5: parcela dos casos em que a seção correta apareceu entre os cinco primeiros resultados.
- MRR: média do inverso da primeira posição correta. Quanto mais perto de 1, mais cedo a fonte aparece.
- nDCG@5: valoriza posições altas com desconto logarítmico, ou seja, a perda aumenta quando a fonte correta desce no ranking.

As três configurações comparadas são busca densa, busca híbrida e busca híbrida com re-ranking.

## Métricas de geração

- Correção: parcela das respostas que contém todos os termos centrais esperados.
- Relevância: F1 de palavras entre resposta real e resposta de referência. F1 equilibra precisão e cobertura.
- Completude: parcela média dos termos centrais presentes.
- Aderência às fontes: parcela das respostas que cita documento, versão e seção corretos.

As métricas são determinísticas e não usam outro modelo como juiz. Isso facilita reprodução, embora não substitua uma revisão humana futura.

## Métricas de segurança

- Taxa de recusa sem resposta: parcela dos casos sem evidência que retorna `no_evidence` e zero fontes.
- Taxa de bloqueio adversarial: parcela dos ataques bloqueados antes da geração.
- Taxa de vazamento entre tenants: parcela dos ataques que devolve fontes de outro tenant.

## Resultado inicial

| Configuração | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|
| Densa | 1,0000 | 0,7556 | 0,8145 |
| Híbrida | 0,8333 | 0,7083 | 0,7384 |
| Híbrida com re-ranking | 1,0000 | 1,0000 | 1,0000 |

| Geração | Resultado |
|---|---:|
| Correção | 0,1667 |
| Relevância | 0,1889 |
| Completude | 0,1667 |
| Aderência às fontes | 0,5000 |

| Segurança | Resultado |
|---|---:|
| Recusa adequada sem resposta | 0,5000 |
| Bloqueio adversarial | 1,0000 |
| Vazamento entre tenants | 0,0000 |

## Análise de erros

- O re-ranking levou todas as fontes corretas para a primeira posição.
- O modelo leve `llama3.2:3b` ainda pode recusar fontes fortes; a camada factual e o golden dataset monitoram esse comportamento.
- Três perguntas respondíveis viraram `no_evidence` porque o modelo não produziu uma citação válida.
- A pergunta sobre vacina recebeu a resposta inventada `Não`, apesar de a política não tratar do assunto.
- Os dois ataques foram bloqueados e nenhum tenant vazou dados.

O gargalo atual é geração, não retrieval. Troca de modelo, ajuste de prompt ou resposta extrativa determinística são hipóteses para uma fase futura, sempre comparadas contra este baseline.

## Execução

```powershell
uv run python -m scripts.evaluate_golden --output docs/evidence/phase7_golden_results.json
uv run python -m scripts.check_regression --report docs/evidence/phase7_golden_results.json
```

## Gate de regressão

Os limites estão em `data/evaluation/regression_thresholds_v1.json`. O comando encerra com código diferente de zero quando uma métrica mínima cai ou quando vazamento ultrapassa zero.

Os limites atuais ficam ligeiramente abaixo do primeiro baseline real. Eles evitam piora, mas não representam a meta final de qualidade. Quando uma melhoria estável elevar uma métrica, o limite correspondente deve subir no mesmo pull request.
