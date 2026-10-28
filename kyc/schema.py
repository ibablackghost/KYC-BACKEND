def only_api_endpoints(endpoints, **kwargs):
    kept = []
    for endpoint in endpoints:
        path = endpoint[0]
        if path.startswith("/api/") and not path.startswith("/api/docs") and not path.startswith("/api/schema"):
            kept.append(endpoint)
    return kept
