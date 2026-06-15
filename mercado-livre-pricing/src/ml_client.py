"""Cliente para a API do Mercado Livre.

Endpoints publicos (busca, tendencias, detalhes de itens) nao exigem
autenticacao. Endpoints que alteram dados do vendedor (ex: atualizar preco
de um anuncio) exigem um access_token OAuth2 - veja get_authorization_url
e exchange_code_for_token para o fluxo de obtencao do token.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

import requests

API_BASE = "https://api.mercadolibre.com"
AUTH_BASE = "https://auth.mercadolibre.com.br"


class MLApiError(RuntimeError):
    """Erro retornado pela API do Mercado Livre."""


@dataclass
class MLCredentials:
    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None

    @classmethod
    def from_env(cls) -> "MLCredentials":
        return cls(
            client_id=os.getenv("ML_CLIENT_ID") or None,
            client_secret=os.getenv("ML_CLIENT_SECRET") or None,
            redirect_uri=os.getenv("ML_REDIRECT_URI") or None,
            access_token=os.getenv("ML_ACCESS_TOKEN") or None,
            refresh_token=os.getenv("ML_REFRESH_TOKEN") or None,
        )


class MLClient:
    """Cliente fino sobre a API REST do Mercado Livre."""

    def __init__(self, site_id: str = "MLB", credentials: MLCredentials | None = None,
                 session: requests.Session | None = None, timeout: float = 15.0):
        self.site_id = site_id
        self.credentials = credentials or MLCredentials()
        self.session = session or requests.Session()
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Endpoints publicos (sem autenticacao)
    # ------------------------------------------------------------------
    def search(self, query: str, limit: int = 50, offset: int = 0,
               category_id: str | None = None) -> dict[str, Any]:
        """Busca produtos publicos por palavra-chave."""
        params: dict[str, Any] = {"q": query, "limit": min(limit, 50), "offset": offset}
        if category_id:
            params["category"] = category_id
        return self._get(f"/sites/{self.site_id}/search", params=params)

    def search_all(self, query: str, max_results: int = 200,
                    category_id: str | None = None) -> list[dict[str, Any]]:
        """Pagina a busca publica ate atingir max_results itens."""
        results: list[dict[str, Any]] = []
        offset = 0
        page_size = 50
        while len(results) < max_results:
            page = self.search(query, limit=page_size, offset=offset, category_id=category_id)
            items = page.get("results", [])
            if not items:
                break
            results.extend(items)
            offset += page_size
            total = page.get("paging", {}).get("total", len(results))
            if offset >= total:
                break
        return results[:max_results]

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Detalhes completos de um item (inclui sold_quantity)."""
        return self._get(f"/items/{item_id}")

    def get_items(self, item_ids: Iterable[str]) -> list[dict[str, Any]]:
        """Busca multiplos itens em lote (max 20 por chamada)."""
        ids = list(item_ids)
        out: list[dict[str, Any]] = []
        for i in range(0, len(ids), 20):
            chunk = ids[i:i + 20]
            data = self._get("/items", params={"ids": ",".join(chunk)})
            for entry in data:
                if entry.get("code") == 200:
                    out.append(entry["body"])
        return out

    def get_trends(self, category_id: str | None = None) -> list[dict[str, Any]]:
        """Termos de busca em alta (ex: para descobrir produtos campeoes)."""
        path = f"/trends/{self.site_id}"
        if category_id:
            path += f"/{category_id}"
        return self._get(path)

    def get_categories(self) -> list[dict[str, Any]]:
        return self._get(f"/sites/{self.site_id}/categories")

    # ------------------------------------------------------------------
    # OAuth2 - autenticacao do vendedor
    # ------------------------------------------------------------------
    def get_authorization_url(self) -> str:
        if not (self.credentials.client_id and self.credentials.redirect_uri):
            raise MLApiError("ML_CLIENT_ID e ML_REDIRECT_URI precisam estar configurados")
        return (
            f"{AUTH_BASE}/authorization"
            f"?response_type=code&client_id={self.credentials.client_id}"
            f"&redirect_uri={self.credentials.redirect_uri}"
        )

    def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """Troca o 'code' obtido no redirect OAuth por access/refresh tokens."""
        creds = self.credentials
        if not (creds.client_id and creds.client_secret and creds.redirect_uri):
            raise MLApiError("Credenciais OAuth incompletas (client_id/secret/redirect_uri)")
        data = {
            "grant_type": "authorization_code",
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "code": code,
            "redirect_uri": creds.redirect_uri,
        }
        resp = self.session.post(f"{API_BASE}/oauth/token", data=data, timeout=self.timeout)
        self._raise_for_status(resp)
        token_data = resp.json()
        self.credentials.access_token = token_data.get("access_token")
        self.credentials.refresh_token = token_data.get("refresh_token")
        return token_data

    def refresh_access_token(self) -> dict[str, Any]:
        creds = self.credentials
        if not (creds.client_id and creds.client_secret and creds.refresh_token):
            raise MLApiError("Refresh token ou credenciais ausentes")
        data = {
            "grant_type": "refresh_token",
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
        }
        resp = self.session.post(f"{API_BASE}/oauth/token", data=data, timeout=self.timeout)
        self._raise_for_status(resp)
        token_data = resp.json()
        self.credentials.access_token = token_data.get("access_token")
        self.credentials.refresh_token = token_data.get("refresh_token", creds.refresh_token)
        return token_data

    # ------------------------------------------------------------------
    # Endpoints autenticados (gestao dos seus anuncios)
    # ------------------------------------------------------------------
    def get_my_user(self) -> dict[str, Any]:
        return self._get("/users/me", auth=True)

    def get_my_items(self, seller_id: str, status: str = "active",
                      max_results: int = 200) -> list[str]:
        """Retorna os IDs dos anuncios do vendedor."""
        ids: list[str] = []
        offset = 0
        while len(ids) < max_results:
            data = self._get(
                f"/users/{seller_id}/items/search",
                params={"status": status, "offset": offset, "limit": 50},
                auth=True,
            )
            page_ids = data.get("results", [])
            if not page_ids:
                break
            ids.extend(page_ids)
            offset += 50
            total = data.get("paging", {}).get("total", len(ids))
            if offset >= total:
                break
        return ids[:max_results]

    def update_item_price(self, item_id: str, price: float) -> dict[str, Any]:
        """Atualiza o preco de um anuncio proprio. Requer access_token valido."""
        return self._put(f"/items/{item_id}", json={"price": price}, auth=True)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if auth:
            if not self.credentials.access_token:
                raise MLApiError(
                    "Esta operacao requer ML_ACCESS_TOKEN. Configure as credenciais OAuth "
                    "(veja .env.example) antes de chamar endpoints autenticados."
                )
            headers["Authorization"] = f"Bearer {self.credentials.access_token}"
        return headers

    def _get(self, path: str, params: dict[str, Any] | None = None, auth: bool = False,
             _retry_on_401: bool = True) -> Any:
        resp = self.session.get(
            f"{API_BASE}{path}", params=params, headers=self._headers(auth), timeout=self.timeout
        )
        if resp.status_code == 401 and auth and _retry_on_401 and self.credentials.refresh_token:
            self.refresh_access_token()
            return self._get(path, params=params, auth=auth, _retry_on_401=False)
        self._raise_for_status(resp)
        return resp.json()

    def _put(self, path: str, json: dict[str, Any], auth: bool = False,
             _retry_on_401: bool = True) -> Any:
        resp = self.session.put(
            f"{API_BASE}{path}", json=json, headers=self._headers(auth), timeout=self.timeout
        )
        if resp.status_code == 401 and auth and _retry_on_401 and self.credentials.refresh_token:
            self.refresh_access_token()
            return self._put(path, json=json, auth=auth, _retry_on_401=False)
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if resp.ok:
            return
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        raise MLApiError(f"{resp.status_code} {resp.reason}: {detail}")


def with_rate_limit_backoff(func, *args, max_retries: int = 3, **kwargs):
    """Executa func aplicando backoff exponencial em caso de erro 429."""
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except MLApiError as exc:
            if "429" in str(exc) and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise
