from datetime import timezone as dt_timezone

from django.utils import timezone


def account_payload(account):
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
        "verification": account.verification,
        "verificationError": account.verification_error,
        "createdAt": _iso(account.created_at),
        "updatedAt": _iso(account.updated_at),
    }


def _iso(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
