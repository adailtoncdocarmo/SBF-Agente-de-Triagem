# Skill — Pontuar os 7 critérios (Framework v3, Parte 3)

Você recebe um currículo **já cegado** e a régua da vaga. Dê uma nota **inteira
de 0 a 4** a cada um dos 7 critérios, **ancorada na força da evidência** (tabelas
abaixo). Cite evidências literais e lacunas. Você **não calcula score** nem
ranking — só atribui a nota ancorada e os sinais. O Python faz toda a conta.

## Escala (INTEIRA — sem decimais)

| Nota | Significado |
|---:|---|
| 0 | Ausente — sem evidência |
| 1 | Fraco — evidência vaga, superficial ou distante |
| 2 | Parcial — atende parte do critério |
| 3 | Forte — atende bem |
| 4 | Excelente — evidência muito forte ou superior ao esperado |

Não use 2,5 ou 3,5. Para exigir mais de um sênior, o Python sobe o piso inteiro
— não a granularidade.

## Âncoras por critério

**`tecnicas` — Competências técnicas.** Proporção dos must-have presentes,
ponderada por profundidade (uso real > lista) e contexto.
- "Conhecimento em sistema PDV" (palavra solta) → 1
- "Operava o sistema PDV no dia a dia" → 2-3
- "Operava PDV, fechava caixa e treinava novatos no sistema" → 4
- Lista de palavras-chave sem uso ("keyword stuffing") → 1

**`experiencia` — Experiência relevante.** Não conta anos brutos — conta
proximidade, profundidade e complexidade. 4 anos em contexto idêntico valem mais
que 12 em contexto distante.
- Experiência só tangencial / muito antiga / contexto não comparável → 1
- Funções parecidas em setor diferente → 2
- Últimas funções espelham as responsabilidades da vaga → 3-4

**`resultados` — Resultados e impacto.** Conquistas mensuráveis, proporcionais ao
escopo.
- "Responsável por atendimento" → 1
- "Batia metas de vendas" → 2
- "Bateu meta em 7 de 12 meses; reduziu fila do caixa" → 3-4
- **Cuidado:** não reprove quem não escreve números. Reduza `resultados`, mas não
  zere se `tecnicas` e `experiencia` são fortes. Em funções operacionais,
  ausência de números pesa menos.

**`complexidade` — Senioridade e complexidade.** Autonomia, escopo,
responsabilidade.
- "Participava da rotina" → 1-2
- "Coordenava a equipe do turno / respondia pela loja" → 3-4

**`setor` — Aderência ao setor/contexto.** Mesmo cargo e setor → 4; mesmo cargo,
setor parecido → 3; cargo parecido, setor diferente → 2; tudo diferente → 1.

**`formacao` — Formação e certificações.** Avalie pela **relação com a vaga**,
nunca pelo prestígio da instituição (ignore o nome da escola). Certificação sem
prática pontua pouco; com prática demonstrada, pontua mais.

**`progressao` — Progressão e coerência.** Evolução de escopo/responsabilidade →
3-4. Gaps e trocas **não rebaixam automaticamente** — em varejo, tenure curto é
esperado. Lacuna vira flag, não nota baixa por si só.

## Recência (sinalize, não calcule)

Para cada nota, informe `ultimo_uso_ano` (ano aproximado do último uso da
competência principal do critério), quando o CV permitir. O Python aplica o
desconto de recência — você só sinaliza o ano. O ano importa sobretudo em
**`tecnicas`** e **`experiencia`** — onde a defasagem pesa; nos demais critérios
ele pode ser nulo (não force um ano onde o CV não deixa claro).

## Saída

Devolva `notas` com **exatamente um item por critério (7 no total)**, cada um
com: `criterio` (o id do critério), `nota_0_4` (inteiro), `justificativa_nota`,
`evidencias` (frases literais), `lacunas`, `ultimo_uso_ano` (ou nulo) e
`confianca_criterio` (`alta`/`media`/`baixa`).
Confiança baixa quando o CV é confuso/incompleto para aquele critério.

**`justificativa_nota`**: UMA frase explicando **por que** a nota é essa — o que
sustentou e o que faltou para subir. Concreta e específica, não genérica. Ex.:
"Operava PDV no dia a dia (força clara), mas sem indício de gestão de equipe."
