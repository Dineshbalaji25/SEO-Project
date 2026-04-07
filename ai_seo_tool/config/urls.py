from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('seo_tool.urls')),
    path('api/auth/', include('catalogue_api.auth_urls')),
    path('api/', include('catalogue_api.urls')),
]
