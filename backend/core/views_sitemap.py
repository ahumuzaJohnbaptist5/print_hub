# core/views_sitemap.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from orders.models import Order
from stations.models import Station

class StaticSitemap(Sitemap):
    """Sitemap for static pages"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        return [
            ('home', 'Home'),
            ('upload', 'Upload Document'),
            ('dashboard', 'Dashboard'),
            ('track_order', 'Track Order'),
            ('live_board', 'Live Board'),
        ]
    
    def location(self, item):
        return reverse(item[0])
    
    def lastmod(self, item):
        return timezone.now()

class OrderSitemap(Sitemap):
    """Sitemap for order detail pages"""
    changefreq = "daily"
    priority = 0.6
    
    def items(self):
        # Only show completed or ready orders (not pending/cancelled)
        return Order.objects.filter(
            status__in=['ready', 'collected', 'completed']
        ).order_by('-created_at')[:1000]
    
    def lastmod(self, obj):
        return obj.updated_at or obj.created_at

class StationSitemap(Sitemap):
    """Sitemap for station pages"""
    changefreq = "monthly"
    priority = 0.5
    
    def items(self):
        return Station.objects.filter(is_active=True)
    
    def lastmod(self, obj):
        return obj.updated_at or timezone.now()
