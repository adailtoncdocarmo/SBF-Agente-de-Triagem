"""Testes da higiene de texto exibido ao RH (remoção de travessões)."""

from __future__ import annotations

from app.texto import limpar_dashes


def test_remove_travessao_no_meio_da_frase() -> None:
    assert (
        limpar_dashes("portfólio digital — áreas distintas")
        == "portfólio digital, áreas distintas"
    )


def test_remove_meia_risca_espacada() -> None:
    assert limpar_dashes("Telecom e TI – setores distantes") == "Telecom e TI, setores distantes"


def test_meia_risca_em_intervalo_vira_hifen() -> None:
    assert limpar_dashes("peso 0–100") == "peso 0-100"


def test_vazio_e_none() -> None:
    assert limpar_dashes("") == ""
    assert limpar_dashes(None) == ""


def test_texto_sem_travessao_inalterado() -> None:
    assert limpar_dashes("Vaga X: 5 currículo(s) avaliado(s)") == "Vaga X: 5 currículo(s) avaliado(s)"
