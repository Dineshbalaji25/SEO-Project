from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def mock_token(request):
    """Mock JWT auth at /api/auth/token/"""
    return JsonResponse({
        "access": "mock_access_token_12345",
        "refresh": "mock_refresh_token_67890"
    })

def mock_search(request):
    """Mock product search at /api/products/search/"""
    partner_name = request.GET.get("partner_name", "Acme")
    product_name = request.GET.get("product_name", "Sample")
    
    # Return a list of plausible-looking products for the given name
    products = [
        {
            "id": 4041,
            "title": product_name or "Handcrafted Ceramic Mug",
            "slug": "handcrafted-ceramic-mug",
            "partner_name": partner_name,
            "admin_url": "https://thotfy.com/dashboard/catalogue/products/4041/",
            "meta_description": "A beautiful mock product for testing."
        }
    ]
    return JsonResponse({"count": 1, "products": products})

@csrf_exempt
def mock_update_seo(request):
    """Mock SEO update at /api/products/update-seo/"""
    if request.method == 'PATCH' or request.method == 'POST':
        data = json.loads(request.body)
        return JsonResponse({
            "detail": "Mock: Product SEO fields updated successfully.",
            "product": {
                "id": data.get("id", 4041),
                "title": data.get("seo_title", "Mock Title"),
                "slug": "mock-slug",
                "partner_name": data.get("partner_name", "Mock Partner"),
                "admin_url": f"https://thotfy.com/dashboard/catalogue/products/4041/",
                "meta_description": data.get("meta_description", "Mock Meta")
            }
        })
    return JsonResponse({"error": "Method not allowed"}, status=405)
