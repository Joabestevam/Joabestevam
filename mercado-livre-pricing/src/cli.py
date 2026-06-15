"""CLI do sistema de gestao de precos e descoberta de produtos campeoes.

Exemplos:
    python -m src.cli price-report --config config/products.json
    python -m src.cli find-champions --queries "tenis,fone bluetooth" --top 10
    python -m src.cli apply-prices --config config/products.json --confirm
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .ml_client import MLApiError, MLClient, MLCredentials
from .models import CompetitorSnapshot, PriceSuggestion, ProductConfig
from .pricing_engine import suggest_price
from .product_finder import find_champions

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_products(config_path: Path) -> list[ProductConfig]:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return [ProductConfig(**item) for item in raw]


def _client_from_env(site_id: str = "MLB") -> MLClient:
    load_dotenv()
    return MLClient(site_id=site_id, credentials=MLCredentials.from_env())


def _current_price(client: MLClient, config: ProductConfig) -> float | None:
    if not config.item_id:
        return None
    try:
        item = client.get_item(config.item_id)
        return item.get("price")
    except MLApiError as exc:
        logger.warning("Nao foi possivel obter preco atual de %s: %s", config.item_id, exc)
        return None


def _competitors_for(client: MLClient, config: ProductConfig) -> list[CompetitorSnapshot]:
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


def cmd_price_report(args: argparse.Namespace) -> int:
    client = _client_from_env(args.site)
    products = _load_products(Path(args.config))

    suggestions: list[PriceSuggestion] = []
    for product in products:
        current = _current_price(client, product)
        competitors = _competitors_for(client, product)
        suggestion = suggest_price(product, competitors, current_price=current)
        suggestions.append(suggestion)
        _print_suggestion(suggestion)

    if args.output:
        _write_csv(Path(args.output), suggestions)
        print(f"\nRelatorio salvo em {args.output}")

    return 0


def _print_suggestion(s: PriceSuggestion) -> None:
    print(f"\n=== {s.sku} - {s.title} ===")
    print(f"Custo total:        R$ {s.cost_price:.2f}")
    print(f"Preco atual:        {'R$ ' + format(s.current_price, '.2f') if s.current_price else 'desconhecido'}")
    print(f"Preco minimo viavel: R$ {s.min_viable_price:.2f}")
    print(f"Preco alvo:         R$ {s.target_price:.2f}")
    print(f"Preco sugerido:     R$ {s.suggested_price:.2f} (margem {s.suggested_margin_pct:.1f}%)")
    if s.competitor_count:
        print(
            f"Concorrentes ({s.competitor_count}): "
            f"min R$ {s.competitor_min:.2f} | mediana R$ {s.competitor_median:.2f} | "
            f"max R$ {s.competitor_max:.2f}"
        )
    else:
        print("Concorrentes: nenhum encontrado")
    print(f"Acao recomendada:   {s.action.upper()}")
    for note in s.notes:
        print(f"  - {note}")


def _write_csv(path: Path, suggestions: list[PriceSuggestion]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [f.name for f in dataclasses.fields(PriceSuggestion) if f.name != "notes"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + ["notes"])
        writer.writeheader()
        for s in suggestions:
            row = {k: getattr(s, k) for k in fieldnames}
            row["notes"] = " | ".join(s.notes)
            writer.writerow(row)


def cmd_apply_prices(args: argparse.Namespace) -> int:
    client = _client_from_env(args.site)
    products = _load_products(Path(args.config))

    for product in products:
        if not product.item_id:
            continue
        current = _current_price(client, product)
        competitors = _competitors_for(client, product)
        suggestion = suggest_price(product, competitors, current_price=current)

        if suggestion.action not in ("reduzir", "aumentar"):
            continue

        print(
            f"{product.sku}: {suggestion.action} de R$ {current:.2f} para "
            f"R$ {suggestion.suggested_price:.2f}"
        )
        if not args.confirm:
            print("  (modo simulacao - use --confirm para aplicar de fato)")
            continue
        try:
            client.update_item_price(product.item_id, suggestion.suggested_price)
            print("  -> preco atualizado no Mercado Livre.")
        except MLApiError as exc:
            print(f"  -> ERRO ao atualizar preco: {exc}")

    return 0


def cmd_find_champions(args: argparse.Namespace) -> int:
    client = _client_from_env(args.site)
    queries = [q.strip() for q in args.queries.split(",") if q.strip()] if args.queries else None

    champions = find_champions(client, queries=queries, category_id=args.category, top_n=args.top)

    if not champions:
        print("Nenhum produto campeao encontrado (verifique conexao/termos de busca).")
        return 1

    print(f"{'SCORE':>8}  {'VENDAS':>7}  {'CONCORR.':>9}  {'PRECO':>10}  FRETE GRATIS  TERMO / TITULO")
    for c in champions:
        print(
            f"{c.score:8.2f}  {c.sold_quantity:7d}  {c.competitor_count:9d}  "
            f"R$ {c.price:7.2f}  {'sim' if c.free_shipping else 'nao':>12}  "
            f"[{c.query}] {c.title[:60]}"
        )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[f.name for f in dataclasses.fields(champions[0])])
            writer.writeheader()
            for c in champions:
                writer.writerow(dataclasses.asdict(c))
        print(f"\nRelatorio salvo em {args.output}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="MLB", help="Site do Mercado Livre (MLB=Brasil, MLA=Argentina, ...)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("price-report", help="Gera relatorio de precos sugeridos")
    p_report.add_argument("--config", default="config/products.json")
    p_report.add_argument("--output", default=str(DATA_DIR / "price_report.csv"))
    p_report.set_defaults(func=cmd_price_report)

    p_apply = sub.add_parser("apply-prices", help="Aplica os precos sugeridos no Mercado Livre")
    p_apply.add_argument("--config", default="config/products.json")
    p_apply.add_argument("--confirm", action="store_true", help="Aplica de fato (sem isso, roda em modo simulacao)")
    p_apply.set_defaults(func=cmd_apply_prices)

    p_champ = sub.add_parser("find-champions", help="Busca produtos campeoes (alta demanda, baixa concorrencia)")
    p_champ.add_argument("--queries", help="Lista de termos separados por virgula. Se omitido, usa tendencias do ML.")
    p_champ.add_argument("--category", help="ID de categoria do Mercado Livre (opcional)")
    p_champ.add_argument("--top", type=int, default=20)
    p_champ.add_argument("--output", default=str(DATA_DIR / "champions.csv"))
    p_champ.set_defaults(func=cmd_find_champions)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
