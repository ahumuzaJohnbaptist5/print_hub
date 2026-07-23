from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from whatsapp_bot.views import send_whatsapp_message

class Command(BaseCommand):
    help = 'Send scheduled advert to WhatsApp groups'

    def add_arguments(self, parser):
        parser.add_argument('message', type=str, help='Advert message to send')

    def handle(self, *args, **options):
        message = options['message']
        group_ids = getattr(settings, 'WHATSAPP_GROUP_IDS', [])

        sent = 0
        for gid in group_ids:
            try:
                send_whatsapp_message(gid, f"📢 *PrintHub Update*\n\n{message}\n\n📞 {settings.WHATSAPP_BUSINESS_PHONE}\n🌐 printlink.pythonanywhere.com")
                sent += 1
                self.stdout.write(f"Sent to {gid}")
            except Exception as e:
                self.stdout.write(f"Failed {gid}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Advert sent to {sent} groups"))
