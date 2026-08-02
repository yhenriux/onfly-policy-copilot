# ADR 0005 — Geração estruturada e fallback

## Contexto

Texto livre não permite confirmar fontes, confiança ou ausência de evidência. O modelo local também pode ficar indisponível ou devolver um formato inválido.

## Decisão

Usar uma interface comum de provedor. O Ollama devolve JSON validado pelo Pydantic com resposta, posições das fontes e confiança. O prompt recebe a versão `policy_answer_v1`.

Falhas transitórias usam novas tentativas com espera crescente. Falha final de geração devolve uma resposta degradada sem afirmação factual. Falha de embedding mantém HTTP 503, pois não existe recuperação segura sem o vetor da pergunta.

Somente evidências com score mínimo de `0,50` participam da geração e, para o modelo de 1B atual, apenas o trecho mais forte é enviado por padrão.

## Consequências

- Respostas identificam provedor, modelo, prompt, status e quantidade de tentativas.
- O serviço rejeita posições de fontes que não existiam no contexto autorizado.
- Perguntas sem evidência forte não chegam ao gerador.
- O fallback preserva o contrato, mas não tenta responder quando o modelo falha.
- A estratégia de uma evidência por padrão reduz distrações, porém pode limitar perguntas que exigem combinar várias seções.
