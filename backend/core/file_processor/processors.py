# file_processor/processors.py
import os
import json
from django.core.files.base import ContentFile
from .validators import FileValidator
from .preview import PreviewGenerator
from .converters import FileConverter

class FileProcessor:
    """Main file processing orchestrator"""
    
    def __init__(self, file, file_name):
        self.file = file
        self.file_name = file_name
        self.file.seek(0)
    
    def process(self):
        """Process the file and return all info"""
        result = {
            'success': False,
            'errors': [],
            'info': {},
            'preview': {},
            'converted': None
        }
        
        # Validate
        errors = FileValidator.validate_file(self.file)
        if errors:
            result['errors'] = errors
            return result
        
        # Get file info
        result['info'] = FileConverter.get_file_info(self.file, self.file_name)
        
        # Generate preview
        result['preview'] = PreviewGenerator.generate_preview(self.file, self.file_name)
        
        # Convert to PDF if needed
        ext = os.path.splitext(self.file_name)[1][1:].lower()
        if ext != 'pdf':
            try:
                pdf_buffer = FileConverter.convert_to_pdf(self.file, self.file_name)
                if pdf_buffer:
                    result['converted'] = ContentFile(pdf_buffer.getvalue(), 
                                                      name=f"{os.path.splitext(self.file_name)[0]}.pdf")
            except Exception as e:
                result['errors'].append(f"PDF conversion skipped: {str(e)}")
        
        result['success'] = True
        return result
    
    @staticmethod
    def get_processing_summary(file, file_name):
        """Get a summary without full processing"""
        ext = os.path.splitext(file_name)[1][1:].lower()
        return {
            'filename': file_name,
            'size': file.size,
            'extension': ext,
            'is_valid': ext in FileValidator.ALLOWED_EXTENSIONS
        }
