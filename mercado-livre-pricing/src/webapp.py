"""Dashboard web local para o sistema de gestao de precos.

Uso:
    python -m src.webapp

Abre em http://127.0.0.1:5000 - mostra o relatorio de precos dos produtos
configurados em config/products.json e permite buscar produtos campeoes,
sem precisar usar a linha de comando.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from .ml_client import MLApiError
from .pricing_engine import suggest_price
from .product_finder import find_champions
from .services import (
    DEFAULT_CONFIG_PATH,
    build_price_report,
    client_from_env,
    competitors_for,
    current_price,
    load_products,
)


def create_app(config_path: Path = DEFAULT_CONFIG_PATH) -> Flask:
    app = Flask(__name__)
    app.secret_key = "ml-pricing-dashboard"  # apenas para mensagens flash locais

    @app.route("/")
    def dashboard():
        if not config_path.exists():
            return render_template(
                "dashboard.html",
                suggestions=None,
                error=(
                    f"Arquivo de configuracao nao encontrado: {config_path}. "
                    "Copie config/products.example.json para config/products.json "
                    "e edite com os seus produtos."
                ),
            )

        client = client_from_env()
        products = load_products(config_path)
        error = None
        try:
            suggestions = build_price_report(client, products)
        except MLApiError as exc:
            suggestions = []
            error = f"Erro ao consultar a API do Mercado Livre: {exc}"

        return render_template("dashboard.html", suggestions=suggestions, error=error)

    @app.route("/champions")
    def champions():
        queries_raw = request.args.get("queries", "").strip()
        results = []
        error = None
        searched = bool(request.args.get("search"))

        if searched:
            client = client_from_env()
            queries = [q.strip() for q in queries_raw.split(",") if q.strip()] or None
            try:
                results = find_champions(client, queries=queries, top_n=20)
            except MLApiError as exc:
                error = f"Erro ao consultar a API do Mercado Livre: {exc}"

        return render_template(
            "champions.html", results=results, queries=queries_raw, error=error, searched=searched
        )

    @app.route("/apply/<sku>", methods=["POST"])
    def apply_price(sku: str):
        client = client_from_env()
        products = {p.sku: p for p in load_products(config_path)}
        product = products.get(sku)

        if not product or not product.item_id:
            flash(f"Produto {sku} nao encontrado ou sem item_id configurado.", "error")
            return redirect(url_for("dashboard"))

        current = current_price(client, product)
        competitors = competitors_for(client, product)
        suggestion = suggest_price(product, competitors, current_price=current)

        try:
            client.update_item_price(product.item_id, suggestion.suggested_price)
            flash(f"{sku}: preco atualizado para R$ {suggestion.suggested_price:.2f}.", "success")
        except MLApiError as exc:
            flash(f"{sku}: erro ao atualizar preco - {exc}", "error")

        return redirect(url_for("dashboard"))

    return app


def main() -> None:
    app = create_app()
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
