"""Middleware for MindMend app."""

TRACK_PATHS = ('/', '/chat/', '/login/', '/register/', '/mood/', '/forum/', '/dashboard/', '/resources/')

# Paths that are always allowed — even before profile setup is complete.
_SETUP_EXEMPT_PREFIXES = (
    '/profile/setup/',
    '/profile/toggle-identity/',
    '/logout/',
    '/static/',
    '/media/',
    '/favicon.ico',
)


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


class ProfileSetupMiddleware:
    """
    Redirects authenticated users who haven't completed their profile setup.
    Counsellor accounts (linked to a Counsellor object) are exempt.
    Static files, media, logout, and the setup page itself are also exempt.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._needs_redirect(request):
            from django.shortcuts import redirect
            return redirect('profile_setup')
        return self.get_response(request)

    def _needs_redirect(self, request) -> bool:
        if not request.user.is_authenticated:
            return False

        path = request.path

        # Exempt paths — always allowed
        for prefix in _SETUP_EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return False

        # Counsellor/doctor accounts skip mandatory setup
        try:
            from .models import Counsellor
            if Counsellor.objects.filter(user=request.user).exists():
                return False
        except Exception:
            return False

        # Check profile completion
        try:
            return not request.user.profile.profile_complete
        except Exception:
            # No profile yet — redirect to setup
            return True
