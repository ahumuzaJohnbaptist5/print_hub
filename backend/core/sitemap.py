# core/sitemap.py
"""
Sitemap generation for PrintHub
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from orders.models import Order
from stations.models import Station
from django.conf import settings

class StaticSitemap(Sitemap):
    """Sitemap for static pages"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        return [
            ('home', 'home'),
            ('upload', 'upload'),
            ('pricing', 'pricing'),
            ('dashboard', 'dashboard'),
            ('track_order', 'track_order'),
        ]
    
    def location(self, item):
        return reverse(item[0])
    
    def lastmod(self, item):
        return timezone.now()

class OrderSitemap(Sitemap):
    """Sitemap for order pages"""
    changefreq = "daily"
    priority = 0.6
    
    def items(self):
        # Show recent orders that are public
        return Order.objects.filter(
            status__in=['ready', 'completed'],
            is_public=True
        )[:1000]  # Limit for performance
    
    def location(self, obj):
        return f"/orders/{obj.id}/"
    
    def lastmod(self, obj):
        return obj.updated_at or obj.created_at

class StationSitemap(Sitemap):
    """Sitemap for station pages"""
    changefreq = "monthly"
    priority = 0.5
    
    def items(self):
        return Station.objects.filter(is_active=True)
    
    def location(self, obj):
        return f"/stations/{obj.id}/"
    
    def lastmod(self, obj):
        return obj.updated_at or timezone.now()

class CombinedSitemap(Sitemap):
    """Combined sitemap for all pages"""
    
    def items(self):
        # Combine all sitemaps
        items = []
        
        # Static pages
        static = StaticSitemap()
        items.extend(static.items())
        
        # Recent orders (limit to 500 for performance)
        orders = Order.objects.filter(
            status__in=['ready', 'completed']
        ).order_by('-created_at')[:500]
        items.extend(orders)
        
        # Stations
        stations = Station.objects.filter(is_active=True)
        items.extend(stations)
        
        return items
    
    def location(self, obj):
        if isinstance(obj, tuple):
            return reverse(obj[0])
        elif isinstance(obj, Order):
            return f"/orders/{obj.id}/"
        elif isinstance(obj, Station):
            return f"/stations/{obj.id}/"
        return '/'
    
    def lastmod(self, obj):
        if isinstance(obj, tuple):
            return timezone.now()
        elif hasattr(obj, 'updated_at'):
            return obj.updated_at or obj.created_at
        return timezone.now()
