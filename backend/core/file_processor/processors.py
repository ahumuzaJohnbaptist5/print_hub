import os
from django.core.files.base import ContentFile

class FileProcessor:
    """Main file processing orchestrator"""
    
    def __init__(self, file, file_name):
        self.file = file
        self.file_name = file_name
        self.file.seek(0)
    
    def process(self):
        """Process the file and return all info"""
        result = {
            'success': True,
            'errors': [],
            'info': {
                'name': self.file_name,
                'size': self.file.size,
                'extension': os.path.splitext(self.file_name)[1][1:].lower(),
                'type': 'unknown'
            },
            'preview': {'type': 'unknown'},
            'converted': None
        }
        return result
    
    @staticmethod
    def get_processing_summary(file, file_name):
        """Get a summary without full processing"""
        ext = os.path.splitext(file_name)[1][1:].lower()
        return {
            'filename': file_name,
            'size': file.size,
            'extension': ext,
            'is_valid': True
        }
