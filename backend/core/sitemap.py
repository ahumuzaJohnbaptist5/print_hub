# backend/core/sitemap.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from django.apps import apps


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
        Order = apps.get_model('orders', 'Order')
        return Order.objects.filter(
            status__in=['ready', 'collected', 'completed']
        ).order_by('-created_at')[:500]
    
    def lastmod(self, obj):
        return obj.updated_at or obj.created_at


# ─── REMOVED: StationSitemap ──────────────────────────────────


# ─── SITEMAPS DICTIONARY - Only static and orders ──────────
sitemaps = {
    'static': StaticSitemap,
    'orders': OrderSitemap,
    # 'stations': StationSitemap,  ← REMOVED
}
