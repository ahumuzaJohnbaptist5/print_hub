# backend/core/management/commands/generate_sitemap.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
import xml.etree.ElementTree as ET

from orders.models import Order
from stations.models import Station


class Command(BaseCommand):
    help = 'Generate sitemap.xml for SEO'

    def handle(self, *args, **options):
        self.stdout.write('📁 Generating sitemap...')
        
        root = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        base_url = settings.BASE_URL
        
        # Static pages
        pages = [
            ('/', 'daily', '1.0'),
            ('/upload/', 'weekly', '0.9'),
            ('/dashboard/', 'weekly', '0.8'),
            ('/track/', 'weekly', '0.8'),
            ('/live-board/', 'daily', '0.7'),
            ('/auth/login/', 'monthly', '0.5'),
            ('/auth/register/', 'monthly', '0.5'),
        ]
        
        for path, freq, priority in pages:
            url = ET.SubElement(root, 'url')
            loc = ET.SubElement(url, 'loc')
            loc.text = f"{base_url}{path}"
            lastmod = ET.SubElement(url, 'lastmod')
            lastmod.text = timezone.now().date().isoformat()
            changefreq = ET.SubElement(url, 'changefreq')
            changefreq.text = freq
            priority_elem = ET.SubElement(url, 'priority')
            priority_elem.text = priority
        
        # Stations
        for station in Station.objects.filter(is_active=True):
            url = ET.SubElement(root, 'url')
            loc = ET.SubElement(url, 'loc')
            loc.text = f"{base_url}/stations/{station.id}/"
            lastmod = ET.SubElement(url, 'lastmod')
            lastmod.text = (station.updated_at or timezone.now()).date().isoformat()
            changefreq = ET.SubElement(url, 'changefreq')
            changefreq.text = 'monthly'
            priority_elem = ET.SubElement(url, 'priority')
            priority_elem.text = '0.6'
        
        # Recent orders
        for order in Order.objects.filter(status__in=['ready', 'collected']).order_by('-created_at')[:200]:
            url = ET.SubElement(root, 'url')
            loc = ET.SubElement(url, 'loc')
            loc.text = f"{base_url}/track/?order_id={order.id}"
            lastmod = ET.SubElement(url, 'lastmod')
            lastmod.text = (order.updated_at or order.created_at).date().isoformat()
            changefreq = ET.SubElement(url, 'changefreq')
            changefreq.text = 'daily'
            priority_elem = ET.SubElement(url, 'priority')
            priority_elem.text = '0.6'
        
        # Write to file
        tree = ET.ElementTree(root)
        tree.write('templates/sitemap.xml', encoding='utf-8', xml_declaration=True)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Sitemap generated with {len(root)} URLs'))
