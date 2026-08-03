# core/seo.py
"""
SEO utilities for PrintHub
"""
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.contrib.sites.models import Site
from typing import Dict, List, Optional
import json

class SEOGenerator:
    """Generate SEO metadata for pages"""
    
    @staticmethod
    def meta_tags(title: str, description: str, keywords: list = None, 
                  image: str = None, url: str = None, page_type: str = 'website') -> Dict:
        """Generate complete meta tags for a page"""
        
        if not url:
            url = settings.BASE_URL or ''
        
        if not image:
            image = f"{url}{settings.STATIC_URL}images/og-image.png"
        
        base = {
            'title': title,
            'description': description[:160],  # Truncate for SEO
            'keywords': ', '.join(keywords) if keywords else '',
            'canonical': url,
            'robots': 'index, follow',
            
            # Open Graph
            'og_title': title,
            'og_description': description[:160],
            'og_image': image,
            'og_url': url,
            'og_type': page_type,
            'og_site_name': 'PrintHub',
            
            # Twitter
            'twitter_card': 'summary_large_image',
            'twitter_title': title[:70],
            'twitter_description': description[:160],
            'twitter_image': image,
            
            # JSON-LD
            'json_ld': SEOGenerator.get_json_ld(page_type, {
                'name': title,
                'description': description,
                'url': url,
                'image': image
            })
        }
        
        return base
    
    @staticmethod
    def get_json_ld(page_type: str, data: Dict) -> str:
        """Generate JSON-LD structured data"""
        
        base_schema = {
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            'name': 'PrintHub',
            'url': settings.BASE_URL,
            'description': 'Fast, reliable printing services for students at Kabale University',
            'potentialAction': {
                '@type': 'SearchAction',
                'target': f"{settings.BASE_URL}/search/?q={{search_term_string}}",
                'query-input': 'required name=search_term_string'
            }
        }
        
        # Page-specific schemas
        schemas = []
        schemas.append(base_schema)
        
        if page_type == 'Product':
            product_schema = {
                '@context': 'https://schema.org',
                '@type': 'Product',
                'name': data.get('name', 'PrintHub Printing Services'),
                'description': data.get('description', 'High-quality printing services'),
                'url': data.get('url', settings.BASE_URL),
                'image': data.get('image'),
                'offers': {
                    '@type': 'Offer',
                    'priceCurrency': 'UGX',
                    'price': '200',
                    'availability': 'https://schema.org/InStock'
                }
            }
            schemas.append(product_schema)
        
        return json.dumps(schemas, indent=2)

class MetaTags:
    """Predefined meta tags for common pages"""
    
    HOME = {
        'title': 'PrintHub — Kabale University Printing Services',
        'description': 'Upload your documents, pay with MTN or Airtel, and pick up at your nearest campus station. Fast, reliable printing for students at Kabale University.',
        'keywords': ['printing', 'Kabale University', 'student printing', 'document upload', 'MTN payment', 'Airtel payment']
    }
    
    UPLOAD = {
        'title': 'Upload Documents for Printing — PrintHub',
        'description': 'Upload PDF, DOC, or image files for printing. Quick, affordable printing services for students.',
        'keywords': ['upload documents', 'print PDF', 'student printing', 'document printing']
    }
    
    DASHBOARD = {
        'title': 'My Orders — PrintHub Dashboard',
        'description': 'View and track your printing orders. Check status, payment, and pickup details.',
        'keywords': ['track order', 'printing status', 'order history']
    }
    
    PRICING = {
        'title': 'Printing Prices — Affordable Student Printing',
        'description': 'See our competitive pricing for B&W and color printing. Special rates for students at Kabale University.',
        'keywords': ['printing prices', 'cost per page', 'student rates', 'affordable printing']
    }
