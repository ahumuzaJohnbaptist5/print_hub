# backend/orders/views/client_views.py
import json
import logging
import base64
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.core.validators import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils.html import strip_tags

from stations.models import Station  # <-- FIXED: Import from correct app
from orders.models import Order, DeliveryZone, Announcement
from orders.utils import apply_order_status_change
from .helpers import (
    _user_role, _can_view_order, validate_upload_file,
    _build_order_queryset, _order_summary_counts,
    _get_tracked_orders, send_order_confirmation_email, send_cancellation_email
)

# Import file processor - wrap in try/except to avoid breaking if not installed
try:
    from file_processor.processors import FileProcessor
except ImportError:
    FileProcessor = None
    print("Warning: file_processor not available")

User = get_user_model()
logger = logging.getLogger(__name__)

@login_required
def dashboard_view(request):
    orders = Order.objects.filter(client=request.user).order_by('-created_at')
    stats = Order.objects.filter(client=request.user).aggregate(
        total_orders=Count('id'),
        completed_orders=Count('id', filter=Q(status='collected')),
        pending_orders=Count('id', filter=Q(status='pending')),
        total_spent=Sum('total_price', filter=Q(status__in=['paid', 'printing', 'in_transit', 'ready', 'collected']))
    )
    return render(request, 'orders/dashboard.html', {
        'orders': orders,
        'stats': stats,
    })

@transaction.atomic
def upload_view(request):
    stations = Station.objects.all()
    delivery_zones = DeliveryZone.objects.filter(is_active=True)
    upload_error = None
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in or create an account to complete your upload.')
            return redirect('/auth/login/?next=/upload/')
            
        file = request.FILES.get('file')
        page_count = request.POST.get('page_count', 1)
        is_color = request.POST.get('is_color', 'False') == 'True'
        is_double_sided = request.POST.get('is_double_sided') == 'on'
        station_id = request.POST.get('station')
        binding = request.POST.get('binding', 'none')
        delivery_type = request.POST.get('delivery_type', 'pickup')
        delivery_zone_id = request.POST.get('delivery_zone')
        notes = strip_tags(request.POST.get('notes', '').strip())
        
        order_type = request.POST.get('order_type', 'document')
        paper_size = request.POST.get('paper_size', 'A4')
        copies = request.POST.get('copies', 1)
        calculated_price = request.POST.get('calculated_price', '0')
        
        passport_data = request.POST.get('passport_data', '')
        scanner_data = request.POST.get('scanner_data', '')
        
        if not file and (passport_data or scanner_data):
            try:
                if passport_data:
                    format, imgstr = passport_data.split(';base64,')
                    ext = format.split('/')[-1]
                    file = ContentFile(
                        base64.b64decode(imgstr),
                        name=f'passport_photo.{ext}'
                    )
            except Exception as e:
                logger.error(f"Error processing camera/scanner data: {e}")
                upload_error = 'Error processing captured image.'
                
        if not file:
            upload_error = 'Please select a file.'
        else:
            upload_error = validate_upload_file(file)
            
        if upload_error:
            return render(request, 'orders/upload.html', {
                'stations': stations,
                'delivery_zones': delivery_zones,
                'upload_error': upload_error,
            })
        
        # File processing - only if file_processor is available
        processing_result = None
        if FileProcessor:
            try:
                processor = FileProcessor(file, file.name)
                processing_result = processor.process()
                if processing_result['success']:
                    logger.info(f"File processed successfully: {file.name}")
            except Exception as e:
                logger.error(f"File processing error: {e}")
            
        station = None
        if station_id and station_id.isdigit():
            station = Station.objects.filter(id=int(station_id)).first()
            
        delivery_zone = None
        if delivery_type == 'delivery' and delivery_zone_id and delivery_zone_id.isdigit():
            delivery_zone = DeliveryZone.objects.filter(id=int(delivery_zone_id)).first()
            
        try:
            page_count_int = int(page_count)
            copies_int = int(copies)
            
            if page_count_int < 1:
                raise ValueError("Page count must be at least 1")
            if copies_int < 1:
                copies_int = 1
                
            order_type_display = dict(Order.ORDER_TYPE_CHOICES).get(order_type, 'Document Print')
            paper_size_display = dict(Order.PAPER_SIZE_CHOICES).get(paper_size, 'A4')
            
            extra_notes = f"Order Type: {order_type_display}\n"
            extra_notes += f"Paper Size: {paper_size_display}\n"
            extra_notes += f"Copies: {copies_int}"
            
            if notes:
                notes = f"{notes}\n{extra_notes}"
            else:
                notes = extra_notes

            if order_type == 'passport':
                is_color = True
                binding = 'none'
                is_double_sided = False
                page_count_int = copies_int 
                
                passport_base_price = copies_int * Order.PASSPORT_PHOTO_PRICE
                delivery_fee = delivery_zone.delivery_fee if delivery_zone and delivery_type == 'delivery' else 0
                calculated_price = str(passport_base_price + delivery_fee)
                
            elif order_type == 'scanned':
                binding = 'none'
                is_double_sided = False
                page_count_int = copies_int if copies_int > page_count_int else page_count_int

            order = Order(
                client=request.user,
                station=station,
                file=file,
                file_name=file.name,
                page_count=page_count_int,
                is_color=is_color,
                is_double_sided=is_double_sided,
                binding=binding,
                delivery_type=delivery_type,
                delivery_zone=delivery_zone,
                notes=notes,
                status='pending',
                order_type=order_type,
                paper_size=paper_size,
                copies=copies_int,
            )
            
            # Add file metadata if processing succeeded
            if processing_result and processing_result.get('success'):
                order.file_metadata = processing_result.get('info', {})
                if processing_result.get('preview'):
                    order.file_preview = processing_result['preview'].get('preview', '')
                    if 'thumbnail' in processing_result['preview']:
                        order.file_thumbnail = processing_result['preview'].get('thumbnail', '')
            
            if calculated_price:
                try:
                    js_price = Decimal(str(calculated_price))
                    if js_price > 0:
                        order.total_price = js_price
                except Exception:
                    pass
                    
            order.save()
            
            try:
                send_order_confirmation_email(order)
            except Exception as e:
                logger.error(f"Failed to send confirmation email for order #{order.id}: {e}", exc_info=True)
                
            messages.success(request, f'Order #{order.id} submitted! Total: {order.total_price:,.0f} UGX')
            return redirect('order_receipt', order_id=order.id)
            
        except ValueError as e:
            upload_error = f'Invalid input: {str(e)}'
        except Exception as e:
            logger.error(f"Error creating order: {e}", exc_info=True)
            upload_error = 'Error creating order. Please try again.'
            
        return render(request, 'orders/upload.html', {
            'stations': stations,
            'delivery_zones': delivery_zones,
            'upload_error': upload_error,
        })

    return render(request, 'orders/upload.html', {
        'stations': stations,
        'delivery_zones': delivery_zones,
        'upload_error': upload_error,
    })

# ... rest of client_views.py (keep your existing functions)
