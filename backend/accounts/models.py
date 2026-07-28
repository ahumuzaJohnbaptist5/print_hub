from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid  # ✅ ADD THIS


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('admin', 'Administrator'),
        ('agent', 'Agent'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    station = models.ForeignKey(
        'stations.Station',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='agents',
    )
    
    # ✅ ADD THESE TWO FIELDS
   # email_verified = models.BooleanField(default=False)
    #email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.username
