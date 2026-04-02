# catalogue_api/urls.py
from django.urls import path
from .views.product_views import ProductSearchView, ProductSEOUpdateView

urlpatterns = [
    path("products/search/", ProductSearchView.as_view(), name="api_product_search"),
    path("products/update-seo/", ProductSEOUpdateView.as_view(), name="api_product_update_seo"),
]
