# backend/core/templatetags/seo_tags.py
from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag(takes_context=True)
def seo_meta(context):
    request = context.get('request')
    if not request:
        return ''
    
    path = request.path
    
    # Page-specific meta
    meta_configs = {
        '/': {
            'title': 'PrintHub — Kabale University Printing Services',
            'description': 'Upload your documents, pay with MTN or Airtel, and pick up at your nearest campus station. Fast, reliable printing for students.',
        },
        '/upload/': {
            'title': 'Upload Documents for Printing — PrintHub',
            'description': 'Upload PDF, Word, or image files for printing. Quick, affordable printing services for students at Kabale University.',
        },
        '/dashboard/': {
            'title': 'My Orders — PrintHub Dashboard',
            'description': 'View and track your printing orders. Check status, payment, and pickup details.',
        },
        '/track/': {
            'title': 'Track Your Order — PrintHub',
            'description': 'Track your printing order status. Enter your order ID or email to check progress.',
        },
        '/pricing/': {
            'title': 'Printing Prices — Affordable Student Printing',
            'description': 'See our competitive pricing for B&W and color printing. Special rates for students at Kabale University.',
        },
        '/stations/': {
            'title': 'PrintHub Stations — Pickup Locations',
            'description': 'Find your nearest PrintHub station on campus. View locations and pickup information.',
        },
    }
    
    # Find matching config
    config = meta_configs.get(path, meta_configs['/'])
    
    html = f"""
    <!-- Primary Meta Tags -->
    <title>{config['title']}</title>
    <meta name="description" content="{config['description']}">
    <link rel="canonical" href="{request.build_absolute_uri()}">
    
    <!-- Open Graph -->
    <meta property="og:title" content="{config['title']}">
    <meta property="og:description" content="{config['description']}">
    <meta property="og:url" content="{request.build_absolute_uri()}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="PrintHub">
    <meta property="og:image" content="https://www.printhubug.com/static/og-image.png">
    
    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{config['title']}">
    <meta name="twitter:description" content="{config['description']}">
    <meta name="twitter:image" content="https://www.printhubug.com/static/og-image.png">
    """
    
    return html
