"""Estágio 0 — Cegamento (anti-viés / LGPD), Python puro e testável.

Cegamento realista (Framework 7.2): não é apagar tudo. É (1) **remover
identificadores diretos** (nome, e-mail, telefone, CPF, CEP, links, idade/data de
nascimento), (2) **preservar a evidência profissional** (cargos, ferramentas,
resultados), e (3) **marcar proxies sensíveis** (bairro, instituição, ano de
formatura) para que não sejam usados como critério — eles são monitorados, não
pontuados. Roda **antes** de qualquer chamada à IA.

Limitação honesta: a remoção de nome é heurística (primeira linha / rótulo
"Nome:"). Cobre os casos comuns de CV brasileiro, não é infalível.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

MARCADOR = "[REMOVIDO]"

# --- Identificadores diretos (removidos) ---
_RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_RE_URL = re.compile(r"\bhttps?://\S+\b|\b(?:www\.|linkedin\.com/|github\.com/)\S+", re.I)
_RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_RE_CEP = re.compile(r"\b\d{5}-?\d{3}\b")
_RE_TELEFONE = re.compile(
    r"(?:\+55\s?)?\(?\d{2}\)?[\s.-]?\d{4,5}[\s.-]?\d{4}\b"
)
_RE_IDADE = re.compile(r"\bidade[:\s]*\d{1,2}\b", re.I)
_RE_NASCIMENTO = re.compile(
    r"\b(?:data\s+de\s+nascimento|nascido[a]?\s+em|nascimento)[:\s]*[\d/.-]{6,10}\b",
    re.I,
)
_RE_ROTULO_NOME = re.compile(r"^\s*nome[:\s].*$", re.I | re.M)

# Linha que "parece um nome": 2-4 palavras capitalizadas, sem dígitos, curta.
_RE_LINHA_NOME = re.compile(
    r"^\s*([A-ZÀ-Ý][a-zà-ÿ']+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][a-zà-ÿ']+){1,3})\s*$"
)

# --- Proxies sensíveis (marcados, não usados como critério) ---
_RE_BAIRRO = re.compile(r"\b(?:bairro|rua|av\.?|avenida|alameda)\b", re.I)
_RE_FORMATURA = re.compile(
    r"\b(?:formad[oa]\s+em|conclu[ií]d[oa]\s+em|conclus[ãa]o|formatura)[:\s]*\d{4}\b",
    re.I,
)
_RE_INSTITUICAO = re.compile(
    r"\b(?:universidade|faculdade|instituto|col[ée]gio|puc|usp|unicamp|fgv|uf[a-z]{1,3})\b",
    re.I,
)


class ResultadoCegamento(BaseModel):
    """Saída do cegamento: texto limpo + auditoria do que foi tratado.

    `nome_detectado` é guardado **só para rótulo de exibição** ao RH (lista de
    candidatos). A IA continua recebendo apenas `texto_cegado` — o scoring é cego.
    """

    texto_cegado: str
    id_anonimo: str
    nome_detectado: str | None = None
    removidos: list[str] = Field(default_factory=list)
    proxies_marcados: list[str] = Field(default_factory=list)


def cegar_cv(texto_bruto: str, id_anonimo: str) -> ResultadoCegamento:
    """Remove PII direta, preserva evidência profissional e marca proxies.

    Args:
        texto_bruto: texto extraído do CV (PDF/txt).
        id_anonimo: identificador anônimo do candidato (ex.: "CAND-0007").

    Returns:
        `ResultadoCegamento` com o texto cegado e listas de auditoria.
    """
    removidos: list[str] = []
    proxies: list[str] = []
    nome_detectado: str | None = None
    texto = texto_bruto

    # 1) Heurística de nome na primeira linha não vazia.
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if linha.strip():
            m = _RE_LINHA_NOME.match(linha)
            if m:
                nome_detectado = m.group(1).strip()
                linhas[i] = MARCADOR
                removidos.append("nome")
            break
    texto = "\n".join(linhas)

    # 1b) Rótulo "Nome: Fulano" é o sinal mais confiável — sobrepõe a heurística.
    rotulo = _RE_ROTULO_NOME.search(texto)
    if rotulo:
        valor = re.sub(r"^\s*nome[:\s]+", "", rotulo.group(0), flags=re.I).strip()
        if valor and valor != MARCADOR:
            nome_detectado = valor

    # 2) Identificadores diretos via regex.
    def _remover(regex: re.Pattern[str], rotulo: str, alvo: str) -> str:
        nonlocal removidos
        if regex.search(alvo):
            removidos.append(rotulo)
            return regex.sub(MARCADOR, alvo)
        return alvo

    texto = _remover(_RE_ROTULO_NOME, "nome", texto)
    texto = _remover(_RE_EMAIL, "email", texto)
    texto = _remover(_RE_URL, "link", texto)
    texto = _remover(_RE_CPF, "cpf", texto)
    texto = _remover(_RE_CEP, "cep", texto)
    texto = _remover(_RE_NASCIMENTO, "nascimento", texto)
    texto = _remover(_RE_IDADE, "idade", texto)
    # Telefone por último (o padrão é mais genérico — evita comer CPF/CEP já tratados).
    texto = _remover(_RE_TELEFONE, "telefone", texto)

    # 3) Proxies — apenas detectados/marcados (não removidos do histórico).
    if _RE_BAIRRO.search(texto):
        proxies.append("endereco_bairro")
    if _RE_INSTITUICAO.search(texto):
        proxies.append("instituicao_ensino")
    # Ano de formatura é proxy de idade/socioeconômico → neutraliza o ano.
    if _RE_FORMATURA.search(texto):
        proxies.append("ano_formatura")
        texto = _RE_FORMATURA.sub("formação concluída [ANO_REMOVIDO]", texto)

    return ResultadoCegamento(
        texto_cegado=texto.strip(),
        id_anonimo=id_anonimo,
        nome_detectado=nome_detectado,
        removidos=sorted(set(removidos)),
        proxies_marcados=sorted(set(proxies)),
    )
