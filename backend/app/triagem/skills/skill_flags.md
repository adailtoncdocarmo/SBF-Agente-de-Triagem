# Skill — Flags de risco e clareza (Framework v3, Parte 4)

Você recebe um currículo **já cegado**. Sinalize riscos e a clareza do texto.
**Flags NÃO entram no score** — elas modulam a **confiança** e o roteamento para
revisão humana, nunca a nota do candidato.

## Flags de risco (severidade)

| Sinal | Severidade |
|---|---|
| Informação ausente, mas não crítica | `baixa` |
| Datas sobrepostas / cronologia inconsistente | `media` |
| Currículo aparentemente copiado da descrição da vaga | `media` |
| Contradição forte / credencial improvável | `alta` |
| Fraude aparente (credencial inexistente, falsificação) | `critica` |

Para cada risco, dê `descricao`, `severidade` e uma `acao` curta (ex.: "validar
na entrevista"). Não invente riscos — só sinalize o que o texto sustenta.

## Clareza → confiança da avaliação

A clareza do texto **não mede a qualidade do candidato** — mede o quanto dá para
avaliar com segurança.

| Currículo | nivel / confianca_avaliacao |
|---|---|
| Claro, com responsabilidades e resultados | `alta` |
| Genérico mas compreensível | `media` |
| Confuso / incompleto / contraditório | `baixa` |

Currículo ruim → **confiança baixa**, não nota baixa. Confiança baixa joga o
caso para a revisão humana.

Devolva `risco` (lista, pode ser vazia) e `clareza` (`nivel` + `confianca_avaliacao`).
