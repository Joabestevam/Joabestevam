"""Modelos de dados usados pela engine de precos e pelo buscador de campeoes."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductConfig:
    """Configuracao de um produto monitorado, vinda de config/products.json."""

    sku: str
    title: str
    item_id: str | None = None  # ID do anuncio no Mercado Livre (ex: MLB123456789), se ja publicado
    search_query: str = ""  # termo usado para encontrar concorrentes
    cost_price: float = 0.0  # custo do produto (compra/fabricacao)
    extra_cost: float = 0.0  # custos adicionais fixos (embalagem, etc.)
    min_margin_pct: float = 10.0  # margem minima aceitavel sobre o preco de venda
    target_margin_pct: float = 25.0  # margem desejada
    ml_fee_pct: float = 13.0  # comissao do Mercado Livre para a categoria (%)
    fixed_fee: float = 0.0  # taxa fixa do ML para itens de baixo valor
    shipping_cost: float = 0.0  # custo de frete absorvido pelo vendedor
    strategy: str = "match_median"  # beat_lowest | match_median | premium
    competitiveness_step: float = 0.01  # margem percentual abaixo do concorrente em beat_lowest


@dataclass
class CompetitorSnapshot:
    item_id: str
    title: str
    price: float
    sold_quantity: int = 0
    free_shipping: bool = False
    seller_id: int | None = None


@dataclass
class PriceSuggestion:
    sku: str
    title: str
    cost_price: float
    current_price: float | None
    min_viable_price: float
    target_price: float
    suggested_price: float
    suggested_margin_pct: float
    competitor_min: float | None
    competitor_median: float | None
    competitor_max: float | None
    competitor_count: int
    strategy: str
    action: str  # "manter" | "reduzir" | "aumentar" | "alerta_margem"
    notes: list[str] = field(default_factory=list)


@dataclass
class ChampionCandidate:
    item_id: str
    title: str
    query: str
    price: float
    sold_quantity: int
    competitor_count: int
    free_shipping: bool
    score: float
