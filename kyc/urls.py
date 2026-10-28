from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from .views import (
    AccountDetailView,
    AccountListCreateView,
    HealthView,
    VerificationDetailView,
)

urlpatterns = [
    path(
        "schema/",
        SpectacularAPIView.as_view(authentication_classes=[], permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            authentication_classes=[],
            permission_classes=[AllowAny],
        ),
        name="swagger",
    ),
    path("health/", HealthView.as_view(), name="health"),
    path("accounts/", AccountListCreateView.as_view(), name="account-list"),
    path("accounts/<uuid:account_id>/", AccountDetailView.as_view(), name="account-detail"),
    path(
        "verifications/<str:session_id>/",
        VerificationDetailView.as_view(),
        name="verification-detail",
    ),
]
