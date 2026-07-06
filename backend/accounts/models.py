from django.contrib.auth.models import AbstractUser
from django.db import models


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

    def __str__(self):
        return self.username
