"""Middleware for MindMend app."""

TRACK_PATHS = ('/', '/chat/', '/login/', '/register/', '/mood/', '/forum/', '/dashboard/', '/resources/')


class LocationTrackingMiddleware:
    """
    Logs user access with geolocation on key pages. Throttled per IP (1/hour).
    Respects the user's location_opt_out privacy setting.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if any(path == p or path.startswith(p.rstrip('/') + '/') for p in TRACK_PATHS):
            # Respect privacy opt-out: skip tracking for users who have opted out
            if self._user_opted_out(request):
                return response
            try:
                from .location_tracker import log_access
                log_access(request)
            except Exception:
                pass
        return response

    def _user_opted_out(self, request) -> bool:
        """Return True if the authenticated user has opted out of location tracking."""
        if not request.user.is_authenticated:
            return False
        try:
            return bool(request.user.profile.location_opt_out)
        except Exception:
            return False
