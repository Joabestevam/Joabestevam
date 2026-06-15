"""Engine de gestao de precos.

Calcula, para cada produto monitorado:
  - preco minimo viavel (margem minima aceitavel)
  - preco alvo (margem desejada)
  - preco sugerido, considerando a estrategia escolhida e os precos
    praticados pela concorrencia no Mercado Livre.
"""
from __future__ import annotations

import statistics
from typing import Iterable

from .models import ChampionCandidate, CompetitorSnapshot, PriceSuggestion, ProductConfig

# Diferenca percentual tolerada entre preco atual e sugerido antes de
# recomendar uma alteracao (evita "flapping" por centavos).
PRICE_CHANGE_TOLERANCE_PCT = 1.0


def total_cost(config: ProductConfig) -> float:
    return config.cost_price + config.extra_cost + config.shipping_cost


def margin_pct_for_price(config: ProductConfig, price: float) -> float:
    """Margem liquida (%) obtida ao vender pelo preco informado."""
    if price <= 0:
        return float("-inf")
    ml_fee = price * (config.ml_fee_pct / 100.0) + config.fixed_fee
    profit = price - total_cost(config) - ml_fee
    return (profit / price) * 100.0


def price_for_margin(config: ProductConfig, margin_pct: float) -> float:
    """Preco necessario para atingir a margem (%) desejada."""
    denom = 1.0 - (config.ml_fee_pct + margin_pct) / 100.0
    if denom <= 0:
        raise ValueError(
            f"Margem de {margin_pct}% inviavel: comissao do ML ({config.ml_fee_pct}%) "
            "ja consome o preco de venda."
        )
    return (total_cost(config) + config.fixed_fee) / denom


def min_viable_price(config: ProductConfig) -> float:
    return price_for_margin(config, config.min_margin_pct)


def target_price(config: ProductConfig) -> float:
    return price_for_margin(config, config.target_margin_pct)


def _competitor_prices(competitors: Iterable[CompetitorSnapshot]) -> list[float]:
    return sorted(c.price for c in competitors if c.price and c.price > 0)


def suggest_price(
    config: ProductConfig,
    competitors: list[CompetitorSnapshot],
    current_price: float | None = None,
) -> PriceSuggestion:
    """Gera a sugestao de preco para um produto, dado o cenario competitivo."""
    notes: list[str] = []
    min_price = min_viable_price(config)
    target = target_price(config)

    prices = _competitor_prices(competitors)
    comp_min = prices[0] if prices else None
    comp_max = prices[-1] if prices else None
    comp_median = statistics.median(prices) if prices else None

    strategy = config.strategy
    if not prices:
        notes.append("Nenhum concorrente encontrado; usando preco-alvo baseado em margem.")
        raw_suggestion = target
    elif strategy == "beat_lowest":
        raw_suggestion = comp_min * (1 - config.competitiveness_step)
    elif strategy == "premium":
        raw_suggestion = max(target, comp_max * 0.98)
    else:  # match_median (default)
        raw_suggestion = comp_median

    suggested = raw_suggestion
    if suggested < min_price:
        notes.append(
            f"Preco competitivo (R$ {suggested:.2f}) ficaria abaixo da margem minima "
            f"({config.min_margin_pct:.1f}%); ajustado para o piso de R$ {min_price:.2f}."
        )
        suggested = min_price

    suggested_margin = margin_pct_for_price(config, suggested)

    action = "manter"
    if current_price is not None and current_price > 0:
        diff_pct = (suggested - current_price) / current_price * 100.0
        if abs(diff_pct) <= PRICE_CHANGE_TOLERANCE_PCT:
            action = "manter"
        elif diff_pct < 0:
            action = "reduzir"
        else:
            action = "aumentar"

        current_margin = margin_pct_for_price(config, current_price)
        if current_margin < config.min_margin_pct:
            action = "alerta_margem"
            notes.append(
                f"Preco atual (R$ {current_price:.2f}) esta com margem de "
                f"{current_margin:.1f}%, abaixo do minimo de {config.min_margin_pct:.1f}%."
            )

    return PriceSuggestion(
        sku=config.sku,
        title=config.title,
        cost_price=total_cost(config),
        current_price=current_price,
        min_viable_price=round(min_price, 2),
        target_price=round(target, 2),
        suggested_price=round(suggested, 2),
        suggested_margin_pct=round(suggested_margin, 2),
        competitor_min=comp_min,
        competitor_median=comp_median,
        competitor_max=comp_max,
        competitor_count=len(prices),
        strategy=strategy,
        action=action,
        notes=notes,
    )


def champion_score(sold_quantity: int, competitor_count: int, free_shipping: bool) -> float:
    """Pontuacao heuristica: alta demanda com baixa concorrencia pontua mais.

    score = vendas / (1 + concorrentes), com bonus de 10% para frete gratis
    (itens com frete gratis tendem a converter melhor no Mercado Livre).
    """
    score = sold_quantity / (1 + competitor_count)
    if free_shipping:
        score *= 1.1
    return round(score, 3)


def rank_champions(candidates: list[ChampionCandidate], top_n: int = 20) -> list[ChampionCandidate]:
    return sorted(candidates, key=lambda c: c.score, reverse=True)[:top_n]
