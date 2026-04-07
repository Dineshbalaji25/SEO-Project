"""
catalogue_api/views/product_views.py

Two endpoints that the AI SEO tool calls:

  GET  /api/products/search/?partner_name=X&product_name=Y
       → returns matching products so the caller can confirm before writing

  PATCH /api/products/update-seo/
        body: { partner_name, product_name, seo_title, seo_description, meta_description }
        → finds the product, writes the three SEO fields, returns updated product
"""
from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from oscar.core.loading import get_model

from ..serializers.product_serializers import (
    ProductPreviewSerializer,
    ProductSearchSerializer,
    ProductSEOUpdateSerializer,
)

logger = logging.getLogger(__name__)

try:
    from oscar.core.loading import get_model
    Product = get_model("catalogue", "Product")
    Partner = get_model("partner", "Partner")
    HAS_OSCAR = True
except (ImportError, Exception):
    # Failsafe for local testing without Oscar
    Product = None
    Partner = None
    HAS_OSCAR = False


def _build_admin_url(product: "Product") -> str:
    """Construct the thotfy admin URL for a product."""
    return f"https://thotfy.com/dashboard/catalogue/products/{product.pk}/"


def _product_to_preview(product: "Product", partner_name: str) -> dict:
    """Serialize a Product into the lightweight preview dict."""
    return {
        "id": product.pk,
        "title": product.title,
        "slug": product.slug,
        "partner_name": partner_name,
        "description": product.description or "",
        # Oscar stores meta_title / meta_description on the product if using
        # oscar-meta or a custom fork. Fall back gracefully.
        "meta_title": getattr(product, "meta_title", "") or "",
        "meta_description": getattr(product, "meta_description", "") or "",
        "admin_url": _build_admin_url(product),
    }


def _find_products(partner_name: str, product_name: str):
    """
    Locate products via Oscar's catalogue + partner relationship.
    Fallback to local mocks if Oscar isn't installed.
    """
    if not HAS_OSCAR:
        return _get_mock_products(partner_name, product_name), None

    try:
        partner = Partner.objects.get(name__iexact=partner_name.strip())
    except Partner.DoesNotExist:
        return None, f"No partner named '{partner_name}' found in thotfy.com."
    except Exception:
        # Fallback for multiple partners or other DB errors
        products = Product.objects.filter(
            stockrecords__partner__name__iexact=partner_name.strip(),
            title__icontains=product_name.strip(),
            structure__in=[Product.STANDALONE, Product.PARENT],
        ).distinct()
        return products, None

    products = (
        Product.objects
        .filter(
            stockrecords__partner=partner,
            title__icontains=product_name.strip(),
            structure__in=[Product.STANDALONE, Product.PARENT],
        )
        .distinct()
    )
    return products, None


def _get_mock_products(partner_name: str, product_name: str):
    """Local mock that generates a UNIQUE ID for each distinct product title."""
    from types import SimpleNamespace
    
    # Generate a unique ID based on the title (within a plausible range like 1000-9999)
    unique_id = 1000 + (hash(product_name.strip().lower()) % 9000)
    
    return [
        SimpleNamespace(
            pk=unique_id,
            title=product_name or "Handcrafted Sample",
            slug="handcrafted-sample-item",
            description="A beautiful item analyzed by AI.",
            meta_title="",
            meta_description="SEO-optimized product metadata.",
        )
    ]


class ProductSearchView(APIView):
    """
    GET /api/products/search/?partner_name=Acme&product_name=Bamboo+Board

    Returns matching products so the AI tool can confirm before writing.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProductSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        partner_name = serializer.validated_data["partner_name"]
        product_name = serializer.validated_data["product_name"]

        products, error = _find_products(partner_name, product_name)

        if error:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)

        if not products:
            return Response(
                {
                    "detail": (
                        f"No products matching '{product_name}' found "
                        f"for partner '{partner_name}'."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        results = [_product_to_preview(p, partner_name) for p in products[:10]]
        return Response({"count": len(results), "products": results})


class ProductSEOUpdateView(APIView):
    """
    PATCH /api/products/update-seo/

    Finds the product by partner + name, writes the three SEO fields.
    If multiple products match, returns a 300 MULTIPLE CHOICES response
    listing them — the caller should disambiguate and retry.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = ProductSEOUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        partner_name = data["partner_name"]
        product_name = data["product_name"]

        products, error = _find_products(partner_name, product_name)

        if error:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)

        if not products:
            return Response(
                {
                    "detail": (
                        f"No products matching '{product_name}' found "
                        f"for partner '{partner_name}'."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        count = len(products) if isinstance(products, list) else products.count()
        if count > 1:
            # Ambiguous — return the choices so the caller can show them
            results = [_product_to_preview(p, partner_name) for p in products[:10]]
            return Response(
                {
                    "detail": (
                        f"Found {count} products matching '{product_name}'. "
                        "Please refine the product name."
                    ),
                    "products": results,
                },
                status=status.HTTP_300_MULTIPLE_CHOICES,
            )

        product = products[0] if not HAS_OSCAR else products.first()

        # ── Write the SEO fields ──────────────────────────────────────────────
        product.title = data["seo_title"]
        product.description = data["seo_description"]

        if HAS_OSCAR:
            # Write meta_description if the Oscar model has it
            if hasattr(product, "meta_title"):
                product.meta_title = data["seo_title"]
            if hasattr(product, "meta_description"):
                product.meta_description = data["meta_description"]

            product.save(
                update_fields=_build_update_fields(product)
            )

        logger.info(
            "SEO fields updated for product '%s' (pk=%d) by partner '%s' (Mock: %s)",
            product.title,
            product.pk,
            partner_name,
            not HAS_OSCAR
        )

        preview = _product_to_preview(product, partner_name)
        preview["meta_description"] = data["meta_description"]  # reflect written value

        return Response(
            {
                "detail": "Product SEO fields updated successfully." if HAS_OSCAR else "Mock: Product SEO fields updated successfully.",
                "product": preview,
            },
            status=status.HTTP_200_OK,
        )


def _build_update_fields(product: "Product") -> list[str]:
    """Build the save() update_fields list based on which fields exist."""
    fields = ["title", "description"]
    if hasattr(product, "meta_title"):
        fields.append("meta_title")
    if hasattr(product, "meta_description"):
        fields.append("meta_description")
    return fields
