"""Configurações da aplicação, carregadas do `.env` via pydantic-settings.

Centraliza tudo que é configurável. Na Fase 1 nada além da chave de API
precisa ser ajustado — todos os campos têm defaults sãos.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do repositório (… /SBF), calculada a partir deste arquivo:
# config.py → app → backend → SBF
RAIZ_REPO: Path = Path(__file__).resolve().parents[2]


class Configuracoes(BaseSettings):
    """Configurações lidas do ambiente / arquivo `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(RAIZ_REPO / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- IA ---
    # Opcional para subir o esqueleto; obrigatória para triar de verdade.
    anthropic_api_key: str = ""

    # Modelos POR ESTÁGIO (trade-off custo×qualidade é decisão de negócio):
    # Haiku nos estágios simples; Sonnet onde a decisão mora; Opus opcional.
    modelo_regua: str = "claude-sonnet-4-6"
    modelo_portao1: str = "claude-haiku-4-5"
    modelo_scoring: str = "claude-sonnet-4-6"
    modelo_flags: str = "claude-haiku-4-5"
    modelo_comparacao: str = "claude-sonnet-4-6"

    # Custos por milhão de tokens (USD), por família de modelo (input, output).
    custo_haiku_in: float = 1.0
    custo_haiku_out: float = 5.0
    custo_sonnet_in: float = 3.0
    custo_sonnet_out: float = 15.0
    custo_opus_in: float = 5.0
    custo_opus_out: float = 25.0

    # Câmbio USD→BRL para exibir o custo em Real ao lado do dólar nas Métricas.
    # Configurável no `.env` (TAXA_USD_BRL) — o custo de API é sempre cobrado em USD;
    # aqui é só uma conversão de exibição para o RH/diretoria evidenciar em R$.
    taxa_usd_brl: float = 5.40

    # --- Cortes default da régua (nota absoluta 0-100; preset "Equilibrado") ---
    corte_verde_default: int = 60  # nota mínima para "Promissor" (verde)
    corte_amarelo_default: int = 35  # nota mínima para "Revisar" (amarelo)
    alvo_auto_decisao_default: float = 0.65
    # Legados (réguas antigas) — não decidem mais a zona.
    percentil_shortlist_default: int = 80
    piso_absoluto_default: int = 55

    # --- Fila / processamento ---
    concorrencia_cvs: int = 4  # CVs processados em paralelo por lote

    # --- Limites de upload (proteção contra DoS) ---
    max_arquivos_por_lote: int = 200  # teto de CVs por lote
    max_tamanho_arquivo_mb: int = 10  # teto por arquivo

    # --- Resiliência / fallback multi-provedor ---
    # Teto de tempo por chamada de IA: garante que a fila não trave esperando a API.
    timeout_llm_segundos: float = 60.0
    fallback_habilitado: bool = False  # default; configurável em runtime pela UI
    # Custos best-effort por MTok do provedor de fallback (configuráveis em runtime).
    custo_fallback_in: float = 5.0
    custo_fallback_out: float = 15.0

    # --- Banco de dados ---
    # Caminho do arquivo SQLite (criado em runtime no primeiro start).
    db_path: Path = RAIZ_REPO / "backend" / "data" / "app.db"

    # --- Frontend ---
    # Diretório com o build do React (servido como SPA na raiz "/").
    frontend_dist: Path = RAIZ_REPO / "frontend" / "dist"

    @property
    def database_url(self) -> str:
        """URL de conexão SQLAlchemy para o SQLite."""
        return f"sqlite:///{self.db_path}"

    def custo_usd(
        self,
        modelo: str,
        tokens_in: int,
        tokens_out: int,
        tokens_cache_read: int = 0,
    ) -> float:
        """Estima o custo (USD) de uma chamada, com leitura de cache a ~0,1×.

        Os tokens de cache custam ~10% do preço de input — é por isso que
        cachear as skills estáveis reduz tanto o custo do lote.
        """
        nome = modelo.lower()
        if "haiku" in nome:
            preco_in, preco_out = self.custo_haiku_in, self.custo_haiku_out
        elif "opus" in nome:
            preco_in, preco_out = self.custo_opus_in, self.custo_opus_out
        else:  # sonnet (default)
            preco_in, preco_out = self.custo_sonnet_in, self.custo_sonnet_out
        custo = (
            tokens_in / 1_000_000 * preco_in
            + tokens_cache_read / 1_000_000 * preco_in * 0.1
            + tokens_out / 1_000_000 * preco_out
        )
        return round(custo, 6)


@lru_cache
def get_configuracoes() -> Configuracoes:
    """Retorna a instância única (cacheada) das configurações."""
    return Configuracoes()


configuracoes: Configuracoes = get_configuracoes()
