from django.db import models
from django.conf import settings

class AssistantDraft(models.Model):
    """
    Secure, database-backed draft order.
    Replaces the insecure in-memory DRAFT_ORDERS dictionary.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='assistant_draft'
    )
    page_count = models.IntegerField(null=True, blank=True)
    is_color = models.BooleanField(default=False)
    is_double_sided = models.BooleanField(default=False)
    binding = models.CharField(max_length=20, default='none')
    delivery_type = models.CharField(max_length=20, default='pickup')
    discount_code = models.CharField(max_length=50, null=True, blank=True)
    station_id = models.IntegerField(null=True, blank=True)
    
    # File upload fields
    file = models.FileField(upload_to='assistant_uploads/%Y/%m/%d/', null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Draft for {self.user.username}"
