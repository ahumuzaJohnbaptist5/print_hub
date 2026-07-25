# core/middleware.py
"""
Rate limiting middleware for global API protection
"""
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import re

class GlobalRateLimitMiddleware(MiddlewareMixin):
    """
    Middleware to apply rate limiting to all API endpoints
    """
    
    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = [
        r'^/admin/',
        r'^/static/',
        r'^/media/',
        r'^/favicon.ico',
        r'^/sw.js',
        r'^/manifest.json',
    ]
    
    # Different rate limits for different path patterns
    PATH_RATES = [
        (r'^/api/', '100/1m'),      # API endpoints: 100 per minute
        (r'^/auth/', '20/5m'),      # Auth endpoints: 20 per 5 minutes
        (r'^/payments/', '10/5m'),  # Payment endpoints: 10 per 5 minutes
        (r'^/orders/upload/', '10/1h'),  # Upload: 10 per hour
        (r'^/whatsapp/', '50/5m'),  # WhatsApp: 50 per 5 minutes
    ]
    
    DEFAULT_RATE = '50/1h'  # 50 per hour default
    
    def process_request(self, request):
        # Skip if rate limiting disabled
        if not getattr(settings, 'RATELIMIT_ENABLE', True):
            return None
        
        path = request.path
        
        # Skip excluded paths
        for pattern in self.EXCLUDED_PATHS:
            if re.match(pattern, path):
                return None
        
        # Determine rate limit for this path
        rate_limit = self.DEFAULT_RATE
        for pattern, rate in self.PATH_RATES:
            if re.match(pattern, path):
                rate_limit = rate
                break
        
        # Parse rate limit
        limit, period = self.parse_rate(rate_limit)
        
        # Get client identifier
        client_id = self.get_client_id(request)
        cache_key = f'global_ratelimit:{client_id}:{path}'
        
        # Check current count
        current = cache.get(cache_key, 0)
        
        if current >= limit:
            # Rate limit exceeded
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': True,
                    'message': 'Too many requests. Please try again later.',
                    'retry_after': period,
                    'limit': limit,
                }, status=429)
            return None  # Let the view handle it
        
        # Increment counter
        cache.set(cache_key, current + 1, period)
        
        # Store rate limit info in request for views to use
        request.rate_limit_info = {
            'limit': limit,
            'remaining': limit - current - 1,
            'period': period,
        }
        
        return None
    
    def parse_rate(self, rate_str):
        """Parse rate limit string like '100/1m' into (limit, period_seconds)."""
        parts = rate_str.split('/')
        limit = int(parts[0])
        period_str = parts[1]
        
        # Parse period
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
            period = 3600  # Default to 1 hour
        
        return limit, period
    
    def get_client_id(self, request):
        """Get unique client identifier."""
        if request.user.is_authenticated:
            return f"user_{request.user.id}"



    # Add this method to GlobalRateLimitMiddleware

def process_response(self, request, response):
    """Add rate limit headers to response."""
    if hasattr(request, 'rate_limit_info'):
        info = request.rate_limit_info
        response['X-RateLimit-Limit'] = str(info['limit'])
        response['X-RateLimit-Remaining'] = str(info['remaining'])
        response['X-RateLimit-Reset'] = str(timezone.now().timestamp() + info['period'])
    
    return response
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        if not ip:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return f"ip_{ip}"
