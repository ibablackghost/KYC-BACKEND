from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    message = _flatten(response.data)
    if message:
        response.data = {"message": message}
    return response


def _flatten(data):
    if isinstance(data, dict):
        if isinstance(data.get("message"), str) and data["message"].strip():
            return data["message"].strip()
        if "detail" in data:
            return _flatten(data["detail"])
        parts = []
        for value in data.values():
            text = _flatten(value)
            if text:
                parts.append(text)
        return " ".join(parts)
    if isinstance(data, list):
        return " ".join(text for item in data if (text := _flatten(item)))
    if data is None:
        return ""
    return str(data).strip()
