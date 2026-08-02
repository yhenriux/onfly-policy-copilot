# Threat model — segurança multi-tenant

## Objetivo

Este documento descreve como o case protege dados sintéticos de empresas diferentes. Threat model significa mapear ameaças, impactos e controles antes que um incidente aconteça.

## Ativos protegidos

- Políticas corporativas de cada tenant.
- Contexto autenticado de usuário, tenant e papéis.
- Tokens e credenciais demonstrativas.
- Perguntas enviadas ao assistente.
- Fontes recuperadas e respostas geradas.

## Fronteiras de confiança

1. O navegador ou cliente não é confiável.
2. O endpoint de login valida credenciais sintéticas e emite um token assinado.
3. A API confia no tenant somente depois de validar a assinatura e a expiração.
4. O retrieval recebe o tenant autenticado e filtra o Qdrant.
5. Cada payload retornado é conferido novamente antes da geração.
6. Documentos são dados, nunca instruções de sistema.
7. Ollama e Qdrant são dependências locais e podem falhar sem quebrar o contrato público.

## Ameaças e controles

| Ameaça | Impacto | Controle preventivo | Controle de detecção |
|---|---|---|---|
| Usuário altera `tenant_id` no corpo | Acesso a outra empresa | O campo não existe mais no contrato; tenant vem do token | Teste espera HTTP 422 para campo forjado |
| Token adulterado | Falsificação de usuário ou tenant | Assinatura HMAC-SHA256 e comparação segura | Teste rejeita token modificado |
| Token expirado | Uso prolongado de uma sessão roubada | Prazo de validade no token | Erro HTTP 401 e teste automatizado de expiração |
| Senha descoberta | Acesso indevido ao tenant | PBKDF2 com salt; somente hashes no repositório | Falhas de login podem virar métrica na Fase 8 |
| Filtro de tenant ausente | Vazamento entre empresas | Tenant obrigatório em cada retriever | Validação pós-retrieval bloqueia payload divergente |
| Prompt injection na pergunta | Alteração das regras do assistente | Padrões conhecidos são bloqueados antes do embedding | HTTP 400 e teste adversarial |
| Instrução maliciosa em documento | Documento tenta comandar o modelo | Chunk sinalizado é removido do contexto | Teste confirma zero chamadas ao gerador |
| Modelo cita fonte inexistente | Resposta sem autorização | Posições citadas são validadas contra o contexto | Saída inválida vira fallback degradado |
| Modelo responde sem citar | Afirmação sem suporte | Texto do modelo é substituído pela resposta padrão sem evidência | Status `no_evidence` e fontes vazias |
| Credencial ou pergunta aparece em log | Exposição de dado sensível | Mascaramento por chave e padrões de e-mail/CPF | Teste verifica que valores originais desaparecem |
| Ollama indisponível | Falha ou resposta inventada | Retry, backoff e fallback sem afirmação factual | Status `degraded` e número de tentativas |
| Conteúdo malicioso aparece no front | Execução de script no navegador | Respostas e fontes são inseridas como texto, nunca como HTML | Teste protege o uso de `textContent` |
| Feedback usa requisição de outro tenant | Liga avaliação ao contexto errado | API confere a relação entre `request_id` e tenant | Teste cruzado espera HTTP 404 |
| Token fica salvo no navegador | Reutilização indevida depois da sessão | Token mantido somente em memória | Trocar empresa limpa o estado da aba |

## Riscos aceitos nesta demonstração

- Os usuários e as senhas são totalmente sintéticos e estão documentados para facilitar a avaliação.
- O token é próprio e demonstrativo; produção deve usar um provedor de identidade e padrões consolidados.
- O catálogo de prompt injection cobre ataques conhecidos, não todas as variações possíveis.
- Não existe revogação de token nesta fase.
- Rate limiting, trilha de auditoria e alertas operacionais pertencem às fases de observabilidade e entrega.
- As políticas são sintéticas e não contêm dados reais de clientes da Onfly.
- Feedback fica em memória e é perdido ao reiniciar; produção exigiria persistência auditável.

## Critérios de segurança validados

- Uma credencial da Aurora não produz contexto da Brisa.
- O corpo da pergunta não consegue escolher o tenant.
- Um resultado com tenant divergente é bloqueado antes da geração.
- Prompt injection conhecida não chega ao modelo.
- Instrução maliciosa recuperada de documento não chega ao prompt.
- Senhas, tokens, perguntas, e-mails e CPFs passam pelo mascaramento antes de um eventual log estruturado.
- Feedback de um tenant não pode apontar para a requisição de outro tenant.
