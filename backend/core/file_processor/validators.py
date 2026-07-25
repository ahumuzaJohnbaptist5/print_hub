# file_processor/validators.py
import os
import magic
from PIL import Image
import PyPDF2
from django.core.exceptions import ValidationError

class FileValidator:
    """Enhanced file validation"""
    
    ALLOWED_EXTENSIONS = {
        'pdf': ['application/pdf'],
        'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'doc': ['application/msword'],
        'pptx': ['application/vnd.openxmlformats-officedocument.presentationml.presentation'],
        'jpg': ['image/jpeg'],
        'jpeg': ['image/jpeg'],
        'png': ['image/png'],
        'txt': ['text/plain'],
    }
    
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    
    @classmethod
    def validate_file(cls, file):
        """Validate file type, size, and content"""
        errors = []
        
        # Check size
        if file.size > cls.MAX_FILE_SIZE:
            errors.append(f"File too large. Max size: {cls.MAX_FILE_SIZE / 1024 / 1024}MB")
        
        # Check extension
        ext = os.path.splitext(file.name)[1][1:].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            errors.append(f"File type '{ext}' not allowed")
        
        # Check MIME type
        try:
            file_content = file.read(1024)
            file.seek(0)
            mime = magic.from_buffer(file_content, mime=True)
            allowed_mimes = cls.ALLOWED_EXTENSIONS.get(ext, [])
            if allowed_mimes and mime not in allowed_mimes:
                errors.append(f"Invalid file content. Expected {allowed_mimes[0]}, got {mime}")
        except Exception:
            pass
        
        return errors
    
    @classmethod
    def validate_image(cls, file):
        """Validate image files"""
        try:
            img = Image.open(file)
            if img.mode not in ['RGB', 'RGBA']:
                return ["Image format not supported"]
            
            # Check dimensions
            width, height = img.size
            if width < 100 or height < 100:
                return ["Image too small. Min 100x100 pixels"]
            if width > 5000 or height > 5000:
                return ["Image too large. Max 5000x5000 pixels"]
            
            return []
        except Exception as e:
            return [f"Invalid image: {str(e)}"]
