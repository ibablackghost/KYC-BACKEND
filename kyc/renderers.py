from rest_framework.renderers import JSONRenderer


class UnicodeJSONRenderer(JSONRenderer):
    ensure_ascii = False
