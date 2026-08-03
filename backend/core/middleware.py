# core/middleware.py
"""
Rate limiting middleware for global API protection
"""
import ipaddress
import re

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class GlobalRateLimitMiddleware(MiddlewareMixin):
    """
    Middleware to apply rate limiting to all API endpoints
    
    Features:
    - Admin/Staff bypass (developers never get locked out)
    - Path-specific rate limits
    - Atomic cache increments
    - Proxy IP resolution (X-Forwarded-For)
    - SEO crawler whitelist
    """
    
    # ⭐ NEW: Paths to exclude from rate limiting entirely
    EXCLUDED_PATHS = [
        r'^/admin/',
        r'^/static/',
        r'^/media/',
        r'^/favicon.ico',
        r'^/sw.js',
        r'^/manifest.json',
        r'^/health/',          # ⭐ NEW: Render health checks
        r'^/robots.txt',       # ⭐ NEW: Google SEO crawlers
        r'^/sitemap.xml',      # ⭐ NEW: Google SEO crawlers
        r'^/.well-known/',     # ⭐ NEW: SSL verification
    ]

    # ⭐ UPDATED: Different rate limits for different path patterns
    # Format: (regex pattern, rate, bucket_name)
    PATH_RATES = [
        # API endpoints - generous for Live Board and chat
        (r'^/api/', '120/1m', 'api'),           # ⭐ UPDATED: 120 from 100
        (r'^/api/assistant/', '120/1m', 'assistant'), # ⭐ NEW: Chatbot endpoint
        
        # Authentication - strict to prevent brute force
        (r'^/auth/', '20/5m', 'auth'),
        (r'^/login/', '20/5m', 'auth'),
        (r'^/register/', '10/5m', 'auth'),      # ⭐ NEW: Register endpoint
        
        # Payments - moderate protection
        (r'^/payments/', '30/5m', 'payments'),  # ⭐ UPDATED: 30 from 10
        
        # Uploads - protect storage
        (r'^/orders/upload/', '60/1h', 'upload'), # ⭐ UPDATED: 60 from 10
        (r'^/upload/', '60/1h', 'upload'),       # ⭐ NEW: Generic upload
        
        # WhatsApp webhooks - Meta is chatty
        (r'^/whatsapp/', '500/5m', 'whatsapp'),  # ⭐ UPDATED: 500 from 50
        (r'^/webhook/', '500/5m', 'webhook'),    # ⭐ NEW: Generic webhook
    ]

    # ⭐ UPDATED: Default rate from 50/1h to 120/1m
    # Normal browsing should not be strictly limited by the hour
    DEFAULT_RATE = '120/1m'  # ⭐ CHANGED: More generous for normal users
    DEFAULT_RATE_NAME = 'default'

    def process_request(self, request):
        # Skip if rate limiting disabled
        if not getattr(settings, 'RATELIMIT_ENABLE', True):
            return None

        path = request.path

        # Skip excluded paths
        for pattern in self.EXCLUDED_PATHS:
            if re.match(pattern, path):
                return None

        # ⭐ NEW: BYPASS FOR ADMINS & STAFF
        # Developers, admins, and agents should never be locked out
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.is_superuser or request.user.is_staff:
                return None

        # Determine rate limit and bucket for this path
        rate_limit, rate_name = self.get_rate_for_path(path)

        # Parse rate limit
        limit, period = self.parse_rate(rate_limit)

        # Get client identifier
        client_id = self.get_client_id(request)

        # Use bucket name instead of exact path to reduce bypass via path variation
        cache_key = f'global_ratelimit:{client_id}:{rate_name}'

        # Atomically increment and get current count + reset time
        current, reset_timestamp = self.increment_rate_counter(cache_key, period)

        # Store rate limit info in request for views/response
        request.rate_limit_info = {
            'limit': limit,
            'remaining': max(0, limit - current),
            'reset': reset_timestamp,
        }

        # Enforce limit
        if current > limit:
            return self.rate_limited_response(request, limit, reset_timestamp)

        return None

    def process_response(self, request, response):
        """Add rate limit headers to response."""
        info = getattr(request, 'rate_limit_info', None)
        if info:
            response['X-RateLimit-Limit'] = str(info['limit'])
            response['X-RateLimit-Remaining'] = str(info['remaining'])
            response['X-RateLimit-Reset'] = str(info['reset'])

        return response

    def get_rate_for_path(self, path):
        """Return (rate_limit, bucket_name) for a given path."""
        for pattern, rate, name in self.PATH_RATES:
            if re.match(pattern, path):
                return rate, name

        return self.DEFAULT_RATE, self.DEFAULT_RATE_NAME

    def parse_rate(self, rate_str):
        """Parse rate limit string like '100/1m' into (limit, period_seconds)."""
        try:
            parts = rate_str.split('/')
            limit = int(parts[0])
            period_str = parts[1]

            unit = period_str[-1]
            value = int(period_str[:-1])

            if unit == 's':
                period = value
            elif unit == 'm':
                period = value * 60
            elif unit == 'h':
                period = value * 3600
            elif unit == 'd':
                period = value * 86400
            else:
                period = 3600

            return limit, period
        except Exception:
            # Safe fallback
            return 50, 3600

    def increment_rate_counter(self, cache_key, period):
        """
        Atomically increment rate limit counter and return:
        (current_count, reset_timestamp)
        """
        now_ts = int(timezone.now().timestamp())
        expires_key = f'{cache_key}:expires'

        # Try to create the key first
        added = cache.add(cache_key, 1, timeout=period)

        if added:
            reset_ts = now_ts + period
            cache.set(expires_key, reset_ts, timeout=period)
            return 1, reset_ts

        # If key already exists, increment it
        try:
            current = cache.incr(cache_key)
        except ValueError:
            # In case key expired/disappeared between add and incr
            current = 1
            cache.set(cache_key, current, timeout=period)

        reset_ts = cache.get(expires_key)
        if not reset_ts:
            reset_ts = now_ts + period
            cache.set(expires_key, reset_ts, timeout=period)

        return current, reset_ts

    def rate_limited_response(self, request, limit, reset_timestamp):
        """Return a 429 response."""
        retry_after = max(1, reset_timestamp - int(timezone.now().timestamp()))

        wants_json = (
            request.path.startswith('/api/')
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.headers.get('Accept', '').startswith('application/json')
        )

        if wants_json:
            response = JsonResponse(
                {
                    'error': True,
                    'message': 'Too many requests. Please try again later.',
                    'retry_after': retry_after,
                    'limit': limit,
                },
                status=429,
            )
        else:
            response = HttpResponse(
                'Too many requests. Please try again later.',
                status=429,
            )

        response['Retry-After'] = str(retry_after)
        return response

    def get_client_id(self, request):
        """Get unique client identifier."""
        user = getattr(request, 'user', None)

        if user is not None and user.is_authenticated:
            return f'user_{user.pk}'

        ip = self.get_client_ip(request)
        return f'ip_{ip}'

    def get_client_ip(self, request):
        """
        Get client IP address safely.

        Important:
        - If you are behind a trusted reverse proxy, set RATELIMIT_TRUSTED_PROXY_COUNT.
        - If you are not behind a proxy, leave it as 0.
        """
        remote_addr = request.META.get('REMOTE_ADDR', '') or 'unknown'

        trusted_proxy_count = int(
            getattr(settings, 'RATELIMIT_TRUSTED_PROXY_COUNT', 0)
        )

        # If no trusted proxy, use direct connection IP only
        if trusted_proxy_count <= 0:
            return self.normalize_ip(remote_addr)

        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if not xff:
            return self.normalize_ip(remote_addr)

        ips = [ip.strip() for ip in xff.split(',') if ip.strip()]
        if not ips:
            return self.normalize_ip(remote_addr)

        # Take the right-most untrusted client IP based on trusted proxy count
        try:
            candidate = ips[-trusted_proxy_count]
        except IndexError:
            candidate = ips[0]

        normalized = self.normalize_ip(candidate)
        if normalized != 'unknown':
            return normalized

        return self.normalize_ip(remote_addr)

    @staticmethod
    def normalize_ip(value):
        """Normalize and validate IP address."""
        try:
            return str(ipaddress.ip_address(value))
        except (ValueError, TypeError):
            return 'unknown'
