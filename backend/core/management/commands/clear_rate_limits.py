# core/management/commands/clear_rate_limits.py
from django.core.management.base import BaseCommand
from django.core.cache import cache
import re

class Command(BaseCommand):
    help = 'Clear all rate limit caches'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix',
            type=str,
            help='Only clear rate limits with this prefix (e.g., ratelimit:login)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear all caches (use with caution)',
        )

    def handle(self, *args, **options):
        prefix = options.get('prefix')
        
        if options.get('all'):
            self.stdout.write('⚠️  Clearing ALL cache...')
            cache.clear()
            self.stdout.write(self.style.SUCCESS('✅ All cache cleared!'))
            return
        
        if prefix:
            # Clear specific prefix
            # Note: This is a simplified version - in production, use Redis SCAN
            self.stdout.write(f'🧹 Clearing rate limits with prefix: {prefix}')
            # In a real implementation, you'd use Redis SCAN or similar
            self.stdout.write(self.style.WARNING('⚠️  This operation requires Redis SCAN support'))
            self.stdout.write('💡 Tip: Use --all to clear everything')
            return
        
        self.stdout.write(self.style.WARNING('⚠️  Please specify --prefix or --all'))
        self.stdout.write('Example: python manage.py clear_rate_limits --prefix ratelimit:login')
        self.stdout.write('Example: python manage.py clear_rate_limits --all')
