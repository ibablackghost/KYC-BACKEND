import copy
from datetime import timezone as dt_timezone

from django.utils import timezone


def account_payload(account, request=None):
    return {
        "id": str(account.id),
        "firstName": account.first_name,
        "lastName": account.last_name,
        "email": account.email,
        "phone": account.phone,
        "dateOfBirth": account.date_of_birth.isoformat(),
        "status": account.status,
        "sessionId": account.session_id,
        "verificationUrl": account.verification_url,
        "verification": _verification(account, request),
        "verificationError": account.verification_error,
        "createdAt": _iso(account.created_at),
        "updatedAt": _iso(account.updated_at),
    }


def _verification(account, request):
    verification = account.verification
    if not isinstance(verification, dict):
        return verification
    verification = copy.deepcopy(verification)
    document = verification.get("document")
    if isinstance(document, dict):
        document["frontImageUrl"] = _file_url(account.id_front, request)
        document["backImageUrl"] = _file_url(account.id_back, request)
        document["portraitImageUrl"] = _file_url(account.id_portrait, request)
    liveness = verification.get("liveness")
    if isinstance(liveness, dict):
        liveness["photoUrl"] = _file_url(account.face_photo, request)
    return verification


def _file_url(field, request):
    if not field:
        return None
    if request is None:
        return field.url
    return request.build_absolute_uri(field.url)


def _iso(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
