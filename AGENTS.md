# Regras permanentes do projeto

## Fonte de verdade

- Seguir o `PROJECT_PLAN.md` como planejamento oficial do projeto.
- Trabalhar em uma tarefa pequena por vez e respeitar a ordem das fases.
- Implementar um front-end demonstrativo na fase de acabamento, cobrindo credenciais mockadas, contexto do tenant e uso do assistente.

## Audiência, comunicação e organização

- Direcionar todo arquivo, documentação e evidência técnica aos avaliadores e ao time de Engenharia da Onfly.
- Apresentar o sistema como um case técnico independente, sem registrar bastidores de estudo, instruções pessoais ou referências a protótipos anteriores.
- Escrever comunicações, documentações, comentários e docstrings em português simples.
- Usar termos técnicos somente quando ajudarem a explicar a solução e definir seu significado na primeira ocorrência.
- Explicar decisões, alternativas, vantagens, limitações e riscos com frases diretas.
- Evitar jargão sem explicação, siglas não definidas e linguagem desnecessariamente complexa.
- Organizar, nomear, catalogar e classificar o código por responsabilidade.
- Ler o código existente antes de editar.
- Ao finalizar, informar arquivos alterados, comandos executados, resultados e riscos restantes.

## Implementação

- Preservar comportamento funcional já testado.
- Não adicionar dependência sem justificar.
- Nunca inserir segredos no repositório.
- Usar somente dados sintéticos.
- Aplicar filtro de tenant em toda operação de recuperação.
- Criar ou atualizar testes para qualquer mudança de comportamento.
- Rodar lint, type checking e testes antes de concluir.
- Atualizar documentação e ADR quando houver decisão arquitetural.
