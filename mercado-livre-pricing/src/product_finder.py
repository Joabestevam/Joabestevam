"""Buscador de "produtos campeoes": alta demanda x baixa concorrencia.

Usa os termos em alta (trends) do Mercado Livre e/ou uma lista de
palavras-chave fornecida pelo usuario, busca os anuncios mais relevantes
para cada termo e pontua cada item combinando volume de vendas
(sold_quantity) com o numero de concorrentes para aquele termo.
"""
from __future__ import annotations

import logging
from typing import Iterable

from .ml_client import MLApiError, MLClient
from .models import ChampionCandidate
from .pricing_engine import champion_score, rank_champions

logger = logging.getLogger(__name__)

# Quantos resultados de busca consideramos "o tamanho da concorrencia" para um termo.
COMPETITOR_SAMPLE_SIZE = 50

# Quantos dos resultados mais relevantes de cada termo sao avaliados em detalhe
# (chamando /items/{id} para obter sold_quantity).
TOP_RESULTS_PER_QUERY = 5


def find_champions(
    client: MLClient,
    queries: Iterable[str] | None = None,
    category_id: str | None = None,
    top_n: int = 20,
) -> list[ChampionCandidate]:
    """Retorna os produtos com melhor relacao demanda/concorrencia.

    Se `queries` nao for informado, usa os termos em alta (trends) do
    Mercado Livre para o `category_id` (ou geral, se None).
    """
    terms = list(queries) if queries else _trending_terms(client, category_id)
    if not terms:
        logger.warning("Nenhum termo de busca disponivel para encontrar campeoes.")
        return []

    candidates: list[ChampionCandidate] = []
    for term in terms:
        try:
            candidates.extend(_evaluate_query(client, term))
        except MLApiError as exc:
            logger.warning("Falha ao avaliar termo %r: %s", term, exc)

    return rank_champions(candidates, top_n=top_n)


def _trending_terms(client: MLClient, category_id: str | None, limit: int = 10) -> list[str]:
    try:
        trends = client.get_trends(category_id)
    except MLApiError as exc:
        logger.warning("Nao foi possivel obter tendencias: %s", exc)
        return []
    return [t["keyword"] for t in trends[:limit] if t.get("keyword")]


def _evaluate_query(client: MLClient, query: str) -> list[ChampionCandidate]:
    page = client.search(query, limit=COMPETITOR_SAMPLE_SIZE)
    results = page.get("results", [])
    competitor_count = page.get("paging", {}).get("total", len(results))

    top_results = results[:TOP_RESULTS_PER_QUERY]
    if not top_results:
        return []

    item_ids = [r["id"] for r in top_results]
    details = {item["id"]: item for item in client.get_items(item_ids)}

    candidates: list[ChampionCandidate] = []
    for result in top_results:
        item_id = result["id"]
        detail = details.get(item_id, {})
        sold_quantity = detail.get("sold_quantity", result.get("sold_quantity", 0)) or 0
        free_shipping = bool(result.get("shipping", {}).get("free_shipping"))
        price = result.get("price", 0.0)

        candidates.append(
            ChampionCandidate(
                item_id=item_id,
                title=result.get("title", ""),
                query=query,
                price=price,
                sold_quantity=sold_quantity,
                competitor_count=competitor_count,
                free_shipping=free_shipping,
                score=champion_score(sold_quantity, competitor_count, free_shipping),
            )
        )
    return candidates
