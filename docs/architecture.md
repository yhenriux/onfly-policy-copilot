# Arquitetura do Onfly Policy Copilot

## Visão geral

O projeto usa uma arquitetura modular. Isso significa que autenticação, recuperação, geração, segurança, feedback e interface possuem responsabilidades separadas.

```mermaid
flowchart LR
    Browser["Front-end demonstrativo"] --> API["FastAPI"]
    API --> Auth["Autenticação mockada"]
    API --> Guard["Controles de segurança"]
    Guard --> Retrieval["Busca híbrida e re-ranking"]
    Retrieval --> Qdrant["Qdrant"]
    Retrieval --> Ollama["Ollama: all-minilm"]
    API --> Ollama2["Ollama: llama3.2:1b"]
    API --> Feedback["Feedback em memória"]
    API --> Obs["Logs, trace e métricas"]
```

## Fluxo de uma consulta

1. O avaliador escolhe Aurora ou Brisa na interface.
2. A API valida a credencial sintética e devolve um token assinado.
3. O front envia somente a pergunta e o token.
4. A API obtém o tenant do token e bloqueia prompt injection conhecida.
5. O Ollama transforma a pergunta em embedding, que é um vetor numérico de significado.
6. Qdrant e BM25 recuperam candidatos somente do tenant autenticado.
7. O CrossEncoder reordena os candidatos em uma thread de trabalho para não bloquear a API.
8. O `llama3.2:1b` recebe somente o contexto autorizado e produz JSON validado.
9. A resposta inclui fontes, confiança, `request_id` e tempos por componente.
10. O feedback só é aceito se o `request_id` pertencer ao mesmo tenant.

## Fronteiras importantes

- O navegador nunca informa `tenant_id`.
- O token fica somente na memória da aba.
- Texto vindo da API é exibido como texto, não como HTML executável.
- Feedback não guarda pergunta, resposta, token ou credencial.
- Dados e credenciais são inteiramente sintéticos.

## Execução

No modo local, Qdrant usa uma pasta persistente e Ollama roda no computador. No Compose, Qdrant vira um serviço HTTP persistente e a API acessa o Ollama do computador por `host.docker.internal`.
