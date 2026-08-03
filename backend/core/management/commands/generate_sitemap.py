# core/management/commands/generate_sitemap.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from core.sitemap import CombinedSitemap
import os
import xml.etree.ElementTree as ET
from datetime import datetime

class Command(BaseCommand):
    help = 'Generate sitemap.xml for SEO'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='templates/sitemap.xml',
            help='Output file path'
        )
    
    def handle(self, *args, **options):
        output_file = options['output']
        
        self.stdout.write('📁 Generating sitemap...')
        
        # Generate sitemap using Django's built-in
        from django.contrib.sitemaps.views import sitemap
        from django.http import HttpRequest
        
        # Create sitemap
        sitemap_obj = CombinedSitemap()
        urls = []
        
        for item in sitemap_obj.items():
            location = sitemap_obj.location(item)
            lastmod = sitemap_obj.lastmod(item)
            priority = getattr(sitemap_obj, 'priority', 0.5)
            changefreq = getattr(sitemap_obj, 'changefreq', 'weekly')
            
            urls.append({
                'loc': f"{settings.BASE_URL}{location}",
                'lastmod': lastmod,
                'priority': priority,
                'changefreq': changefreq
            })
        
        # Generate XML
        root = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        
        for url_data in urls:
            url_elem = ET.SubElement(root, 'url')
            
            loc = ET.SubElement(url_elem, 'loc')
            loc.text = url_data['loc']
            
            if url_data['lastmod']:
                lastmod = ET.SubElement(url_elem, 'lastmod')
                lastmod.text = url_data['lastmod'].isoformat()
            
            changefreq = ET.SubElement(url_elem, 'changefreq')
            changefreq.text = url_data['changefreq']
            
            priority = ET.SubElement(url_elem, 'priority')
            priority.text = str(url_data['priority'])
        
        # Write to file
        tree = ET.ElementTree(root)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Sitemap generated: {output_file} ({len(urls)} URLs)')
        )
