import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from orders.models import Order
from .processors import FileProcessor
from .utils import get_file_size_human

@login_required
@csrf_exempt
def process_file(request):
    """API endpoint to process uploaded file"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    processor = FileProcessor(file, file.name)
    result = processor.process()
    
    if result.get('info'):
        result['info']['size_human'] = get_file_size_human(result['info']['size'])
    
    return JsonResponse(result)

@login_required
def file_preview(request, order_id):
    """Get preview for an order's file"""
    try:
        order = Order.objects.get(id=order_id, client=request.user)
        if not order.file:
            return JsonResponse({'error': 'No file found'}, status=404)
        
        processor = FileProcessor(order.file, order.file_name)
        preview = processor.process().get('preview', {})
        return JsonResponse(preview)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)

@login_required
def file_info(request, order_id):
    """Get file information for an order"""
    try:
        order = Order.objects.get(id=order_id, client=request.user)
        if not order.file:
            return JsonResponse({'error': 'No file found'}, status=404)
        
        info = FileProcessor.get_processing_summary(order.file, order.file_name)
        info['size_human'] = get_file_size_human(order.file.size)
        return JsonResponse(info)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
