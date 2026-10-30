import requests
from django.core.files.base import ContentFile

_MAX_BYTES = 8 * 1024 * 1024

_FIELDS = (
    ("id_verifications", "front_image", "id_front"),
    ("id_verifications", "back_image", "id_back"),
    ("id_verifications", "portrait_image", "id_portrait"),
    ("liveness_checks", "reference_image", "face_photo"),
)


def store_verification_images(account, decision):
    """Copie le recto, le verso et les photos chez nous. Les liens Didit expirent."""
    for block_name, source_name, field_name in _FIELDS:
        url = _source_url(decision, block_name, source_name)
        content = _download(url)
        if content is None:
            continue
        extension, body = content
        field = getattr(account, field_name)
        if field:
            field.delete(save=False)
        field.save(f"{field_name}{extension}", ContentFile(body), save=False)


def _source_url(decision, block_name, source_name):
    blocks = decision.get(block_name) if isinstance(decision, dict) else None
    if not isinstance(blocks, list) or not blocks or not isinstance(blocks[0], dict):
        return None
    url = blocks[0].get(source_name)
    if isinstance(url, str) and url.startswith("https://"):
        return url
    return None


def _download(url):
    if not url:
        return None
    try:
        response = requests.get(url, timeout=20, stream=True)
    except requests.RequestException:
        return None
    try:
        if response.status_code != 200:
            return None
        body = response.content
    finally:
        response.close()
    if not body or len(body) > _MAX_BYTES:
        return None
    extension = _image_extension(body)
    if extension is None:
        return None
    return extension, body


def _image_extension(body):
    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return ".webp"
    return None
