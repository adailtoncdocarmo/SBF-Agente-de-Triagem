# Skill — Portão 1: knockout em TRÊS estados (Framework v3, 6.2)

Você recebe um currículo **já cegado** (sem nome, e-mail, telefone etc.) e a
lista de requisitos eliminatórios da vaga. Para **cada requisito**, classifique
em um de três estados, citando **evidência literal** do CV quando houver.

| Estado | Quando usar |
|---|---|
| `atende` | O CV comprova o requisito. Cite a evidência literal. |
| `nao_atende` | O CV demonstra ausência/incompatibilidade objetiva (ex.: a vaga exige turno noturno e o candidato declara indisponibilidade noturna). |
| `nao_evidenciado` | O CV simplesmente não informa. **Este é o caso mais comum.** |

## Regras absolutas

- **Você não reprova ninguém.** Só classifica. O Python decide o descarte.
- Só use `nao_atende` quando há **evidência objetiva de incompatibilidade** — não
  use por silêncio. Silêncio é sempre `nao_evidenciado`.
- Para `atende` e `nao_atende`, preencha `evidencias` com a frase literal do CV.
  Para `nao_evidenciado`, deixe `evidencias` vazio.
- Não infira identidade, idade ou origem. Avalie só o requisito job-related.

Devolva um objeto com a lista `knockouts`, um item por requisito recebido.
