# file_processor/converters.py
import os
import io
from PIL import Image
import PyPDF2
from docx2pdf import convert
import subprocess

class FileConverter:
    """Convert files between formats"""
    
    @staticmethod
    def convert_to_pdf(file, file_name):
        """Convert various formats to PDF"""
        ext = os.path.splitext(file_name)[1][1:].lower()
        
        if ext == 'pdf':
            return file
        
        elif ext in ['jpg', 'jpeg', 'png']:
            return FileConverter._image_to_pdf(file)
        
        elif ext in ['docx', 'doc']:
            return FileConverter._word_to_pdf(file, file_name)
        
        elif ext == 'txt':
            return FileConverter._text_to_pdf(file)
        
        else:
            raise ValueError(f"Cannot convert {ext} to PDF")
    
    @staticmethod
    def _image_to_pdf(file):
        """Convert image to PDF"""
        try:
            img = Image.open(file)
            pdf_buffer = io.BytesIO()
            img.convert('RGB').save(pdf_buffer, format='PDF')
            pdf_buffer.seek(0)
            return pdf_buffer
        except Exception as e:
            raise Exception(f"Image to PDF conversion failed: {str(e)}")
    
    @staticmethod
    def _text_to_pdf(file):
        """Convert text to PDF"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            
            # Read text content
            content = file.read().decode('utf-8')
            file.seek(0)
            
            # Add text to PDF
            y = 750
            for line in content.split('\n')[:50]:
                if y < 50:
                    c.showPage()
                    y = 750
                c.drawString(50, y, line[:100])
                y -= 15
            
            c.save()
            pdf_buffer.seek(0)
            return pdf_buffer
        except Exception as e:
            raise Exception(f"Text to PDF conversion failed: {str(e)}")
    
    @staticmethod
    def _word_to_pdf(file, file_name):
        """Convert Word to PDF"""
        try:
            # Save temp file
            temp_path = f"/tmp/{file_name}"
            with open(temp_path, 'wb') as f:
                f.write(file.read())
            file.seek(0)
            
            # Convert using subprocess (requires LibreOffice)
            output_path = temp_path.replace('.docx', '.pdf')
            subprocess.run([
                'libreoffice', '--headless', '--convert-to', 'pdf',
                temp_path, '--outdir', '/tmp/'
            ], check=True)
            
            with open(output_path, 'rb') as f:
                pdf_content = io.BytesIO(f.read())
            
            # Cleanup
            os.remove(temp_path)
            if os.path.exists(output_path):
                os.remove(output_path)
            
            pdf_content.seek(0)
            return pdf_content
        except Exception:
            # Fallback to text extraction
            raise Exception("Word to PDF conversion requires LibreOffice")
    
    @staticmethod
    def get_file_info(file, file_name):
        """Get detailed file information"""
        ext = os.path.splitext(file_name)[1][1:].lower()
        
        info = {
            'name': file_name,
            'size': file.size,
            'extension': ext,
            'type': 'unknown'
        }
        
        if ext in ['jpg', 'jpeg', 'png']:
            try:
                img = Image.open(file)
                info['type'] = 'image'
                info['dimensions'] = img.size
                info['mode'] = img.mode
                file.seek(0)
            except:
                pass
        
        elif ext == 'pdf':
            try:
                reader = PyPDF2.PdfReader(file)
                info['type'] = 'pdf'
                info['pages'] = len(reader.pages)
                file.seek(0)
            except:
                pass
        
        elif ext in ['docx', 'doc']:
            info['type'] = 'document'
        
        elif ext == 'pptx':
            info['type'] = 'presentation'
        
        elif ext == 'txt':
            info['type'] = 'text'
        
        return info
