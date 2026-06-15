"""Funcoes compartilhadas entre o CLI e o dashboard web.

Encapsula a obtencao de configuracao, cliente da API, preco atual,
concorrentes e o relatorio de precos completo.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from .ml_client import MLApiError, MLClient, MLCredentials
from .models import CompetitorSnapshot, PriceSuggestion, ProductConfig
from .pricing_engine import suggest_price

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "products.json"


def load_products(config_path: Path) -> list[ProductConfig]:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return [ProductConfig(**item) for item in raw]


def client_from_env(site_id: str = "MLB") -> MLClient:
    load_dotenv()
    return MLClient(site_id=site_id, credentials=MLCredentials.from_env())


def current_price(client: MLClient, config: ProductConfig) -> float | None:
    if not config.item_id:
        return None
    try:
        item = client.get_item(config.item_id)
        return item.get("price")
    except MLApiError as exc:
        logger.warning("Nao foi possivel obter preco atual de %s: %s", config.item_id, exc)
        return None


def competitors_for(client: MLClient, config: ProductConfig) -> list[CompetitorSnapshot]:
    if not config.search_query:
        return []
    try:
        page = client.search(config.search_query, limit=50)
    except MLApiError as exc:
        logger.warning("Falha ao buscar concorrentes para %r: %s", config.search_query, exc)
        return []

    snapshots = []
    for result in page.get("results", []):
        if config.item_id and result.get("id") == config.item_id:
            continue  # nao comparar o produto com ele mesmo
        snapshots.append(
            CompetitorSnapshot(
                item_id=result.get("id", ""),
                title=result.get("title", ""),
                price=result.get("price", 0.0),
                sold_quantity=result.get("sold_quantity", 0) or 0,
                free_shipping=bool(result.get("shipping", {}).get("free_shipping")),
                seller_id=(result.get("seller") or {}).get("id"),
            )
        )
    return snapshots


def build_price_report(client: MLClient, products: list[ProductConfig]) -> list[PriceSuggestion]:
    suggestions = []
    for product in products:
        current = current_price(client, product)
        competitors = competitors_for(client, product)
        suggestions.append(suggest_price(product, competitors, current_price=current))
    return suggestions
