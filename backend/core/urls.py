from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.conf import settings
from orders.views import live_board_preview_image

@never_cache
def service_worker(request):
    with open(settings.BASE_DIR / 'sw.js', 'r') as f:
        return HttpResponse(f.read(), content_type='application/javascript')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('accounts.urls')),
    
    # Orders - ALL under /orders/ prefix
    path('orders/', include('orders.urls')),
    
    # Live board preview (standalone)
    path('orders/live-board-preview.png', live_board_preview_image, name='live_board_preview'),
    
    # Other apps
    path('payments/', include('payments.urls')),
    path('finances/', include('finances.urls')),
    path('notifications/', include('notifications.urls')),
    path('whatsapp/', include('whatsapp_bot.urls')),
    
    # Service worker
    path('sw.js', service_worker),
]
