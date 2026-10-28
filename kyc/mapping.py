import re

TERMINAL_STATUSES = {
    "approved",
    "declined",
    "in review",
    "expired",
    "abandoned",
    "kyc expired",
}

_REQUIRED_FEATURES = (
    ("la vérification d'identité (ID Verification)", ("ID", "ID_VERIFICATION")),
    ("la détection de présence (Liveness)", ("LIVENESS",)),
    ("la correspondance faciale (Face Match)", ("FACE_MATCH", "FACEMATCH")),
)


def is_terminal(status):
    if not isinstance(status, str):
        return False
    return status.strip().lower() in TERMINAL_STATUSES


def map_verification(decision):
    document = _map_document(_first_block(decision, "id_verifications"))
    liveness = _map_check(_first_block(decision, "liveness_checks"))
    face_match = _map_check(_first_block(decision, "face_matches"))
    return {
        "status": _text(decision.get("status")) if isinstance(decision.get("status"), str) else "",
        "document": document,
        "liveness": liveness,
        "faceMatch": face_match,
        "accountReady": _approved(document) and _approved(liveness) and _approved(face_match),
        "workflowGap": workflow_gap(decision),
        "aml": _map_aml(_first_block(decision, "aml_screenings")),
    }


def workflow_gap(decision):
    if "features" not in decision:
        return None
    tokens = _feature_tokens(decision.get("features"))
    missing = [
        label
        for label, names in _REQUIRED_FEATURES
        if tokens.isdisjoint(names)
    ]
    if not missing:
        return None
    if len(missing) == 1:
        steps = missing[0]
        pronoun = "cette étape"
    elif len(missing) == 2:
        steps = f"{missing[0]} ni {missing[1]}"
        pronoun = "ces étapes"
    else:
        steps = f"{missing[0]}, {missing[1]} et {missing[2]}"
        pronoun = "ces étapes"
    return (
        f"Le workflow Didit publié ne contient pas {steps}. "
        f"Ajoutez {pronoun} dans la console Didit."
    )


def _first_block(decision, key):
    value = decision.get(key) if isinstance(decision, dict) else None
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return None


def _map_document(block):
    if block is None:
        return None
    return {
        "status": _text(block.get("status")),
        "type": _text(block.get("document_type")),
        "fullName": _text(block.get("full_name")),
        "nationality": _text(block.get("nationality")),
        "dateOfBirth": _text(block.get("date_of_birth")),
        "documentNumber": mask_document_number(block.get("document_number")),
        "expirationDate": _text(block.get("expiration_date")),
        "warnings": _warnings(block),
    }


def _map_check(block):
    if block is None:
        return None
    return {
        "status": _text(block.get("status")),
        "score": _number(block.get("score")),
        "present": True,
    }


def _map_aml(block):
    if block is None:
        return None
    total = block.get("total_hits")
    if isinstance(total, bool) or not isinstance(total, int):
        total = 0
    return {
        "status": _text(block.get("status")),
        "totalHits": total,
    }


def mask_document_number(value):
    if not isinstance(value, str) or not value:
        return ""
    if len(value) <= 4:
        return value
    return ("•" * (len(value) - 4)) + value[-4:]


def _warnings(block):
    raw = block.get("warnings")
    if not isinstance(raw, list):
        return []
    texts = []
    for item in raw:
        if len(texts) >= 5:
            break
        if not isinstance(item, dict):
            continue
        text = item.get("short_description")
        if isinstance(text, str) and text.strip():
            texts.append(text)
    return texts


def _feature_tokens(features):
    parts = []
    if isinstance(features, str):
        parts = re.split(r"[,;\s]+", features)
    elif isinstance(features, list):
        for item in features:
            if isinstance(item, str):
                parts.extend(re.split(r"[,;\s]+", item))
    tokens = set()
    for part in parts:
        token = part.strip().upper().replace("-", "_")
        if token:
            tokens.add(token)
    return tokens


def _approved(block):
    return isinstance(block, dict) and str(block.get("status", "")).strip().lower() == "approved"


def _text(value):
    return value if isinstance(value, str) else ""


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value
