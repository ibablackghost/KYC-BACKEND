import uuid
from urllib.parse import quote, urlsplit, urlunsplit

import requests
from django.conf import settings

CREATE_SESSION_URL = "https://verification.didit.me/v3/session/"
DECISION_URL = "https://verification.didit.me/v3/session/{session_id}/decision/"


class DiditError(Exception):
    def __init__(self, message, status_code=502, not_found=False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.not_found = not_found


def didit_configured():
    return configuration_problem() is None


def configuration_problem():
    missing_key = not _api_key()
    invalid_workflow = not _workflow_uuid()
    if missing_key and invalid_workflow:
        return (
            "La clé API Didit (DIDIT_API_KEY) et l'UUID du workflow "
            "(DIDIT_WORKFLOW_ID) ne sont pas configurés sur le serveur."
        )
    if missing_key:
        return "La clé API Didit (DIDIT_API_KEY) n'est pas configurée sur le serveur."
    if invalid_workflow:
        return "L'UUID du workflow Didit (DIDIT_WORKFLOW_ID) est absent ou invalide."
    return None


def create_session(account):
    problem = configuration_problem()
    if problem:
        raise DiditError(problem, status_code=503)

    status, body = _call("POST", CREATE_SESSION_URL, _session_payload(account))
    if status < 200 or status >= 300 or not isinstance(body, dict):
        message = "La création de la session Didit a échoué."
        detail = _safe_detail(body)
        if detail:
            message = f"{message} {detail}"
        raise DiditError(message, status_code=502)

    session_id = body.get("session_id")
    url = body.get("url")
    if not isinstance(session_id, str) or not session_id.strip():
        raise DiditError("Didit n'a pas renvoyé d'identifiant de session.", status_code=502)
    if not isinstance(url, str) or not url.strip():
        raise DiditError("Didit n'a pas renvoyé d'URL de vérification.", status_code=502)

    result = {"session_id": session_id.strip(), "url": url.strip()}
    raw_status = body.get("status")
    if isinstance(raw_status, str) and raw_status.strip():
        result["status"] = raw_status.strip()
    return result


def fetch_decision(session_id):
    problem = configuration_problem()
    if problem:
        raise DiditError(problem, status_code=503)

    encoded = quote(str(session_id), safe="")
    status, body = _call("GET", DECISION_URL.format(session_id=encoded))
    if status == 404:
        raise DiditError("Dossier introuvable.", status_code=404, not_found=True)
    if status < 200 or status >= 300 or not isinstance(body, dict):
        raise DiditError("Impossible de récupérer la décision Didit.", status_code=502)
    return body


def callback_url():
    raw = (getattr(settings, "PUBLIC_APP_URL", "") or "").strip() or "http://localhost:4200"
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        base = "http://localhost:4200"
    else:
        base = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    return base.rstrip("/") + "/verification"


def _session_payload(account):
    return {
        "workflow_id": _workflow_uuid(),
        "vendor_data": str(account.id),
        "callback": callback_url(),
        "callback_method": "both",
        "language": "fr",
        "contact_details": {
            "email": account.email,
            "phone": account.phone,
            "send_notification_emails": False,
            "email_lang": "fr",
        },
        "expected_details": {
            "first_name": account.first_name,
            "last_name": account.last_name,
            "date_of_birth": account.date_of_birth.isoformat(),
            "expected_document_types": ["ID"],
        },
        "metadata": {
            "source": "ouverture-compte",
            "required_checks": ["id_verification", "liveness", "face_match"],
        },
    }


def _call(method, url, payload=None):
    # La clé reste dans l'en-tête et n'est jamais journalisée.
    headers = {
        "x-api-key": _api_key(),
        "Accept": "application/json",
    }
    try:
        response = requests.request(
            method,
            url,
            json=payload,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise DiditError("Le service Didit est injoignable.", status_code=502) from exc
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _safe_detail(body):
    if not isinstance(body, dict):
        return None
    raw = body.get("detail")
    if isinstance(raw, list):
        raw = next((item for item in raw if isinstance(item, str)), None)
    if not isinstance(raw, str):
        return None
    text = " ".join(raw.split())
    if not text or len(text) > 300:
        return None
    secret = _api_key()
    lowered = text.lower()
    if secret and secret in text:
        return None
    if "session_token" in lowered or "x-api-key" in lowered:
        return None
    return text


def _api_key():
    return (getattr(settings, "DIDIT_API_KEY", "") or "").strip()


def _workflow_uuid():
    raw = (getattr(settings, "DIDIT_WORKFLOW_ID", "") or "").strip()
    if not raw:
        return ""
    try:
        return str(uuid.UUID(raw))
    except (ValueError, TypeError, AttributeError):
        return ""
