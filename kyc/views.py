import uuid

from django.http import JsonResponse
from django.views.defaults import page_not_found
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .didit import (
    DiditError,
    configuration_problem,
    create_session,
    didit_configured,
    fetch_decision,
)
from .mapping import is_terminal, map_verification
from .models import Account
from .payload import account_payload
from .renderers import UnicodeJSONRenderer
from .serializers import (
    AccountCreateSerializer,
    AccountCreatedSerializer,
    AccountEnvelopeSerializer,
    AccountListSerializer,
    ErrorSerializer,
    HealthSerializer,
)


class PublicAPIView(APIView):
    """Routes JSON publiques : pas de session, donc pas de contrôle CSRF."""

    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [UnicodeJSONRenderer]


class HealthView(PublicAPIView):
    @extend_schema(
        summary="Santé de l'API",
        operation_id="health",
        tags=["Santé"],
        responses={200: HealthSerializer},
    )
    def get(self, request):
        return Response({"ok": True, "diditConfigured": didit_configured()})


class AccountListCreateView(PublicAPIView):
    @extend_schema(
        summary="Lister les dossiers",
        operation_id="account_list",
        tags=["Dossiers"],
        responses={200: AccountListSerializer},
    )
    def get(self, request):
        accounts = Account.objects.order_by("-created_at")
        return Response({"accounts": [account_payload(account) for account in accounts]})

    @extend_schema(
        summary="Créer un dossier et une session Didit",
        operation_id="account_create",
        tags=["Dossiers"],
        request=AccountCreateSerializer,
        responses={
            201: AccountCreatedSerializer,
            400: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = AccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        problem = configuration_problem()
        if problem:
            return Response({"message": problem}, status=503)
        data = serializer.validated_data
        account = Account.objects.create(
            first_name=data["firstName"],
            last_name=data["lastName"],
            email=data["email"],
            phone=data["phone"],
            date_of_birth=data["dateOfBirth"],
            consent=True,
            status="Not Started",
        )
        try:
            session = create_session(account)
        except DiditError as exc:
            account.delete()
            return Response({"message": exc.message}, status=exc.status_code)

        account.session_id = session["session_id"]
        account.verification_url = session["url"]
        if session.get("status"):
            account.status = session["status"]
        account.save(update_fields=["session_id", "verification_url", "status", "updated_at"])
        return Response(
            {
                "account": account_payload(account),
                "verificationUrl": account.verification_url,
            },
            status=201,
        )


class AccountDetailView(PublicAPIView):
    @extend_schema(
        summary="Lire un dossier et rafraîchir la décision",
        operation_id="account_retrieve",
        tags=["Dossiers"],
        responses={200: AccountEnvelopeSerializer, 404: ErrorSerializer},
    )
    def get(self, request, account_id):
        account = _get_account(account_id)
        _refresh_if_needed(account)
        return Response({"account": account_payload(account)})


class VerificationDetailView(PublicAPIView):
    @extend_schema(
        summary="Retrouver un dossier par session Didit",
        operation_id="verification_retrieve",
        tags=["Vérifications"],
        responses={
            200: AccountEnvelopeSerializer,
            404: ErrorSerializer,
            502: ErrorSerializer,
            503: ErrorSerializer,
        },
    )
    def get(self, request, session_id):
        account = Account.objects.filter(session_id=session_id).first()
        if account is None:
            try:
                account = _attach_from_didit(session_id)
            except DiditError as exc:
                return Response({"message": exc.message}, status=exc.status_code)
        else:
            _refresh_if_needed(account)
        return Response({"account": account_payload(account)})


def api_not_found(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse({"message": "Ressource introuvable."}, status=404)
    return page_not_found(request, exception)


def _get_account(account_id):
    try:
        return Account.objects.get(pk=account_id)
    except Account.DoesNotExist as exc:
        raise NotFound("Dossier introuvable.") from exc


def _refresh_if_needed(account):
    if not account.session_id or is_terminal(account.status):
        return
    try:
        decision = fetch_decision(account.session_id)
    except DiditError:
        account.verification_error = "Impossible de récupérer la décision Didit."
        account.save(update_fields=["verification_error", "updated_at"])
        return
    _apply_decision(account, decision)


def _attach_from_didit(session_id):
    try:
        decision = fetch_decision(session_id)
    except DiditError as exc:
        if exc.not_found:
            raise NotFound("Dossier introuvable.") from exc
        raise
    account = _account_from_vendor(decision.get("vendor_data"))
    if account is None:
        raise NotFound("Dossier introuvable.")
    _apply_decision(account, decision, session_id=session_id)
    return account


def _apply_decision(account, decision, session_id=None):
    if session_id and account.session_id != session_id:
        account.session_id = session_id
    status = decision.get("status")
    if isinstance(status, str) and status.strip():
        account.status = status.strip()
    if not account.verification_url:
        session_url = decision.get("session_url")
        if isinstance(session_url, str) and session_url.strip():
            account.verification_url = session_url.strip()
    account.verification = map_verification(decision)
    account.verification_error = None
    account.save()


def _account_from_vendor(vendor_data):
    if not isinstance(vendor_data, str) or not vendor_data.strip():
        return None
    try:
        account_id = uuid.UUID(vendor_data.strip())
    except ValueError:
        return None
    return Account.objects.filter(pk=account_id).first()
