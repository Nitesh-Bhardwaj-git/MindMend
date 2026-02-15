"""
User location tracking from IP using ip-api.com (free, no key required).
Tracks: Country, State, City, lat/lon.
"""
import logging
import time
import urllib.request
import json

logger = logging.getLogger(__name__)
_CACHE = {}  # ip -> (data, timestamp)
_CACHE_TTL = 3600  # 1 hour


def get_client_ip(request):
    """Extract client IP from request (handles proxies, load balancers, CDN)."""
    headers = (
        'HTTP_X_FORWARDED_FOR',      # Standard proxy
        'HTTP_X_REAL_IP',            # Nginx
        'HTTP_CF_CONNECTING_IP',     # Cloudflare
        'HTTP_TRUE_CLIENT_IP',       # Akamai
        'HTTP_X_CLIENT_IP',
        'HTTP_X_CLUSTER_CLIENT_IP',
    )
    for h in headers:
        val = request.META.get(h)
        if val:
            ip = val.split(',')[0].strip()
            if ip and ip not in ('127.0.0.1', '::1'):
                return ip
    return request.META.get('REMOTE_ADDR', '')


def _is_local_ip(ip):
    """Skip lookup for local/private IPs."""
    if not ip:
        return True
    if ip in ('127.0.0.1', '::1', 'localhost'):
        return True
    parts = ip.split('.')
    if len(parts) == 4:
        try:
            first = int(parts[0])
            if first == 10 or (first == 172 and 16 <= int(parts[1]) <= 31) or (first == 192 and int(parts[1]) == 168):
                return True
        except (ValueError, IndexError):
            pass
    return False


def geolocate_ip(ip):
    """
    Get country, state, city, lat, lon from IP via ip-api.com.
    Returns dict or None on failure. Caches results.
    """
    if not ip or _is_local_ip(ip):
        return None
    now = time.time()
    if ip in _CACHE and (now - _CACHE[ip][1]) < _CACHE_TTL:
        return _CACHE[ip][0]
    try:
        url = f'http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon'
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        if data.get('status') != 'success':
            return None
        result = {
            'country': data.get('country', ''),
            'state': data.get('regionName', ''),
            'city': data.get('city', ''),
            'latitude': data.get('lat'),
            'longitude': data.get('lon'),
        }
        _CACHE[ip] = (result, now)
        return result
    except Exception as e:
        logger.warning('Geolocation failed for %s: %s', ip, e)
        return None


def log_access(request, page_path=None):
    """
    Log user access with location. Call from middleware or view.
    Throttles: same IP logged at most once per hour.
    """
    from .models import UserAccessLocation
    from django.utils import timezone
    from datetime import timedelta
    ip = get_client_ip(request)
    session_id = getattr(request.session, 'session_key', '') or ''
    if not session_id:
        try:
            request.session.save()
            session_id = getattr(request.session, 'session_key', '') or ''
        except Exception:
            session_id = ''
    user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None

    cutoff = timezone.now() - timedelta(hours=1)

    if _is_local_ip(ip):
        # For local dev: store a placeholder once per hour per visitor identity.
        local_qs = UserAccessLocation.objects.filter(
            created_at__gte=cutoff,
            country='Local',
            state='Development',
            location_source='ip',
        )
        if user:
            local_qs = local_qs.filter(user=user)
        elif session_id:
            local_qs = local_qs.filter(user__isnull=True, session_id=session_id)
        if local_qs.exists():
            return
        UserAccessLocation.objects.create(
            user=user,
            session_id=session_id,
            ip_address=None,
            country='Local',
            state='Development',
            city='Localhost',
            latitude=28.6139,
            longitude=77.2090,
            page_path=page_path or request.path[:255],
            location_source='ip',
        )
        return
    geo = geolocate_ip(ip)
    if not geo:
        return
    # Throttle per visitor identity (user/session) + IP for 1 hour.
    recent_qs = UserAccessLocation.objects.filter(ip_address=ip, created_at__gte=cutoff)
    if user:
        recent_qs = recent_qs.filter(user=user)
    elif session_id:
        recent_qs = recent_qs.filter(user__isnull=True, session_id=session_id)
    if recent_qs.exists():
        return
    UserAccessLocation.objects.create(
        user=user,
        session_id=session_id,
        ip_address=ip,
        country=geo.get('country', ''),
        state=geo.get('state', ''),
        city=geo.get('city', ''),
        latitude=geo.get('latitude'),
        longitude=geo.get('longitude'),
        page_path=page_path or request.path[:255],
        location_source='ip',
    )


def reverse_geocode(lat, lon):
    """Convert lat/lon to city, state, country via OpenStreetMap Nominatim."""
    try:
        url = f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json'
        req = urllib.request.Request(url, headers={'User-Agent': 'MindMend/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        addr = data.get('address', {})
        return {
            'country': addr.get('country', ''),
            'state': addr.get('state') or addr.get('region', ''),
            'city': addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county', ''),
        }
    except Exception as e:
        logger.warning('Reverse geocode failed: %s', e)
        return {'country': '', 'state': '', 'city': ''}
