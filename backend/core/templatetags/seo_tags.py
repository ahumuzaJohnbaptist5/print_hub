# core/templatetags/seo_tags.py
from django import template
from django.conf import settings
from core.seo import MetaTags, SEOGenerator

register = template.Library()

@register.simple_tag(takes_context=True)
def seo_meta(context):
    """Generate SEO meta tags for the current page"""
    request = context.get('request')
    
    if not request:
        return ''
    
    # Determine page type and get appropriate meta tags
    path = request.path
    
    page_configs = {
        '/': MetaTags.HOME,
        '/upload/': MetaTags.UPLOAD,
        '/dashboard/': MetaTags.DASHBOARD,
        '/pricing/': MetaTags.PRICING,
    }
    
    # Get config based on path, or use home as default
    config = page_configs.get(path, MetaTags.HOME)
    
    url = request.build_absolute_uri()
    seo = SEOGenerator.meta_tags(
        title=config['title'],
        description=config['description'],
        keywords=config.get('keywords', []),
        url=url
    )
    
    # Store JSON-LD in context for later use
    context['seo_json_ld'] = seo['json_ld']
    
    # Build meta tags HTML
    html = f"""
    <!-- Primary Meta Tags -->
    <title>{seo['title']}</title>
    <meta name="title" content="{seo['title']}">
    <meta name="description" content="{seo['description']}">
    <meta name="keywords" content="{seo['keywords']}">
    <meta name="robots" content="{seo['robots']}">
    <link rel="canonical" href="{seo['canonical']}">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="{seo['og_type']}">
    <meta property="og:url" content="{seo['og_url']}">
    <meta property="og:title" content="{seo['og_title']}">
    <meta property="og:description" content="{seo['og_description']}">
    <meta property="og:image" content="{seo['og_image']}">
    <meta property="og:site_name" content="{seo['og_site_name']}">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="{seo['twitter_card']}">
    <meta property="twitter:url" content="{seo['og_url']}">
    <meta property="twitter:title" content="{seo['twitter_title']}">
    <meta property="twitter:description" content="{seo['twitter_description']}">
    <meta property="twitter:image" content="{seo['twitter_image']}">
    """
    
    return html
