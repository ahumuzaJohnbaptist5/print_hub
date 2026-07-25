# core/rate_limit_monitor.py
"""
Rate Limit Monitoring and Reporting
"""
from django.core.cache import cache
from django.utils import timezone
import json

class RateLimitMonitor:
    """Monitor and report on rate limit usage."""
    
    @staticmethod
    def get_rate_limit_status(request, key_prefix):
        """Get current rate limit status for a client."""
        client_id = request.META.get('REMOTE_ADDR', 'unknown')
        if request.user.is_authenticated:
            client_id = f"user_{request.user.id}"
        
        cache_key = f'ratelimit:{key_prefix}:{client_id}'
        current = cache.get(cache_key, 0)
        
        # Note: We don't store the limit in the cache, so we need to know it
        # This is just for monitoring purposes
        
        return {
            'client': client_id,
            'current_requests': current,
            'key': key_prefix,
            'timestamp': timezone.now().isoformat(),
        }
    
    @staticmethod
    def get_all_rate_limits(request):
        """Get all rate limits for a client."""
        # List of all rate limit keys we use
        keys = ['login', 'register', 'upload', 'payment', 'api_liveboard', 'whatsapp']
        
        statuses = []
        for key in keys:
            statuses.append(RateLimitMonitor.get_rate_limit_status(request, key))
        
        return statuses

# Add a management command to view rate limit status
# python manage.py shell
# from core.rate_limit_monitor import RateLimitMonitor
# RateLimitMonitor.get_all_rate_limits(request)
