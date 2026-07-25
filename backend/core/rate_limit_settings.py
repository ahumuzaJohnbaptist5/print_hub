# core/rate_limit_settings.py
"""
Rate Limiting Configuration for PrintHub
"""

# Rate limit settings
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Different rate limits for different endpoints
RATE_LIMITS = {
    # Authentication (strict)
    'auth_login': '5/5m',      # 5 attempts per 5 minutes
    'auth_register': '3/10m',  # 3 attempts per 10 minutes
    'auth_verify': '10/1h',    # 10 attempts per hour
    
    # File Uploads (moderate)
    'file_upload': '20/1h',    # 20 uploads per hour
    'file_download': '100/1h', # 100 downloads per hour
    
    # Orders (moderate)
    'order_create': '30/1h',   # 30 orders per hour
    'order_track': '50/1h',    # 50 tracks per hour
    
    # Payment (strict)
    'payment_init': '10/30m',   # 10 payment initiations per 30 mins
    'payment_verify': '20/1h',  # 20 verifications per hour
    
    # API (moderate)
    'api_liveboard': '200/1m',  # 200 requests per minute
    'api_search': '60/1h',      # 60 searches per hour
    
    # WhatsApp (strict)
    'whatsapp_webhook': '100/5m', # 100 webhook calls per 5 mins
    
    # General (default)
    'default': '100/1h',        # 100 requests per hour
}

# Custom messages for rate limit exceeded
RATELIMIT_MESSAGES = {
    'auth_login': 'Too many login attempts. Please try again in {time} minutes.',
    'auth_register': 'Too many registration attempts. Please try again later.',
    'file_upload': 'Upload limit exceeded. Please wait before uploading more files.',
    'payment_init': 'Too many payment attempts. Please wait before trying again.',
    'default': 'Too many requests. Please slow down and try again later.',
}
