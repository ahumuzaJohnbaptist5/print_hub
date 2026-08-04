# backend/core/sitemap.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone


class StaticSitemap(Sitemap):
    """Sitemap for static pages only - no database queries."""
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


# ─── ONLY STATIC SITEMAP ─────────────────────────────────────
sitemaps = {
    'static': StaticSitemap,
    # No orders, no stations - nothing that can error
}
