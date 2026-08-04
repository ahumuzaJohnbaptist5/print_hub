# backend/core/sitemap.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from orders.models import Order
from stations.models import Station


class StaticSitemap(Sitemap):
    """Sitemap for static pages."""
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
    """Sitemap for order detail pages."""
    changefreq = "daily"
    priority = 0.6
    
    def items(self):
        # Show completed or ready orders (not pending/cancelled)
        return Order.objects.filter(
            status__in=['ready', 'collected', 'completed']
        ).order_by('-created_at')[:500]
    
    def lastmod(self, obj):
        return obj.updated_at or obj.created_at


class StationSitemap(Sitemap):
    """Sitemap for station pages."""
    changefreq = "monthly"
    priority = 0.5
    
    def items(self):
        return Station.objects.filter(is_active=True)
    
    def lastmod(self, obj):
        return obj.updated_at or timezone.now()


class CombinedSitemap(Sitemap):
    """Combined sitemap for all pages."""
    changefreq = "weekly"
    priority = 0.5
    
    def items(self):
        items = []
        
        # Static pages
        static = StaticSitemap()
        for item in static.items():
            items.append(('static', item))
        
        # Recent orders
        orders = Order.objects.filter(
            status__in=['ready', 'collected', 'completed']
        ).order_by('-created_at')[:200]
        for order in orders:
            items.append(('order', order))
        
        # Stations
        stations = Station.objects.filter(is_active=True)
        for station in stations:
            items.append(('station', station))
        
        return items
    
    def location(self, obj):
        item_type, obj_data = obj
        if item_type == 'static':
            return reverse(obj_data[0])
        elif item_type == 'order':
            return f"/track/?order_id={obj_data.id}"
        elif item_type == 'station':
            return f"/stations/{obj_data.id}/"
        return '/'
    
    def lastmod(self, obj):
        item_type, obj_data = obj
        if item_type == 'static':
            return timezone.now()
        elif hasattr(obj_data, 'updated_at'):
            return obj_data.updated_at or obj_data.created_at
        return timezone.now()
