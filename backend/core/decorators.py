# core/decorators.py
"""
Custom rate limiting decorators for PrintHub
"""
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
import re

def rate_limit(key_prefix, limit, period, message=None):
    """
    Custom rate limit decorator.
    
    Args:
        key_prefix: Prefix for the cache key (e.g., 'login', 'upload')
        limit: Number of allowed requests
        period: Time period in seconds (e.g., 300 for 5 minutes)
        message: Custom message when rate limit is exceeded
    
    Usage:
        @rate_limit('login', 5, 300, 'Too many login attempts')
        def login_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not getattr(settings, 'RATELIMIT_ENABLE', True):
                return view_func(request, *args, **kwargs)
            
            # Get client identifier (IP address or user ID if authenticated)
            client_id = get_client_identifier(request)
            cache_key = f'ratelimit:{key_prefix}:{client_id}'
            
            # Get current count
            current = cache.get(cache_key, 0)
            
            if current >= limit:
                # Rate limit exceeded
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': True,
                        'message': message or f'Rate limit exceeded. Please try again later.',
                        'retry_after': period,
                        'limit': limit,
                    }, status=429)
                return render_rate_limit_exceeded(request, message, period)
            
            # Increment counter
            cache.set(cache_key, current + 1, period)
            
            # Add headers to response
            response = view_func(request, *args, **kwargs)
            response['X-RateLimit-Limit'] = str(limit)
            response['X-RateLimit-Remaining'] = str(limit - current - 1)
            response['X-RateLimit-Reset'] = str(timezone.now().timestamp() + period)
            
            return response
        return wrapped
    return decorator

def get_client_identifier(request):
    """Get a unique identifier for the client."""
    # If user is authenticated, use their ID
    if request.user.is_authenticated:
        return f"user_{request.user.id}"
    
    # Otherwise use IP address
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    if not ip:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return f"ip_{ip}"

def render_rate_limit_exceeded(request, message, period):
    """Render rate limit exceeded page."""
    from django.shortcuts import render
    
    # Calculate time remaining
    minutes = period // 60
    seconds = period % 60
    
    time_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
    if seconds > 0:
        time_str += f" and {seconds} second{'s' if seconds != 1 else ''}"
    
    return render(request, 'rate_limit_exceeded.html', {
        'message': message or f'Too many requests. Please try again in {time_str}.',
        'retry_after': time_str,
        'limit_reached': True,
    }, status=429)
