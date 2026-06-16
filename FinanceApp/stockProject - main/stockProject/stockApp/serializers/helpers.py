def _get_request_id(request):
    return (request.META.get('HTTP_X_REQUEST_ID') or
            request.headers.get('X-Request-ID') or None)

def _get_session_id(request):
    return (request.META.get('HTTP_X_SESSION_ID') or
            request.headers.get('X-Session-ID') or None)