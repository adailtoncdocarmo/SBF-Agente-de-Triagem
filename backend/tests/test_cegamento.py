"""Testes do cegamento (Stage 0): remove PII, preserva evidência, marca proxies."""

from __future__ import annotations

from app.triagem.cegamento import MARCADOR, cegar_cv

CV_EXEMPLO = """Maria Aparecida Souza
E-mail: maria.souza@gmail.com
Telefone: (11) 98765-4321
CPF: 123.456.789-00
Endereço: Rua das Flores, 100 — Bairro Centro — CEP 01310-100

EXPERIÊNCIA PROFISSIONAL
Vendedora na Loja Centauro (2021-2024): atendimento, fechamento de caixa,
metas de vendas batidas em 7 dos 12 meses. Domínio de sistema PDV e Excel.

FORMAÇÃO
Ensino médio completo. Curso técnico em vendas concluído em 2019.
Universidade Federal — graduação em andamento.
"""


def test_remove_identificadores_diretos() -> None:
    resultado = cegar_cv(CV_EXEMPLO, "CAND-0001")
    texto = resultado.texto_cegado
    assert "maria.souza@gmail.com" not in texto
    assert "98765-4321" not in texto
    assert "123.456.789-00" not in texto
    assert "01310-100" not in texto
    assert MARCADOR in texto
    assert {"email", "telefone", "cpf", "cep"}.issubset(set(resultado.removidos))


def test_preserva_evidencia_profissional() -> None:
    resultado = cegar_cv(CV_EXEMPLO, "CAND-0001")
    texto = resultado.texto_cegado
    # O que importa para a triagem permanece.
    assert "Centauro" in texto
    assert "PDV" in texto
    assert "Excel" in texto
    assert "metas de vendas" in texto.lower()


def test_marca_proxies_sem_apagar_tudo() -> None:
    resultado = cegar_cv(CV_EXEMPLO, "CAND-0001")
    assert "instituicao_ensino" in resultado.proxies_marcados
    assert "ano_formatura" in resultado.proxies_marcados
    # Ano de formatura é neutralizado (proxy de idade/socioeconômico).
    assert "2019" not in resultado.texto_cegado
    # O texto não vira vazio.
    assert len(resultado.texto_cegado) > 50


def test_remocao_de_nome_na_primeira_linha() -> None:
    resultado = cegar_cv(CV_EXEMPLO, "CAND-0001")
    assert "Maria Aparecida Souza" not in resultado.texto_cegado
    assert "nome" in resultado.removidos
