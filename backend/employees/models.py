# backend/employees/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()


class Application(models.Model):
    """Job application form for PrintHub employees."""
    
    # ─── STAGES ──────────────────────────────────────────────
    STAGE_CHOICES = [
        ('order_verifier', 'Order Verifier'),
        ('document_processor', 'Document Processor'),
        ('print_operator', 'Print Operator'),
        ('qc_inspector', 'Quality Control Inspector'),
        ('pickup_coordinator', 'Pickup/Delivery Coordinator'),
        ('customer_support', 'Customer Support'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interview', 'Interview Scheduled'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    # ─── PERSONAL INFORMATION ────────────────────────────────
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    location = models.CharField(max_length=200, help_text="Current location/city")
    
    # ─── APPLICATION DETAILS ──────────────────────────────────
    applied_stage = models.CharField(max_length=50, choices=STAGE_CHOICES)
    experience_years = models.IntegerField(default=0)
    availability = models.CharField(max_length=200, help_text="When can you start?")
    
    # ─── QUESTIONS ────────────────────────────────────────────
    why_work = models.TextField(max_length=500, help_text="Why do you want to work at PrintHub?")
    experience = models.TextField(max_length=1000, help_text="Describe your relevant experience")
    skills = models.TextField(max_length=500, help_text="List your skills")
    
    # ─── STAGE SPECIFIC QUESTIONS ─────────────────────────────
    # Order Verifier
    attention_to_detail = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Rate your attention to detail (1-10)"
    )
    
    # Document Processor
    software_proficiency = models.CharField(
        max_length=200, null=True, blank=True,
        help_text="List software you're proficient with"
    )
    
    # Print Operator
    printer_experience = models.CharField(
        max_length=500, null=True, blank=True,
        help_text="Describe your printer experience"
    )
    
    # QC Inspector
    quality_standards = models.CharField(
        max_length=500, null=True, blank=True,
        help_text="Do you know quality control standards?"
    )
    
    # Customer Support
    customer_service = models.CharField(
        max_length=500, null=True, blank=True,
        help_text="Describe your customer service experience"
    )
    
    # ─── RESUME / CV ──────────────────────────────────────────
    resume = models.FileField(
        upload_to='resumes/%Y/%m/%d/',
        null=True, blank=True,
        help_text="Upload your CV/Resume (PDF, DOCX)"
    )
    
    # ─── STATUS ──────────────────────────────────────────────
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    reviewer_notes = models.TextField(blank=True, help_text="Internal notes for reviewers")
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_applications'
    )
    
    # ─── TIMESTAMPS ───────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_applied_stage_display()}"
    
    def get_stage_questions(self):
        """Get stage-specific questions for display."""
        questions = {
            'order_verifier': {
                'label': 'Attention to Detail',
                'value': self.attention_to_detail,
                'type': 'rating'
            },
            'document_processor': {
                'label': 'Software Proficiency',
                'value': self.software_proficiency,
                'type': 'text'
            },
            'print_operator': {
                'label': 'Printer Experience',
                'value': self.printer_experience,
                'type': 'textarea'
            },
            'qc_inspector': {
                'label': 'Quality Standards Knowledge',
                'value': self.quality_standards,
                'type': 'textarea'
            },
            'customer_support': {
                'label': 'Customer Service Experience',
                'value': self.customer_service,
                'type': 'textarea'
            },
        }
        return questions.get(self.applied_stage, {})
