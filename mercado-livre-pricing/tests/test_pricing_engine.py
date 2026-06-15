from src.models import CompetitorSnapshot, ProductConfig
from src.pricing_engine import (
    champion_score,
    margin_pct_for_price,
    min_viable_price,
    price_for_margin,
    suggest_price,
    target_price,
)


def make_config(**overrides) -> ProductConfig:
    base = dict(
        sku="TEST-1",
        title="Produto Teste",
        item_id="MLB000",
        search_query="produto teste",
        cost_price=50.0,
        extra_cost=0.0,
        min_margin_pct=10.0,
        target_margin_pct=25.0,
        ml_fee_pct=12.0,
        fixed_fee=0.0,
        shipping_cost=0.0,
        strategy="match_median",
        competitiveness_step=0.02,
    )
    base.update(overrides)
    return ProductConfig(**base)


def test_price_for_margin_recovers_margin():
    config = make_config()
    price = price_for_margin(config, 25.0)
    assert margin_pct_for_price(config, price) - 25.0 < 1e-6


def test_min_and_target_price_ordering():
    config = make_config()
    assert min_viable_price(config) < target_price(config)


def test_match_median_strategy_uses_median_when_above_floor():
    config = make_config(strategy="match_median")
    competitors = [
        CompetitorSnapshot(item_id="A", title="A", price=80.0),
        CompetitorSnapshot(item_id="B", title="B", price=90.0),
        CompetitorSnapshot(item_id="C", title="C", price=100.0),
    ]
    suggestion = suggest_price(config, competitors, current_price=85.0)
    assert suggestion.suggested_price == 90.0
    assert suggestion.competitor_count == 3


def test_beat_lowest_strategy_undercuts_cheapest_competitor():
    config = make_config(strategy="beat_lowest", competitiveness_step=0.05)
    competitors = [
        CompetitorSnapshot(item_id="A", title="A", price=100.0),
        CompetitorSnapshot(item_id="B", title="B", price=120.0),
    ]
    suggestion = suggest_price(config, competitors, current_price=110.0)
    assert suggestion.suggested_price == 95.0


def test_suggestion_floors_at_min_viable_price_when_market_is_too_cheap():
    config = make_config(cost_price=90.0, min_margin_pct=10.0)
    competitors = [CompetitorSnapshot(item_id="A", title="A", price=50.0)]
    suggestion = suggest_price(config, competitors, current_price=95.0)
    assert suggestion.suggested_price == round(min_viable_price(config), 2)
    assert any("margem minima" in note for note in suggestion.notes)


def test_no_competitors_falls_back_to_target_price():
    config = make_config()
    suggestion = suggest_price(config, competitors=[], current_price=70.0)
    assert suggestion.suggested_price == round(target_price(config), 2)
    assert suggestion.competitor_count == 0


def test_action_alerta_margem_when_current_price_below_minimum_margin():
    config = make_config(cost_price=90.0, min_margin_pct=10.0)
    competitors = [CompetitorSnapshot(item_id="A", title="A", price=200.0)]
    suggestion = suggest_price(config, competitors, current_price=92.0)
    assert suggestion.action == "alerta_margem"


def test_action_manter_within_tolerance():
    config = make_config()
    competitors = [CompetitorSnapshot(item_id="A", title="A", price=100.0)]
    target = target_price(config)
    suggestion = suggest_price(config, competitors=[], current_price=target)
    assert suggestion.action == "manter"


def test_champion_score_rewards_demand_over_competition():
    high_demand_low_competition = champion_score(sold_quantity=500, competitor_count=10, free_shipping=False)
    low_demand_high_competition = champion_score(sold_quantity=500, competitor_count=1000, free_shipping=False)
    assert high_demand_low_competition > low_demand_high_competition


def test_champion_score_free_shipping_bonus():
    without_shipping = champion_score(100, 10, free_shipping=False)
    with_shipping = champion_score(100, 10, free_shipping=True)
    assert with_shipping > without_shipping
