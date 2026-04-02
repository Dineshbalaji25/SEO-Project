"""
services/thotfy_service.py

Client for thotfy.com's Oscar product API.

Flow:
  1. authenticate()   — POST /api/auth/token/ → cache the JWT access token
  2. search_product() — GET  /api/products/search/ → confirm product exists
  3. update_seo()     — PATCH /api/products/update-seo/ → write the three fields
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

from .claude_service import SEOContent

logger = logging.getLogger(__name__)

# Thread-safe token lock (multiple Celery workers may run simultaneously)
_token_lock = threading.Lock()
TOKEN_CACHE_KEY = "thotfy_jwt_access_token"
TOKEN_TTL = 60 * 90  # 90 min (tokens live 2h; refresh before expiry)


class ThotfyServiceError(Exception):
    """Raised on any thotfy.com API failure."""
    pass


class ThotfyAmbiguousProductError(ThotfyServiceError):
    """
    Raised when the search returns multiple products.
    Carries the list of candidates so the caller can surface them to the user.
    """
    def __init__(self, message: str, products: list[dict]):
        super().__init__(message)
        self.products = products


@dataclass
class ThotfyProduct:
    id: int
    title: str
    slug: str
    partner_name: str
    admin_url: str
    meta_description: str = ""


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_token() -> str:
    """Return a valid JWT access token, fetching a new one if the cache is empty."""
    with _token_lock:
        token = cache.get(TOKEN_CACHE_KEY)
        if token:
            return token

        url = f"{settings.THOTFY_BASE_URL}/api/auth/token/"
        try:
            resp = requests.post(
                url,
                json={
                    "username": settings.THOTFY_SERVICE_USERNAME,
                    "password": settings.THOTFY_SERVICE_PASSWORD,
                },
                timeout=10,
            )
        except requests.RequestException as e:
            raise ThotfyServiceError(f"Could not connect to thotfy.com auth: {e}") from e

        if resp.status_code == 401:
            raise ThotfyServiceError(
                "thotfy.com authentication failed — check THOTFY_SERVICE_USERNAME/PASSWORD."
            )
        if not resp.ok:
            raise ThotfyServiceError(
                f"thotfy.com auth error {resp.status_code}: {resp.text[:200]}"
            )

        token = resp.json()["access"]
        cache.set(TOKEN_CACHE_KEY, token, timeout=TOKEN_TTL)
        logger.debug("Fetched fresh JWT from thotfy.com")
        return token


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }


def _invalidate_token():
    """Force a fresh token on the next request (call after a 401)."""
    cache.delete(TOKEN_CACHE_KEY)


# ── Public API ────────────────────────────────────────────────────────────────

def search_product(partner_name: str, product_name: str) -> ThotfyProduct:
    """
    Search thotfy.com for the product and return it if exactly one match is found.

    Raises:
        ThotfyServiceError          — partner not found, no products, network error
        ThotfyAmbiguousProductError — multiple products matched
    """
    url = f"{settings.THOTFY_BASE_URL}/api/products/search/"
    params = {"partner_name": partner_name, "product_name": product_name}

    resp = _get_with_token_retry(url, params=params)

    if resp.status_code == 404:
        detail = resp.json().get("detail", "Product not found.")
        raise ThotfyServiceError(detail)

    if resp.status_code == 300:
        data = resp.json()
        raise ThotfyAmbiguousProductError(
            data.get("detail", "Multiple products found."),
            products=data.get("products", []),
        )

    if not resp.ok:
        raise ThotfyServiceError(
            f"thotfy.com search error {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    products = data.get("products", [])

    if len(products) == 0:
        raise ThotfyServiceError(
            f"No products matching '{product_name}' found for partner '{partner_name}'."
        )
    if len(products) > 1:
        raise ThotfyAmbiguousProductError(
            f"{len(products)} products match '{product_name}'. Please be more specific.",
            products=products,
        )

    p = products[0]
    return ThotfyProduct(
        id=p["id"],
        title=p["title"],
        slug=p["slug"],
        partner_name=p["partner_name"],
        admin_url=p["admin_url"],
        meta_description=p.get("meta_description", ""),
    )


def update_product_seo(
    partner_name: str,
    product_name: str,
    seo: SEOContent,
) -> ThotfyProduct:
    """
    Write the three SEO fields to the matched product on thotfy.com.

    Raises:
        ThotfyServiceError          — not found, network error, validation error
        ThotfyAmbiguousProductError — multiple products still matched
    """
    url = f"{settings.THOTFY_BASE_URL}/api/products/update-seo/"
    payload = {
        "partner_name": partner_name,
        "product_name": product_name,
        **seo.to_dict(),
    }

    resp = _patch_with_token_retry(url, payload)

    if resp.status_code == 404:
        raise ThotfyServiceError(resp.json().get("detail", "Product not found."))

    if resp.status_code == 300:
        data = resp.json()
        raise ThotfyAmbiguousProductError(
            data.get("detail", "Multiple products found."),
            products=data.get("products", []),
        )

    if resp.status_code == 400:
        raise ThotfyServiceError(
            f"Validation error from thotfy.com: {resp.json()}"
        )

    if not resp.ok:
        raise ThotfyServiceError(
            f"thotfy.com update error {resp.status_code}: {resp.text[:200]}"
        )

    p = resp.json()["product"]
    return ThotfyProduct(
        id=p["id"],
        title=p["title"],
        slug=p["slug"],
        partner_name=p["partner_name"],
        admin_url=p["admin_url"],
        meta_description=p.get("meta_description", seo.meta_description),
    )


# ── Request helpers with automatic token refresh on 401 ───────────────────────

def _get_with_token_retry(url: str, **kwargs) -> requests.Response:
    try:
        resp = requests.get(url, headers=_headers(), timeout=15, **kwargs)
        if resp.status_code == 401:
            _invalidate_token()
            resp = requests.get(url, headers=_headers(), timeout=15, **kwargs)
        return resp
    except requests.RequestException as e:
        raise ThotfyServiceError(f"Network error reaching thotfy.com: {e}") from e


def _patch_with_token_retry(url: str, payload: dict) -> requests.Response:
    try:
        resp = requests.patch(url, json=payload, headers=_headers(), timeout=20)
        if resp.status_code == 401:
            _invalidate_token()
            resp = requests.patch(url, json=payload, headers=_headers(), timeout=20)
        return resp
    except requests.RequestException as e:
        raise ThotfyServiceError(f"Network error reaching thotfy.com: {e}") from e
