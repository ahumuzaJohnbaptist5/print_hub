import base64
import io
import json
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import mediapipe as mp

# Initialize MediaPipe once
mp_face_detection = mp.solutions.face_detection
mp_face_mesh = mp.solutions.face_mesh
face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.5)
face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)


def decode_base64_image(data_url):
    """Convert base64 data URL to PIL Image."""
    header, encoded = data_url.split(',', 1)
    image_data = base64.b64decode(encoded)
    return Image.open(io.BytesIO(image_data))


def encode_image_to_base64(image, format='JPEG', quality=90):
    """Convert PIL Image to base64 data URL."""
    buffer = io.BytesIO()
    image.save(buffer, format=format, quality=quality)
    encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/{format.lower()};base64,{encoded}'


def analyze_brightness(image):
    """Check if image brightness is acceptable."""
    gray = image.convert('L')
    pixels = np.array(gray)
    avg_brightness = np.mean(pixels)
    return {
        'value': round(avg_brightness, 1),
        'status': 'good' if 80 < avg_brightness < 200 else ('too_dark' if avg_brightness <= 80 else 'too_bright'),
        'label': 'Good' if 80 < avg_brightness < 200 else ('Too dark' if avg_brightness <= 80 else 'Too bright')
    }


def analyze_background(image):
    """Check background uniformity."""
    img = image.resize((200, 200))
    pixels = np.array(img)
    # Sample four corners
    corners = [
        pixels[10, 10], pixels[10, 190],
        pixels[190, 10], pixels[190, 190]
    ]
    # Calculate color variance between corners
    diffs = []
    for i in range(len(corners)):
        for j in range(i+1, len(corners)):
            diff = np.mean(np.abs(corners[i].astype(float) - corners[j].astype(float)))
            diffs.append(diff)
    avg_diff = np.mean(diffs) if diffs else 0
    score = max(0, 1 - avg_diff / 100)
    return {
        'value': round(score, 2),
        'status': 'uniform' if score > 0.6 else 'not_uniform',
        'label': 'Uniform' if score > 0.6 else 'Not uniform'
    }


def analyze_face(image):
    """Analyze face position, landmarks, and expression."""
    img_array = np.array(image.convert('RGB'))
    h, w = img_array.shape[:2]
    
    # Face detection
    results_detection = face_detection.process(img_array)
    
    if not results_detection.detections:
        return {
            'face_count': 0,
            'centered': False,
            'eyes_visible': False,
            'expression': 'no_face',
            'all_checks': False
        }
    
    if len(results_detection.detections) > 1:
        return {
            'face_count': len(results_detection.detections),
            'centered': False,
            'eyes_visible': False,
            'expression': 'multiple_faces',
            'all_checks': False
        }
    
    # Single face detected
    detection = results_detection.detections[0]
    bbox = detection.location_data.relative_bounding_box
    
    # Check if centered
    face_cx = bbox.xmin + bbox.width / 2
    face_cy = bbox.ymin + bbox.height / 2
    is_centered = abs(face_cx - 0.5) < 0.15 and abs(face_cy - 0.5) < 0.12
    face_size_ok = bbox.width > 0.25 and bbox.height > 0.3
    
    # Face mesh for landmarks
    results_mesh = face_mesh.process(img_array)
    has_landmarks = results_mesh.multi_face_landmarks is not None
    
    # Check eyes (landmarks 33, 133 for left eye, 362, 263 for right eye)
    eyes_visible = False
    if has_landmarks and results_mesh.multi_face_landmarks:
        landmarks = results_mesh.multi_face_landmarks[0]
        # Left eye landmarks
        left_eye_top = landmarks.landmark[159].y
        left_eye_bottom = landmarks.landmark[145].y
        left_eye_open = (left_eye_bottom - left_eye_top) > 0.008
        
        # Right eye landmarks
        right_eye_top = landmarks.landmark[386].y
        right_eye_bottom = landmarks.landmark[374].y
        right_eye_open = (right_eye_bottom - right_eye_top) > 0.008
        
        eyes_visible = left_eye_open and right_eye_open
    
    # Check expression (mouth landmarks for smile)
    expression = 'neutral'
    if has_landmarks and results_mesh.multi_face_landmarks:
        landmarks = results_mesh.multi_face_landmarks[0]
        # Mouth corners
        left_corner = landmarks.landmark[61]
        right_corner = landmarks.landmark[291]
        mouth_width = abs(right_corner.x - left_corner.x)
        # Simple heuristic: wider mouth = smile
        if mouth_width > 0.35:
            expression = 'smiling'
    
    all_checks = is_centered and face_size_ok and eyes_visible and expression == 'neutral'
    
    return {
        'face_count': 1,
        'centered': is_centered and face_size_ok,
        'centered_label': 'Centered' if (is_centered and face_size_ok) else 'Not centered',
        'eyes_visible': eyes_visible,
        'eyes_label': 'Visible' if eyes_visible else 'Not visible',
        'expression': expression,
        'expression_label': 'Neutral' if expression == 'neutral' else 'Not neutral',
        'all_checks': all_checks
    }


def remove_background(image):
    """Remove background using rembg."""
    try:
        from rembg import remove
        img_array = np.array(image)
        output = remove(img_array)
        return Image.fromarray(output)
    except Exception as e:
        print(f"Background removal failed: {e}")
        return image


def apply_background_color(image, color_hex='#ffffff'):
    """Apply a solid background color."""
    # Convert hex to RGB
    color_hex = color_hex.lstrip('#')
    bg_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
    
    # Create background
    bg = Image.new('RGBA', image.size, bg_color + (255,))
    
    # If image has alpha, composite it
    if image.mode == 'RGBA':
        return Image.alpha_composite(bg, image).convert('RGB')
    return image.convert('RGB')


def auto_crop_passport(image, size='4x6'):
    """Auto-crop to passport dimensions."""
    # Target sizes
    if size == '2x2':
        target_ratio = 1.0
        target_width = 600
    else:  # 4x6
        target_ratio = 1.5
        target_width = 1200
    
    target_height = int(target_width * target_ratio)
    
    # Find face and crop around it
    img_array = np.array(image.convert('RGB'))
    results = face_detection.process(img_array)
    
    if results.detections:
        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box
        h, w = img_array.shape[:2]
        
        # Calculate face center
        face_cx = int((bbox.xmin + bbox.width / 2) * w)
        face_cy = int((bbox.ymin + bbox.height / 2) * h)
        face_w = int(bbox.width * w)
        face_h = int(bbox.height * h)
        
        # Calculate crop area (head should be ~70% of height)
        crop_h = int(face_h * 2.5)
        crop_w = int(crop_h / target_ratio)
        
        crop_x1 = max(0, face_cx - crop_w // 2)
        crop_y1 = max(0, face_cy - int(crop_h * 0.4))
        crop_x2 = min(w, crop_x1 + crop_w)
        crop_y2 = min(h, crop_y1 + crop_h)
        
        cropped = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    else:
        cropped = image
    
    # Resize to target
    return cropped.resize((target_width, target_height), Image.LANCZOS)


def enhance_scanned_document(image):
    """Enhance a scanned document - B&W, contrast, sharpen."""
    # Convert to grayscale
    gray = image.convert('L')
    
    # Increase contrast
    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(2.0)
    
    # Increase sharpness
    enhancer = ImageEnhance.Sharpness(gray)
    gray = enhancer.enhance(2.0)
    
    # Threshold for B&W effect
    pixels = np.array(gray)
    threshold = 128
    bw = np.where(pixels > threshold, 255, 0).astype(np.uint8)
    
    # Convert back to PIL
    result = Image.fromarray(bw)
    
    # Enhance edges
    result = result.filter(ImageFilter.EDGE_ENHANCE_MORE)
    
    return result


@csrf_exempt
@require_POST
def analyze_passport_frame(request):
    """Analyze a video frame for passport photo quality."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        
        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image = decode_base64_image(image_data)
        
        # Run all checks
        face_result = analyze_face(image)
        brightness_result = analyze_brightness(image)
        background_result = analyze_background(image)
        
        # Combine results
        analysis = {
            'face_position': {
                'status': 'pass' if face_result['centered'] else 'fail',
                'label': face_result.get('centered_label', 'No face')
            },
            'brightness': {
                'status': 'pass' if brightness_result['status'] == 'good' else 'fail',
                'label': brightness_result['label'],
                'value': brightness_result['value']
            },
            'eyes': {
                'status': 'pass' if face_result['eyes_visible'] else 'fail',
                'label': face_result.get('eyes_label', 'Not visible')
            },
            'expression': {
                'status': 'pass' if face_result['expression'] == 'neutral' else 'fail',
                'label': face_result.get('expression_label', 'Not neutral')
            },
            'background': {
                'status': 'pass' if background_result['status'] == 'uniform' else 'fail',
                'label': background_result['label'],
                'value': background_result['value']
            },
            'overall': {
                'status': 'pass' if face_result.get('all_checks') and brightness_result['status'] == 'good' and background_result['status'] == 'uniform' else 'fail',
                'label': 'Ready!' if face_result.get('all_checks') and brightness_result['status'] == 'good' and background_result['status'] == 'uniform' else 'Keep adjusting'
            }
        }
        
        return JsonResponse({'success': True, 'analysis': analysis})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def process_passport_photo(request):
    """Process captured passport photo."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        bg_color = data.get('bg_color', '#ffffff')
        size = data.get('size', '4x6')
        
        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image = decode_base64_image(image_data)
        
        # Remove background
        image_no_bg = remove_background(image)
        
        # Apply new background
        image_with_bg = apply_background_color(image_no_bg, bg_color)
        
        # Auto-crop
        final_image = auto_crop_passport(image_with_bg, size)
        
        # Encode result
        result_base64 = encode_image_to_base64(final_image)
        
        return JsonResponse({
            'success': True,
            'processed_image': result_base64
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def process_scanned_document(request):
    """Process a scanned document page."""
    try:
        data = json.loads(request.body)
        image_data = data.get('image')
        
        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        image = decode_base64_image(image_data)
        
        # Enhance document
        enhanced = enhance_scanned_document(image)
        
        # Encode result
        result_base64 = encode_image_to_base64(enhanced)
        
        return JsonResponse({
            'success': True,
            'processed_image': result_base64
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
