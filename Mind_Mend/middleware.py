"""Middleware for MindMend app."""

TRACK_PATHS = ('/', '/chat/', '/login/', '/register/', '/mood/', '/forum/', '/dashboard/', '/resources/')


class LocationTrackingMiddleware:
    """
    Logs user access with geolocation on key pages. Throttled per IP (1/hour).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if any(path == p or path.startswith(p.rstrip('/') + '/') for p in TRACK_PATHS):
            try:
                from .location_tracker import log_access
                log_access(request)
            except Exception:
                pass
        return response
