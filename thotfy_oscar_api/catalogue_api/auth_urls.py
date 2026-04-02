# catalogue_api/auth_urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # POST /api/auth/token/  { username, password } → { access, refresh }
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    # POST /api/auth/token/refresh/  { refresh } → { access }
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
