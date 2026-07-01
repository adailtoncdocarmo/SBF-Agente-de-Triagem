"""Contratos de saída pinados — a blindagem do low-code de Habilidades.

Cada estágio LLM carrega uma "Habilidade" (texto markdown editável pelo RH). Para
que uma edição não consiga quebrar o contrato Pydantic da saída, o **formato**
(campos obrigatórios, enums válidos, contagens, "nota inteira sem decimais") é
fixado AQUI, em constante Python — **não-editável**, fora do `.md` e do override
SQLite. O orquestrador sempre injeta este contrato por código; mesmo que o RH
apague todo o texto editável, as regras de formato permanecem.

O enforcement real do shape/enum/int continua nos schemas Pydantic + structured
output do provedor (Anthropic enforça server-side); este contrato textual é
cinto-e-suspensório — sobretudo para provedores mais frouxos (OpenAI/Gemini).

Ordem de injeção (estável para o prompt caching): `CONTRATO + skill_editável +
[contexto da vaga]`, com o CV volátil indo no `conteudo` da chamada.
"""

from __future__ import annotations

from app.schemas.enums import ROTULOS_CRITERIOS
from app.triagem.skills_loader import carregar_skill

# Os 7 ids de critério válidos (slugs semânticos) + nome, para os contratos.
_IDS_CRITERIOS = ", ".join(ROTULOS_CRITERIOS)
_CRITERIOS_COM_NOME = "; ".join(f"`{slug}` ({nome})" for slug, nome in ROTULOS_CRITERIOS.items())

# Contrato de formato por skill. Cita literalmente os enums de `schemas/enums.py`
# e as contagens que os schemas/Python esperam.
CONTRATOS: dict[str, str] = {
    "skill_regua": (
        "## Contrato de saída (fixo — não editável)\n"
        "Estruture a régua com EXATAMENTE estes campos:\n"
        "- `knockouts`: um item por requisito eliminatório (lista; pode ser vazia). "
        "Para cada um: `requisito` (rótulo curto), `objetivo` (true só se verificável "
        "objetivamente: CNH, registro, idioma, turno, localidade, formação legal), "
        "`tipico_no_cv` (true se o requisito normalmente aparece num currículo — "
        "certificação, formação, idioma; false se raramente é escrito no CV — CNH, "
        "disponibilidade, localidade) e `justificativa_job_related` (uma linha).\n"
        f"- `criterios_criticos`: de 1 a 3 destes ids: {_IDS_CRITERIOS}.\n"
        f"- `pesos_sugeridos`: mapa com os 7 ids ({_IDS_CRITERIOS}) → peso inteiro.\n"
        "- `competencias_detectadas`: lista de competências citadas na vaga.\n"
        f"Os 7 critérios canônicos são: {_CRITERIOS_COM_NOME}.\n"
        "Use exatamente esses ids. Não dá notas — só estrutura a vaga."
    ),
    "skill_portao1": (
        "## Contrato de saída (fixo — não editável)\n"
        "Devolva `knockouts`: um item por requisito eliminatório recebido. Para cada um:\n"
        "- `requisito`: o texto do requisito.\n"
        "- `estado`: um de `atende`, `nao_atende`, `nao_evidenciado` (silêncio do CV = `nao_evidenciado`).\n"
        "- `evidencias`: citações literais do CV (lista vazia quando `nao_evidenciado`).\n"
        "Você não reprova ninguém — só classifica."
    ),
    "skill_scoring": (
        "## Contrato de saída (fixo — não editável)\n"
        "Devolva `notas` com EXATAMENTE um item por critério (7 notas no total). Para cada um:\n"
        f"- `criterio`: um destes ids: {_IDS_CRITERIOS}.\n"
        "- `nota_0_4`: inteiro de 0 a 4 — SEM decimais (não use 2,5 nem 3,5).\n"
        "- `justificativa_nota`: 1 frase explicando por que a nota é essa.\n"
        "- `evidencias` e `lacunas`: listas de frases.\n"
        "- `ultimo_uso_ano`: ano (inteiro) do último uso, ou nulo.\n"
        "- `confianca_criterio`: um de `alta`, `media`, `baixa`.\n"
        f"Os 7 critérios são: {_CRITERIOS_COM_NOME}.\n"
        "Você não calcula score — só atribui a nota ancorada na evidência."
    ),
    "skill_flags": (
        "## Contrato de saída (fixo — não editável)\n"
        "Devolva:\n"
        "- `risco`: lista (pode ser vazia). Cada item: `descricao`, `severidade` "
        "(um de `baixa`, `media`, `alta`, `critica`), `acao`.\n"
        "- `clareza`: `nivel` e `confianca_avaliacao`, cada um um de `alta`, `media`, `baixa`.\n"
        "Flags não entram na nota — só modulam a confiança."
    ),
    "skill_comparacao": (
        "## Contrato de saída (fixo — não editável)\n"
        "Devolva `vencedor`: um de `A`, `B`, `empate`, e uma `justificativa` curta e rastreável.\n"
        "Você só ordena o empate — nunca altera a nota de ninguém."
    ),
    "skill_sintese": (
        "## Contrato de saída (fixo — não editável)\n"
        "Devolva DOIS textos curtos (cada um no MÁXIMO ~3 linhas; pode ser menos):\n"
        "- `aderencia`: por que o candidato adere (ou não) ao perfil da vaga, "
        "citando pontos concretos da avaliação.\n"
        "- `recomendacao`: orientação objetiva ao RH sobre como endereçar o perfil "
        "(próximos passos, o que confirmar na entrevista).\n"
        "Não invente fatos: use só os sinais recebidos. Não recalcule a nota."
    ),
}


def contrato(nome: str) -> str:
    """Texto de contrato pinado da skill (vazio se a skill não tiver contrato)."""
    return CONTRATOS.get(nome, "")


def montar_com_contrato(nome: str, skill_text: str, *extras: str) -> str:
    """Prefixa o contrato pinado ao texto da skill + extras (ordem estável p/ cache).

    Usado pelo dry-run com o texto AINDA NÃO salvo; o pipeline real usa `sistema`.
    """
    partes = [contrato(nome), skill_text, *extras]
    return "\n\n".join(p for p in partes if p)


def sistema(nome: str, *extras: str) -> str:
    """Bloco de sistema do estágio: contrato pinado + skill (do `.md`) + extras."""
    return montar_com_contrato(nome, carregar_skill(nome), *extras)
